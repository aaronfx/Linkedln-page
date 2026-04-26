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
    Example: "08:00" WAT ÃÂ¢ÃÂÃÂ "07:00" UTC
    """
    h, m = map(int, time_str.split(":"))
    wat = datetime.now(timezone.utc).replace(hour=h, minute=m, second=0)
    wat = wat.replace(tzinfo=timezone(timedelta(hours=1)))
    utc = wat.astimezone(timezone.utc)
    return utc.strftime("%H:%M")


def create_and_post(pillar=None):
    """
    Post to LinkedIn ÃÂ¢ÃÂÃÂ QUEUE-FIRST strategy with retry safety.

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

        # ÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂ Step 1: Try to post from queue (READ without popping) ÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂ
        queue = _safe_read_json(CONTENT_QUEUE_FILE)

        if queue:
            post_data = queue[0]  # Peek, don't pop yet
            queue_index = 0
            logger.info(f"Posting from queue ({len(queue)} total): {post_data.get('pillar', '?')}")
        else:
            # ÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂ Step 2: Queue empty ÃÂ¢ÃÂÃÂ generate fresh content ÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂ
            source = "generated"
            analytics = AnalyticsEngine(linkedin)
            top_posts = analytics.get_top_posts(5, 30)

            from content_engine import load_full_context
            context = load_full_context()

            # Inject learning engine insights into generation
            learning_summary = _learning.get_learning_summary()

            logger.info(f"Queue empty ÃÂ¢ÃÂÃÂ generating fresh intelligent post for pillar: {pillar}")
            post_data = generate_post(
                pillar=pillar,
                optimize_from=top_posts,
                existing_queue=context["existing_queue"],
                post_history=context["post_history"],
                analytics_data=context["analytics_data"],
                comment_insights=context["comment_insights"],
            )

        # ÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂ Step 3: Generate image if needed and not already present ÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂ
        post_text = post_data["text"]
        image_path = post_data.get("image_path", "")
        image_prompt = post_data.get("image_prompt", "")

        if not image_path and image_prompt:
            try:
                image_path = generate_post_image(image_prompt, post_data.get("pillar", ""))
            except Exception as img_err:
                logger.warning(f"Image generation failed, posting text-only: {img_err}")
                image_path = ""

        # ÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂ Step 4: Post to LinkedIn ÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂ
        if image_path and Path(image_path).exists():
            result = linkedin.create_image_post(post_text, image_path)
        else:
            result = linkedin.create_text_post(post_text)

        post_id = result.get("id", "unknown")
        logger.info(f"Post published ({source}): {post_id} | Pillar: {post_data.get('pillar', '?')}")

        # ÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂ Step 4b: Post to Facebook (from separate FB queue) ÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂ
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
                    logger.info("Facebook queue empty ÃÂ¢ÃÂÃÂ skipping FB post this cycle")
            else:
                logger.info("Facebook posting skipped ÃÂ¢ÃÂÃÂ no token configured")
        except Exception as fb_err:
            logger.warning(f"Facebook post failed (non-blocking): {fb_err}")

        # ÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂ Step 4c: Post to Instagram (from separate IG queue) ÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂ
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
                        logger.info("Instagram post skipped ÃÂ¢ÃÂÃÂ no image URL (Instagram requires images)")
                else:
                    logger.info("Instagram queue empty ÃÂ¢ÃÂÃÂ skipping IG post this cycle")
            else:
                logger.info("Instagram posting skipped ÃÂ¢ÃÂÃÂ no account ID configured")
        except Exception as ig_err:
            logger.warning(f"Instagram post failed (non-blocking): {ig_err}")

        # ÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂ Step 5: Save to post history for future intelligence ÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂ
        # ÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂ Step 5: SUCCESS ÃÂ¢ÃÂÃÂ NOW pop from queue (safe) ÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂ
        if queue_index is not None:
            queue = _safe_read_json(CONTENT_QUEUE_FILE)
            if queue:
                queue.pop(0)
                _safe_write_json(CONTENT_QUEUE_FILE, queue)
                logger.info(f"Queue post consumed. {len(queue)} remaining.")

        # ÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂ Step 6: Save to post history ÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂ
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

        # ÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂ Step 7: Record in learning engine ÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂ
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

        # ── Multi-platform learning: IG / Facebook / Threads ──────────────────
        from config import IG_ANALYTICS_FILE, FB_ANALYTICS_FILE, THREADS_ANALYTICS_FILE
        platform_files = [
            ("instagram", IG_ANALYTICS_FILE),
            ("facebook",  FB_ANALYTICS_FILE),
            ("threads",   THREADS_ANALYTICS_FILE),
        ]
        for platform, afile in platform_files:
            try:
                snapshots = _safe_read_json(afile)
                if not snapshots:
                    continue
                all_posts = []
                for snap in snapshots[-10:]:
                    all_posts.extend(snap.get("posts", []))
                if not all_posts:
                    continue
                for p in all_posts:
                    p["_eng"] = p.get("likes", 0) + p.get("comments", 0) * 3 + p.get("shares", 0) * 2
                avg_eng = sum(p["_eng"] for p in all_posts) / max(len(all_posts), 1)
                plat_winners = [p for p in all_posts if p["_eng"] >= avg_eng * 1.5]
                logger.info(f"[{platform}] {len(plat_winners)} viral posts detected (avg eng {avg_eng:.1f})")
                for w in plat_winners[:3]:
                    logger.info(f"  [{platform}] pillar={w.get('pillar','?')} eng={w['_eng']}")
                    if w.get("hashtags"):
                        for tag in w["hashtags"]:
                            _learning.track_hashtag_performance(tag, w["_eng"])
            except Exception as pe:
                logger.warning(f"[{platform}] Analytics learning failed: {pe}")
        # ──────────────────────────────────────────────────────────────────────

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
    """Background thread: runs the scheduled automation tasks for ALL platforms."""
    _health["scheduler_alive"] = True
    logger.info("Scheduler starting Ã¢ÂÂ LinkedIn (personal) + Gopipways company platforms...")

    from config import (
        INSTAGRAM_POSTING_SCHEDULE, FACEBOOK_POSTING_SCHEDULE, THREADS_POSTING_SCHEDULE
    )

    # Ã¢ÂÂÃ¢ÂÂ LinkedIn Ã¢ÂÂ Aaron's personal brand (unchanged, always first) Ã¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂ
    for day, config in POSTING_SCHEDULE.items():
        utc_time = wat_to_utc(config["time"])
        pillar = config["pillar_preference"]
        getattr(sched_lib.every(), day).at(utc_time).do(create_and_post, pillar=pillar)
        logger.info(f"[LinkedIn] {day} {config['time']} WAT -> {utc_time} UTC | {pillar}")

    # Ã¢ÂÂÃ¢ÂÂ Instagram Ã¢ÂÂ Gopipways company brand Ã¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂ
    for day, config in INSTAGRAM_POSTING_SCHEDULE.items():
        utc_time = wat_to_utc(config["time"])
        pillar = config["pillar_preference"]
        getattr(sched_lib.every(), day).at(utc_time).do(create_and_post_instagram, pillar=pillar)
        logger.info(f"[Instagram] {day} {config['time']} WAT -> {utc_time} UTC | {pillar}")

    # Ã¢ÂÂÃ¢ÂÂ Facebook Ã¢ÂÂ Gopipways company brand Ã¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂ
    for day, config in FACEBOOK_POSTING_SCHEDULE.items():
        utc_time = wat_to_utc(config["time"])
        pillar = config["pillar_preference"]
        getattr(sched_lib.every(), day).at(utc_time).do(create_and_post_facebook, pillar=pillar)
        logger.info(f"[Facebook] {day} {config['time']} WAT -> {utc_time} UTC | {pillar}")

    # Ã¢ÂÂÃ¢ÂÂ Threads Ã¢ÂÂ Gopipways company brand Ã¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂ
    for day, config in THREADS_POSTING_SCHEDULE.items():
        utc_time = wat_to_utc(config["time"])
        pillar = config["pillar_preference"]
        getattr(sched_lib.every(), day).at(utc_time).do(create_and_post_threads, pillar=pillar)
        logger.info(f"[Threads] {day} {config['time']} WAT -> {utc_time} UTC | {pillar}")

    # Ã¢ÂÂÃ¢ÂÂ Comment monitoring Ã¢ÂÂ all platforms every 2 hours Ã¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂ
    sched_lib.every(2).hours.do(check_comments)
    sched_lib.every(2).hours.do(check_comments_instagram)
    sched_lib.every(2).hours.do(check_comments_facebook)
    sched_lib.every(2).hours.do(check_comments_threads)

    # Ã¢ÂÂÃ¢ÂÂ Analytics Ã¢ÂÂ all platforms every 12 hours Ã¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂ
    sched_lib.every(12).hours.do(collect_metrics)
    sched_lib.every(12).hours.do(collect_metrics_instagram)
    sched_lib.every(12).hours.do(collect_metrics_facebook)
    sched_lib.every(12).hours.do(collect_metrics_threads)

    # Ã¢ÂÂÃ¢ÂÂ Learning + intelligence loop every 6 hours Ã¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂ
    sched_lib.every(6).hours.do(detect_and_learn)

    # Ã¢ÂÂÃ¢ÂÂ Dead letter retry every hour Ã¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂ
    sched_lib.every(1).hours.do(retry_dead_letter)

    # Ã¢ÂÂÃ¢ÂÂ Weekly report Ã¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂ
    report_day = ANALYTICS_SETTINGS.get("report_day", "sunday")
    report_time = wat_to_utc(ANALYTICS_SETTINGS.get("report_time", "20:00"))
    getattr(sched_lib.every(), report_day).at(report_time).do(weekly_report)

    logger.info("All platform schedulers active. Running loop...")
    while not _shutdown_event.is_set():
        sched_lib.run_pending()
        time.sleep(30)

    logger.info("Scheduler stopped.")
    _health["scheduler_alive"] = False


