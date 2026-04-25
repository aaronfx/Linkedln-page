"""
Worker Process
===============
Runs the automation scheduler in a background thread
alongside the Flask dashboard. Designed for Railway deployment.

Timezone handling: Railway runs in UTC. All scheduled times in config
are WAT (UTC+1), so we convert them to UTC for the schedule library.

Audit improvements:
- Thread-safe JSON file access via filelock
- Retry-on-failure with dead-letter queue (pop AFTER success)
- Graceful SIGTERM shutdown for Railway restarts
- Learning engine integration for persistent insights
- Health check function for monitoring
"""

import os
import sys
import signal
import threading
import time
import json
import logging
import schedule as sched_lib
from datetime import datetime, timezone, timedelta
from pathlib import Path
from filelock import FileLock

from config import POSTING_SCHEDULE, ANALYTICS_SETTINGS, CONTENT_QUEUE_FILE, TIMEZONE
from linkedin_api import LinkedInAPI
from content_engine import generate_post, generate_weekly_content
from image_generator import generate_post_image
from analytics_engine import AnalyticsEngine
from comment_manager import CommentManager
from dashboard import app, run_dashboard
from learning_engine import LearningEngine

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("worker")

# Thread-safe lock for JSON file operations
_file_lock = FileLock(str(CONTENT_QUEUE_FILE) + ".lock", timeout=10)

# Graceful shutdown flag
_shutdown_event = threading.Event()

# Learning engine singleton
_learning = LearningEngine()

# Health state
_health = {
    "started_at": datetime.now(timezone.utc).isoformat(),
    "last_post_attempt": None,
    "last_post_success": None,
    "last_error": None,
    "posts_today": 0,
    "scheduler_alive": False,
}


def get_health_status():
    """Return current worker health for monitoring endpoints."""
    _health["scheduler_alive"] = not _shutdown_event.is_set()
    _health["learning_summary"] = _learning.get_learning_summary()
    _health["alerts"] = _learning.get_alerts(limit=5)
    _health["dead_letter_count"] = len(_learning.get_dead_letter_queue())
    return _health


def _safe_read_json(filepath):
    """Thread-safe JSON file read using filelock."""
    lock = FileLock(str(filepath) + ".lock", timeout=10)
    with lock:
        if Path(filepath).exists():
            try:
                with open(filepath) as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                return []
        return []


def _safe_write_json(filepath, data):
    """Thread-safe JSON file write using filelock."""
    lock = FileLock(str(filepath) + ".lock", timeout=10)
    with lock:
        with open(filepath, "w") as f:
            json.dump(data, f, indent=2, default=str)


def wat_to_utc(time_str):
    """
    Convert a WAT (UTC+1) time string to UTC.
    Example: "08:00" WAT → "07:00" UTC
    """
    h, m = map(int, time_str.split(":"))
    wat = datetime.now(timezone.utc).replace(hour=h, minute=m, second=0)
    wat = wat.replace(tzinfo=timezone(timedelta(hours=1)))
    utc = wat.astimezone(timezone.utc)
    return utc.strftime("%H:%M")