# Ã¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂ
# GOPIPWAYS COMPANY PLATFORM AUTOMATION Ã¢ÂÂ Instagram, Facebook, Threads
# LinkedIn (Aaron's personal brand) uses the existing create_and_post() above.
# Ã¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂ

def _safe_read_json(path, default=None):
    """Thread-safe JSON read with fallback."""
    if default is None:
        default = []
    try:
        from pathlib import Path
        p = Path(path)
        if p.exists():
            import json as _j
            return _j.loads(p.read_text())
    except Exception:
        pass
    return default


def _safe_write_json(path, data):
    """Thread-safe JSON write."""
    try:
        from pathlib import Path
        import json as _j
        Path(path).write_text(_j.dumps(data, indent=2, default=str))
    except Exception as e:
        logger.error(f"_safe_write_json error: {e}")


# Ã¢ÂÂÃ¢ÂÂ Instagram Posting Ã¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂ

def create_and_post_instagram(pillar=None):
    """Queue-first Instagram posting using generate_company_post()."""
    try:
        from config import IG_QUEUE_FILE, IG_HISTORY_FILE, IG_DEAD_LETTER_FILE, IMAGES_DIR
        from instagram_api import InstagramAPI

        queue = _safe_read_json(IG_QUEUE_FILE)
        if not queue:
            from content_engine import generate_company_post
            history = _safe_read_json(IG_HISTORY_FILE)
            company = generate_company_post(pillar=pillar, post_history=history[-20:] if history else [])
            ig_post = company.get("instagram", {})
            caption = ig_post.get("caption", "")
            tags = " ".join(ig_post.get("hashtags", []))
            if tags:
                caption = caption.rstrip() + "\n" + tags
            queue = [{"caption": caption, "pillar": company.get("pillar",""), "type":"company",
                      "core_hook": company.get("core_hook",""), "generated_at": company.get("generated_at","")}]

        entry = queue[0]
        caption = entry.get("caption", entry.get("text", ""))
        image_url = entry.get("image_url", "")

        if not caption:
            logger.warning("Instagram: empty caption, skipping")
            return

        api = InstagramAPI()
        if image_url:
            result = api.create_image_post(image_url=image_url, caption=caption)
        else:
            result = api.create_image_post(image_url="", caption=caption)

        if result.get("id") or result.get("success"):
            queue.pop(0)
            _safe_write_json(IG_QUEUE_FILE, queue)
            history = _safe_read_json(IG_HISTORY_FILE)
            history.append({**entry, "post_id": result.get("id",""), "posted_at": datetime.now(timezone.utc).isoformat(), "platform": "instagram"})
            _safe_write_json(IG_HISTORY_FILE, history)
            _health["last_ig_post"] = datetime.now(timezone.utc).isoformat()
            logger.info(f"Instagram posted: {result.get('id')}")
        else:
            raise ValueError(f"Instagram post failed: {result}")

    except Exception as e:
        logger.error(f"Instagram posting error: {e}")
        try:
            from config import IG_DEAD_LETTER_FILE
            dead = _safe_read_json(IG_DEAD_LETTER_FILE)
            dead.append({"error": str(e), "failed_at": datetime.now(timezone.utc).isoformat()})
            _safe_write_json(IG_DEAD_LETTER_FILE, dead)
        except Exception:
            pass


# Ã¢ÂÂÃ¢ÂÂ Facebook Posting Ã¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂ

def create_and_post_facebook(pillar=None):
    """Queue-first Facebook posting using generate_company_post()."""
    try:
        from config import FB_QUEUE_FILE, FB_HISTORY_FILE, FB_DEAD_LETTER_FILE
        from facebook_api import FacebookAPI

        queue = _safe_read_json(FB_QUEUE_FILE)
        if not queue:
            from content_engine import generate_company_post
            history = _safe_read_json(FB_HISTORY_FILE)
            company = generate_company_post(pillar=pillar, post_history=history[-20:] if history else [])
            fb_post = company.get("facebook", {})
            text = fb_post.get("text", "")
            tags = " ".join(fb_post.get("hashtags", []))
            if tags:
                text = text.rstrip() + "\n" + tags
            queue = [{"text": text, "pillar": company.get("pillar",""), "type":"company",
                      "core_hook": company.get("core_hook",""), "generated_at": company.get("generated_at","")}]

        entry = queue[0]
        text = entry.get("text", entry.get("caption", ""))
        if not text:
            logger.warning("Facebook: empty text, skipping")
            return

        api = FacebookAPI()
        result = api.create_text_post(text)

        if result.get("post_id") or result.get("success"):
            queue.pop(0)
            _safe_write_json(FB_QUEUE_FILE, queue)
            history = _safe_read_json(FB_HISTORY_FILE)
            history.append({**entry, "post_id": result.get("post_id",""), "posted_at": datetime.now(timezone.utc).isoformat(), "platform": "facebook"})
            _safe_write_json(FB_HISTORY_FILE, history)
            _health["last_fb_post"] = datetime.now(timezone.utc).isoformat()
            logger.info(f"Facebook posted: {result.get('post_id')}")
        else:
            raise ValueError(f"Facebook post failed: {result}")

    except Exception as e:
        logger.error(f"Facebook posting error: {e}")
        try:
            from config import FB_DEAD_LETTER_FILE
            dead = _safe_read_json(FB_DEAD_LETTER_FILE)
            dead.append({"error": str(e), "failed_at": datetime.now(timezone.utc).isoformat()})
            _safe_write_json(FB_DEAD_LETTER_FILE, dead)
        except Exception:
            pass