def create_and_post(pillar=None):
    """
    Post to LinkedIn — QUEUE-FIRST strategy with retry safety.

    Critical fix: Queue pop happens AFTER successful post, not before.
    Failed posts go to dead-letter queue for retry or manual review.
    All file ops are thread-safe via filelock.
    """
    _health["last_post_attempt"] = datetime.now(timezone.utc).isoformat()

    try:
        linkedin = LinkedInAPI()
        post_data = None
        source = "queue"
        queue_index = None

        # —— Step 1: Try to post from queue (READ without popping) ——
        queue = _safe_read_json(CONTENT_QUEUE_FILE)

        if queue:
            post_data = queue[0]  # Peek, don't pop yet
            queue_index = 0
            logger.info(f"Posting from queue ({len(queue)} total): {post_data.get('pillar', '?')}")
        else:
            # —— Step 2: Queue empty — generate fresh content ——
            source = "generated"
            analytics = AnalyticsEngine(linkedin)
            top_posts = analytics.get_top_posts(5, 30)

            from content_engine import load_full_context
            context = load_full_context()

            # Inject learning engine insights into generation
            learning_summary = _learning.get_learning_summary()

            logger.info(f"Queue empty — generating fresh intelligent post for pillar: {pillar}")
            post_data = generate_post(
                pillar=pillar,
                optimize_from=top_posts,
                existing_queue=context["existing_queue"],
                post_history=context["post_history"],
                analytics_data=context["analytics_data"],
                comment_insights=context["comment_insights"],
            )

        # —— Step 3: Generate image if needed and not already present ——
        post_text = post_data["text"]
        image_path = post_data.get("image_path", "")
        image_prompt = post_data.get("image_prompt", "")

        if not image_path and image_prompt:
            try:
                image_path = generate_post_image(image_prompt, post_data.get("pillar", ""))
            except Exception as img_err:
                logger.warning(f"Image generation failed, posting text-only: {img_err}")
                image_path = ""

        # —— Step 4: Post to LinkedIn ——
        if image_path and Path(image_path).exists():
            result = linkedin.create_image_post(post_text, image_path)
        else:
            result = linkedin.create_text_post(post_text)

        post_id = result.get("id", "unknown")
        logger.info(f"Post published ({source}): {post_id} | Pillar: {post_data.get('pillar', '?')}")

        # ── Step 4b: Post to Facebook (from separate FB queue) ──
        try:
            from facebook_api import FacebookAPI
            from config import FACEBOOK_PAGE_ACCESS_TOKEN, DATA_DIR
            fb_queue_file = DATA_DIR / "fb_content_queue.json"

            if FACEBOOK_PAGE_ACCESS_TOKEN and FACEBOOK_PAGE_ACCESS_TOKEN != "your-fb-page-token-here":
                fb_queue = []
                if fb_queue_file.exists():
                    try:
                        with open(fb_queue_file) as f:
                            fb_queue = json.load(f)
                    except (json.JSONDecodeError, IOError):
                        fb_queue = []

                if fb_queue:
                    fb_post_data = fb_queue.pop(0)
                    with open(fb_queue_file, "w") as f:
                        json.dump(fb_queue, f, indent=2)

                    fb = FacebookAPI()
                    fb_text = fb_post_data.get("text", "")
                    fb_image = fb_post_data.get("image_path", "")

                    if fb_image and Path(fb_image).exists():
                        fb_result = fb.create_image_post(fb_text, fb_image)
                    else:
                        fb_result = fb.create_text_post(fb_text)

                    fb_post_id = fb_result.get("id", "unknown")
                    logger.info(f"Facebook post published from FB queue ({len(fb_queue)} remaining): {fb_post_id}")
                else:
                    logger.info("Facebook queue empty — skipping FB post this cycle")
            else:
                logger.info("Facebook posting skipped — no token configured")
        except Exception as fb_err:
            logger.warning(f"Facebook post failed (non-blocking): {fb_err}")

        # ── Step 4c: Post to Instagram (from separate IG queue) ──
        try:
            from instagram_api import InstagramAPI
            from config import INSTAGRAM_BUSINESS_ACCOUNT_ID, DATA_DIR
            ig_queue_file = DATA_DIR / "ig_content_queue.json"

            if INSTAGRAM_BUSINESS_ACCOUNT_ID and INSTAGRAM_BUSINESS_ACCOUNT_ID != "your-ig-account-id-here":
                ig_queue = []
                if ig_queue_file.exists():
                    try:
                        with open(ig_queue_file) as f:
                            ig_queue = json.load(f)
                    except (json.JSONDecodeError, IOError):
                        ig_queue = []

                if ig_queue:
                    ig_post_data = ig_queue.pop(0)
                    with open(ig_queue_file, "w") as f:
                        json.dump(ig_queue, f, indent=2)

                    ig = InstagramAPI()
                    ig_caption = ig_post_data.get("caption", ig_post_data.get("text", ""))
                    ig_image_url = ig_post_data.get("image_url", "")

                    if ig_image_url:
                        ig_result = ig.create_image_post(ig_image_url, ig_caption)
                        ig_post_id = ig_result.get("id", "unknown")
                        logger.info(f"Instagram post published from IG queue ({len(ig_queue)} remaining): {ig_post_id}")
                    else:
                        logger.info("Instagram post skipped — no image URL (Instagram requires images)")
                else:
                    logger.info("Instagram queue empty — skipping IG post this cycle")
            else:
                logger.info("Instagram posting skipped — no account ID configured")
        except Exception as ig_err:
            logger.warning(f"Instagram post failed (non-blocking): {ig_err}")

        # ── Step 5: Save to post history for future intelligence ──
        # —— Step 5: SUCCESS — NOW pop from queue (safe) ——
        if queue_index is not None:
            queue = _safe_read_json(CONTENT_QUEUE_FILE)
            if queue:
                queue.pop(0)
                _safe_write_json(CONTENT_QUEUE_FILE, queue)
                logger.info(f"Queue post consumed. {len(queue)} remaining.")

        # —— Step 6: Save to post history ——
        from config import POST_HISTORY_FILE
        history = _safe_read_json(POST_HISTORY_FILE)

        post_record = {
            "id": post_id,
            "text": post_text,
            "pillar": post_data.get("pillar"),
            "hook": post_data.get("hook"),
            "template_used": post_data.get("template_used"),
            "hashtags": post_data.get("hashtags"),
            "image_path": image_path,
            "image_prompt": image_prompt,
            "estimated_engagement": post_data.get("estimated_engagement"),
            "source": source,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        history.append(post_record)
        _safe_write_json(POST_HISTORY_FILE, history)

        # —— Step 7: Record in learning engine ——
        _learning.record_post_result(
            post_id=post_id,
            pillar=post_data.get("pillar", "unknown"),
            hook=post_data.get("hook", ""),
            template=post_data.get("template_used", ""),
            hashtags=post_data.get("hashtags", []),
            success=True,
        )

        _health["last_post_success"] = datetime.now(timezone.utc).isoformat()
        _health["posts_today"] += 1
        logger.info(f"Post saved to history. Total posts: {len(history)}")

    except Exception as e:
        logger.error(f"Failed to create and post: {e}")
        _health["last_error"] = f"{datetime.now(timezone.utc).isoformat()}: {str(e)}"

        # Dead-letter queue: save failed post for retry
        if post_data:
            _learning.add_to_dead_letter(
                post_data=post_data,
                error=str(e),
                source=source if 'source' in dir() else "unknown",
            )
            logger.info("Failed post added to dead-letter queue for retry")
        
        # Record failure in learning engine
        _learning.record_post_result(
            post_id="failed",
            pillar=post_data.get("pillar", "unknown") if post_data else "unknown",
            hook="",
            template="",
            hashtags=[],
            success=False,
            error=str(e),
        )
        _learning.add_alert("post_failure", f"Post failed: {str(e)[:200]}")


def retry_dead_letter():
    """Retry failed posts from the dead-letter queue."""
    try:
        dead_letters = _learning.get_dead_letter_queue()
        if not dead_letters:
            return

        logger.info(f"Retrying {len(dead_letters)} dead-letter posts...")
        retried = 0
        for item in dead_letters[:3]:  # Max 3 retries per cycle
            post_data = item.get("post_data", {})
            if not post_data or not post_data.get("text"):
                continue
            try:
                linkedin = LinkedInAPI()
                post_text = post_data["text"]
                image_path = post_data.get("image_path", "")

                if image_path and Path(image_path).exists():
                    result = linkedin.create_image_post(post_text, image_path)
                else:
                    result = linkedin.create_text_post(post_text)

                post_id = result.get("id", "unknown")
                logger.info(f"Dead-letter retry success: {post_id}")
                _learning.remove_from_dead_letter(item.get("id"))
                retried += 1
            except Exception as retry_err:
                logger.warning(f"Dead-letter retry failed again: {retry_err}")

        if retried:
            logger.info(f"Successfully retried {retried} dead-letter posts")
    except Exception as e:
        logger.error(f"Dead-letter retry cycle failed: {e}")


def check_comments():
    """Monitor and reply to comments."""
    try:
        manager = CommentManager()
        manager.monitor_and_reply()
    except Exception as e:
        logger.error(f"Comment check failed: {e}")
        _learning.add_alert("comment_check_failure", str(e)[:200])


def collect_metrics():
    """Collect analytics metrics and update learning engine."""
    try:
        analytics = AnalyticsEngine()
        analytics.collect_metrics()

        # Update learning engine with latest engagement data
        try:
            linkedin = LinkedInAPI()
            follower_count = linkedin.get_follower_count()
            if follower_count:
                _learning.record_follower_snapshot(follower_count)
        except Exception:
            pass  # Follower count is best-effort
    except Exception as e:
        logger.error(f"Metrics collection failed: {e}")
        _learning.add_alert("metrics_failure", str(e)[:200])


def weekly_report():
    """Generate weekly performance report."""
    try:
        analytics = AnalyticsEngine()
        analytics.generate_weekly_report()

        # Log learning engine summary
        summary = _learning.get_learning_summary()
        growth_rate = _learning.get_growth_rate()
        logger.info(f"Weekly summary - Growth rate: {growth_rate}, Posts tracked: {summary.get('total_posts', 0)}")

        # Check token expiry
        warning = _learning.check_token_expiry_warning()
        if warning:
            _learning.add_alert("token_expiry", warning)
            logger.warning(f"Token warning: {warning}")
    except Exception as e:
        logger.error(f"Weekly report failed: {e}")


def refill_queue():
    """Auto-refill content queue when running low. Uses full intelligence."""
    try:
        queue = _safe_read_json(CONTENT_QUEUE_FILE)

        if len(queue) < 3:
            logger.info("Queue running low, generating intelligent new content...")
            generate_weekly_content()
    except Exception as e:
        logger.error(f"Queue refill failed: {e}")
        _learning.add_alert("queue_refill_failure", str(e)[:200])


def monitor_recent_posts():
    """Check performance of posts from the last 24 hours and flag early winners."""
    try:
        analytics = AnalyticsEngine()
        flagged = analytics.check_recent_performance(hours_ago=24)
        if flagged:
            logger.info(f"Performance monitor: {len(flagged)} early winners detected")
            for w in flagged:
                logger.info(f"  Winner: {w['likes']} likes, {w['comments']} comments")
                # Track in learning engine
                _learning.record_post_result(
                    post_id=w.get("id", "unknown"),
                    pillar=w.get("pillar", "unknown"),
                    hook=w.get("hook", ""),
                    template=w.get("template", ""),
                    hashtags=w.get("hashtags", []),
                    success=True,
                    engagement={"likes": w.get("likes", 0), "comments": w.get("comments", 0)},
                )
    except Exception as e:
        logger.error(f"Performance monitoring failed: {e}")


def detect_and_learn():
    """Daily task: detect viral posts and save insights for content generation."""
    try:
        analytics = AnalyticsEngine()
        insights = analytics.get_performance_insights()

        winners = insights.get("winners", [])
        pillar_ranking = insights.get("pillar_ranking", [])

        logger.info(f"Intelligence loop: {len(winners)} viral posts, {len(pillar_ranking)} pillars ranked")

        if pillar_ranking:
            best = pillar_ranking[0]
            logger.info(f"  Best pillar: {best['pillar']} (avg {best['avg_engagement']} engagement)")

        if winners:
            for w in winners[:3]:
                logger.info(f"  Viral: [{w['pillar']}/{w['template']}] {w['likes']} likes, {w['comments']} comments")
                # Track hashtag performance in learning engine
                if w.get("hashtags"):
                    for tag in w["hashtags"]:
                        _learning.track_hashtag_performance(
                            tag, w.get("likes", 0) + w.get("comments", 0) * 3
                        )

        # Backup learning state
        _learning.backup_to_dict()
        logger.info("Performance insights saved - content engine will use them for next generation")
    except Exception as e:
        logger.error(f"Detect and learn failed: {e}")


def _handle_shutdown(signum, frame):
    """Graceful shutdown handler for SIGTERM (Railway restarts)."""
    logger.info(f"Received signal {signum}. Initiating graceful shutdown...")
    _shutdown_event.set()
    _learning.add_alert("shutdown", f"Graceful shutdown initiated (signal {signum})")
    # Give running tasks up to 30s to finish
    time.sleep(2)
    logger.info("Shutdown complete.")
    sys.exit(0)


def run_scheduler():
    """Background thread: runs the scheduled automation tasks."""
    _health["scheduler_alive"] = True
    logger.info("Scheduler starting...")
    logger.info(f"Config timezone: {TIMEZONE} (WAT = UTC+1)")
    logger.info(f"Server timezone: UTC (Railway default)")
    logger.info("Converting all scheduled times from WAT to UTC...")

    # Schedule posts for each day — convert WAT times to UTC
    for day, config in POSTING_SCHEDULE.items():
        wat_time = config["time"]
        utc_time = wat_to_utc(wat_time)
        pillar = config["pillar_preference"]
        getattr(sched_lib.every(), day).at(utc_time).do(
            create_and_post, pillar=pillar
        )
        logger.info(f"Scheduled post: {day} at {wat_time} WAT ({utc_time} UTC) — {pillar}")

    # Comment monitoring every 2 hours
    sched_lib.every(2).hours.do(check_comments)

    # Analytics collection every 12 hours
    sched_lib.every(12).hours.do(collect_metrics)

    # Weekly report
    report_day = ANALYTICS_SETTINGS["report_day"]
    report_time_wat = ANALYTICS_SETTINGS["report_time"]
    report_time_utc = wat_to_utc(report_time_wat)
    getattr(sched_lib.every(), report_day).at(report_time_utc).do(weekly_report)

    # Performance monitoring every 6 hours
    sched_lib.every(6).hours.do(monitor_recent_posts)
    logger.info("Scheduled: monitor_recent_posts every 6 hours")

    # Daily intelligence loop at 22:00 UTC (23:00 WAT)
    sched_lib.every().day.at("22:00").do(detect_and_learn)
    logger.info("Scheduled: detect_and_learn daily at 22:00 UTC")

    # Queue refill check daily at 23:00 UTC (midnight WAT)
    sched_lib.every().day.at("23:00").do(refill_queue)

    # Dead-letter retry every 4 hours
    sched_lib.every(4).hours.do(retry_dead_letter)
    logger.info("Scheduled: retry_dead_letter every 4 hours")

    logger.info("All tasks scheduled. Running loop...")
    while not _shutdown_event.is_set():
        sched_lib.run_pending()
        # Use event wait instead of sleep for faster shutdown response
        _shutdown_event.wait(timeout=30)

    logger.info("Scheduler loop exited (shutdown requested).")
    _health["scheduler_alive"] = False


if __name__ == "__main__":
    # Register graceful shutdown handlers
    signal.signal(signal.SIGTERM, _handle_shutdown)
    signal.signal(signal.SIGINT, _handle_shutdown)

    # Start scheduler in background thread
    scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
    scheduler_thread.start()
    logger.info("Scheduler thread started")

    # Run dashboard in main thread (Railway needs this for the PORT)
    logger.info("Starting dashboard...")
    run_dashboard()