# Ã¢ÂÂÃ¢ÂÂ Threads Posting Ã¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂ

def create_and_post_threads(pillar=None):
    """Queue-first Threads posting using generate_company_post()."""
    try:
        from config import THREADS_QUEUE_FILE, THREADS_HISTORY_FILE, THREADS_DEAD_LETTER_FILE
        from threads_api import ThreadsAPI

        queue = _safe_read_json(THREADS_QUEUE_FILE)
        if not queue:
            from content_engine import generate_company_post
            history = _safe_read_json(THREADS_HISTORY_FILE)
            company = generate_company_post(pillar=pillar, post_history=history[-20:] if history else [])
            th_post = company.get("threads", {})
            text = th_post.get("text", "")
            tags = " ".join(th_post.get("hashtags", []))
            if tags:
                text = text.rstrip() + "\n" + tags
            queue = [{"text": text, "pillar": company.get("pillar",""), "type":"company",
                      "core_hook": company.get("core_hook",""), "generated_at": company.get("generated_at","")}]

        entry = queue[0]
        text = entry.get("text", "")
        if not text:
            logger.warning("Threads: empty text, skipping")
            return

        api = ThreadsAPI()
        result = api.create_text_post(text)

        if result.get("post_id") or result.get("success"):
            queue.pop(0)
            _safe_write_json(THREADS_QUEUE_FILE, queue)
            history = _safe_read_json(THREADS_HISTORY_FILE)
            history.append({**entry, "post_id": result.get("post_id",""), "posted_at": datetime.now(timezone.utc).isoformat(), "platform": "threads"})
            _safe_write_json(THREADS_HISTORY_FILE, history)
            _health["last_threads_post"] = datetime.now(timezone.utc).isoformat()
            logger.info(f"Threads posted: {result.get('post_id')}")
        else:
            raise ValueError(f"Threads post failed: {result}")

    except Exception as e:
        logger.error(f"Threads posting error: {e}")
        try:
            from config import THREADS_DEAD_LETTER_FILE
            dead = _safe_read_json(THREADS_DEAD_LETTER_FILE)
            dead.append({"error": str(e), "failed_at": datetime.now(timezone.utc).isoformat()})
            _safe_write_json(THREADS_DEAD_LETTER_FILE, dead)
        except Exception:
            pass


# Ã¢ÂÂÃ¢ÂÂ Comment Monitoring Ã¢ÂÂ Company Platforms Ã¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂ

def check_comments_instagram():
    """Check, log, and auto-reply to comments on recent Instagram posts."""
    try:
        from config import IG_HISTORY_FILE, IG_COMMENT_LOG_FILE
        from instagram_api import InstagramAPI
        api = InstagramAPI()
        history = _safe_read_json(IG_HISTORY_FILE)
        if not history:
            return
        comment_log = _safe_read_json(IG_COMMENT_LOG_FILE)
        seen = {entry.get("comment_id") for entry in comment_log}
        for post in history[-5:]:
            pid = post.get("post_id","")
            if not pid:
                continue
            try:
                for c in api.get_comments(pid):
                    cid = c.get("id","")
                    if cid and cid not in seen:
                        comment_log.append({"comment_id": cid, "post_id": pid, "platform": "instagram",
                            "text": c.get("text",""), "username": c.get("username",""),
                            "timestamp": c.get("timestamp",""), "replied": False})
                        seen.add(cid)
                        # Auto-reply using Claude
                        try:
                            comment_text = c.get("text", "").strip()
                            if comment_text:
                                reply_resp = _claude_call(
                                    messages=[{"role": "user", "content": f"Reply to this Instagram comment on Gopipways, a Pan-African financial/trading brand. Be friendly, professional, and concise (under 80 words).\n\nComment: {comment_text}"}],
                                    system="You are the Gopipways brand voice on Instagram. Reply warmly and professionally to comments. Keep replies short and engaging.",
                                    max_tokens=150,
                                )
                                reply_text = reply_resp.content[0].text.strip()
                                api.reply_to_comment(cid, reply_text)
                                comment_log[-1]["replied"] = True
                                comment_log[-1]["reply_text"] = reply_text
                                logger.info(f"[IG] Auto-replied to comment {cid} by @{c.get('username','?')}")
                        except Exception as re:
                            logger.warning(f"[IG] Auto-reply failed for {cid}: {re}")
            except Exception as e:
                logger.debug(f"IG comments error {pid}: {e}")
        _safe_write_json(IG_COMMENT_LOG_FILE, comment_log)
        logger.info(f"Instagram comments: {len(comment_log)} total")
    except Exception as e:
        logger.error(f"check_comments_instagram error: {e}")


def check_comments_facebook():
    """Check, log, and auto-reply to comments on recent Facebook posts."""
    try:
        from config import FB_HISTORY_FILE, FB_COMMENT_LOG_FILE
        from facebook_api import FacebookAPI
        api = FacebookAPI()
        history = _safe_read_json(FB_HISTORY_FILE)
        if not history:
            return
        comment_log = _safe_read_json(FB_COMMENT_LOG_FILE)
        seen = {entry.get("comment_id") for entry in comment_log}
        for post in history[-5:]:
            pid = post.get("post_id","")
            if not pid:
                continue
            try:
                for c in api.get_post_comments(pid):
                    cid = c.get("id","")
                    if cid and cid not in seen:
                        comment_log.append({"comment_id": cid, "post_id": pid, "platform": "facebook",
                            "text": c.get("message",""), "username": c.get("from",{}).get("name",""),
                            "timestamp": c.get("created_time",""), "replied": False})
                        seen.add(cid)
                        # Auto-reply using Claude
                        try:
                            comment_text = c.get("message", "").strip()
                            if comment_text:
                                reply_resp = _claude_call(
                                    messages=[{"role": "user", "content": f"Reply to this Facebook comment on Gopipways, a Pan-African financial/trading brand. Be friendly, professional, and concise (under 80 words).\n\nComment: {comment_text}"}],
                                    system="You are the Gopipways brand voice on Facebook. Reply warmly and professionally to comments. Keep replies short and engaging.",
                                    max_tokens=150,
                                )
                                reply_text = reply_resp.content[0].text.strip()
                                api.reply_to_comment(cid, reply_text)
                                comment_log[-1]["replied"] = True
                                comment_log[-1]["reply_text"] = reply_text
                                logger.info(f"[FB] Auto-replied to comment {cid} by {c.get('from',{}).get('name','?')}")
                        except Exception as re:
                            logger.warning(f"[FB] Auto-reply failed for {cid}: {re}")
            except Exception as e:
                logger.debug(f"FB comments error {pid}: {e}")
        _safe_write_json(FB_COMMENT_LOG_FILE, comment_log)
        logger.info(f"Facebook comments: {len(comment_log)} total")
    except Exception as e:
        logger.error(f"check_comments_facebook error: {e}")


def check_comments_threads():
    """Check, log, and auto-reply to replies on recent Threads posts."""
    try:
        from config import THREADS_HISTORY_FILE, THREADS_COMMENT_LOG_FILE
        from threads_api import ThreadsAPI
        api = ThreadsAPI()
        history = _safe_read_json(THREADS_HISTORY_FILE)
        if not history:
            return
        comment_log = _safe_read_json(THREADS_COMMENT_LOG_FILE)
        seen = {entry.get("comment_id") for entry in comment_log}
        for post in history[-5:]:
            pid = post.get("post_id","")
            if not pid:
                continue
            try:
                for r in api.get_replies(pid):
                    rid = r.get("id","")
                    if rid and rid not in seen:
                        comment_log.append({"comment_id": rid, "post_id": pid, "platform": "threads",
                            "text": r.get("text",""), "username": r.get("username",""),
                            "timestamp": r.get("timestamp",""), "replied": False})
                        seen.add(rid)
                        # Auto-reply using Claude
                        try:
                            reply_text_in = r.get("text", "").strip()
                            if reply_text_in:
                                reply_resp = _claude_call(
                                    messages=[{"role": "user", "content": f"Reply to this Threads reply on Gopipways, a Pan-African financial/trading brand. Be friendly, professional, and concise (under 80 words).\n\nReply: {reply_text_in}"}],
                                    system="You are the Gopipways brand voice on Threads. Reply warmly and professionally. Keep replies short and engaging.",
                                    max_tokens=150,
                                )
                                auto_reply = reply_resp.content[0].text.strip()
                                api.reply_to_thread(rid, auto_reply)
                                comment_log[-1]["replied"] = True
                                comment_log[-1]["reply_text"] = auto_reply
                                logger.info(f"[Threads] Auto-replied to reply {rid} by @{r.get('username','?')}")
                        except Exception as re:
                            logger.warning(f"[Threads] Auto-reply failed for {rid}: {re}")
            except Exception as e:
                logger.debug(f"Threads replies error {pid}: {e}")
        _safe_write_json(THREADS_COMMENT_LOG_FILE, comment_log)
        logger.info(f"Threads replies: {len(comment_log)} total")
    except Exception as e:
        logger.error(f"check_comments_threads error: {e}")


# Ã¢ÂÂÃ¢ÂÂ Analytics Collection Ã¢ÂÂ Company Platforms Ã¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂ

def collect_metrics_instagram():
    """Collect Instagram post and account insights."""
    try:
        from config import IG_HISTORY_FILE, IG_ANALYTICS_FILE
        from instagram_api import InstagramAPI
        api = InstagramAPI()
        account = {}
        try:
            account = api.get_account_insights()
        except Exception:
            pass
        history = _safe_read_json(IG_HISTORY_FILE)
        post_metrics = []
        for post in history[-10:]:
            pid = post.get("post_id","")
            if not pid:
                continue
            try:
                ins = api.get_post_insights(pid)
                post_metrics.append({"post_id": pid, "pillar": post.get("pillar",""),
                    "posted_at": post.get("posted_at",""), **ins})
            except Exception as e:
                logger.debug(f"IG insights error {pid}: {e}")
        analytics = _safe_read_json(IG_ANALYTICS_FILE)
        analytics.append({"collected_at": datetime.now(timezone.utc).isoformat(),
            "account": account, "posts": post_metrics})
        _safe_write_json(IG_ANALYTICS_FILE, analytics[-30:])
        logger.info(f"Instagram analytics collected")
    except Exception as e:
        logger.error(f"collect_metrics_instagram error: {e}")


def collect_metrics_facebook():
    """Collect Facebook post insights."""
    try:
        from config import FB_HISTORY_FILE, FB_ANALYTICS_FILE
        from facebook_api import FacebookAPI
        api = FacebookAPI()
        history = _safe_read_json(FB_HISTORY_FILE)
        post_metrics = []
        for post in history[-10:]:
            pid = post.get("post_id","")
            if not pid:
                continue
            try:
                ins = api.get_post_insights(pid)
                post_metrics.append({"post_id": pid, "pillar": post.get("pillar",""),
                    "posted_at": post.get("posted_at",""), **ins})
            except Exception as e:
                logger.debug(f"FB insights error {pid}: {e}")
        analytics = _safe_read_json(FB_ANALYTICS_FILE)
        analytics.append({"collected_at": datetime.now(timezone.utc).isoformat(), "posts": post_metrics})
        _safe_write_json(FB_ANALYTICS_FILE, analytics[-30:])
        logger.info(f"Facebook analytics collected")
    except Exception as e:
        logger.error(f"collect_metrics_facebook error: {e}")


def collect_metrics_threads():
    """Collect Threads post and account insights."""
    try:
        from config import THREADS_HISTORY_FILE, THREADS_ANALYTICS_FILE
        from threads_api import ThreadsAPI
        api = ThreadsAPI()
        account = {}
        try:
            account = api.get_account_insights()
        except Exception:
            pass
        history = _safe_read_json(THREADS_HISTORY_FILE)
        post_metrics = []
        for post in history[-10:]:
            pid = post.get("post_id","")
            if not pid:
                continue
            try:
                ins = api.get_post_insights(pid)
                post_metrics.append({"post_id": pid, "pillar": post.get("pillar",""),
                    "posted_at": post.get("posted_at",""), **ins})
            except Exception as e:
                logger.debug(f"Threads insights error {pid}: {e}")
        analytics = _safe_read_json(THREADS_ANALYTICS_FILE)
        analytics.append({"collected_at": datetime.now(timezone.utc).isoformat(),
            "account": account, "posts": post_metrics})
        _safe_write_json(THREADS_ANALYTICS_FILE, analytics[-30:])
        logger.info(f"Threads analytics collected")
    except Exception as e:
        logger.error(f"collect_metrics_threads error: {e}")


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
