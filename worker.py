"""
Worker Process
===============
Runs the automation scheduler in a background thread
alongside the Flask dashboard. Designed for Railway deployment.

Timezone handling: Railway runs in UTC. All scheduled times in config
are WAT (UTC+1), so we convert them to UTC for the schedule library.
"""

import os
import threading
import time
import logging
import schedule as sched_lib
from datetime import datetime, timezone, timedelta

from config import POSTING_SCHEDULE, ANALYTICS_SETTINGS, CONTENT_QUEUE_FILE, TIMEZONE
from linkedin_api import LinkedInAPI
from content_engine import generate_post, generate_weekly_content
from image_generator import generate_post_image
from analytics_engine import AnalyticsEngine
from comment_manager import CommentManager
from dashboard import app, run_dashboard

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("worker")


def wat_to_utc(time_str):
    """
    Convert a WAT time string (HH:MM) to UTC (HH:MM).
    WAT is UTC+1, so we subtract 1 hour.
    Handles day wraparound (e.g., 00:30 WAT -> 23:30 UTC previous day).
    """
    hour, minute = map(int, time_str.split(":"))
    utc_hour = (hour - 1) % 24
    return f"{utc_hour:02d}:{minute:02d}"


def create_and_post(pillar=None):
    """
    Post to LinkedIn — QUEUE-FIRST strategy.

    1. If the content queue has posts, pop the next one and post it.
    2. If the queue is empty, generate a fresh intelligent post on the fly.

    This means "Generate Week" on the dashboard pre-loads the queue,
    and the scheduler faithfully posts that pre-approved content.
    """
    try:
        import json
        from pathlib import Path

        linkedin = LinkedInAPI()
        post_data = None
        source = "queue"

        # ── Step 1: Try to post from queue ──
        queue = []
        if CONTENT_QUEUE_FILE.exists():
            try:
                with open(CONTENT_QUEUE_FILE) as f:
                    queue = json.load(f)
            except (json.JSONDecodeError, IOError):
                queue = []

        if queue:
            # Pop the first post from the queue
            post_data = queue.pop(0)

            # Save the remaining queue
            with open(CONTENT_QUEUE_FILE, "w") as f:
                json.dump(queue, f, indent=2)

            logger.info(f"Posting from queue ({len(queue)} remaining): {post_data.get('pillar', '?')}")
        else:
            # ── Step 2: Queue empty — generate fresh content ──
            source = "generated"
            analytics = AnalyticsEngine(linkedin)
            top_posts = analytics.get_top_posts(5, 30)

            from content_engine import load_full_context
            context = load_full_context()

            logger.info(f"Queue empty — generating fresh intelligent post for pillar: {pillar}")
            post_data = generate_post(
                pillar=pillar,
                optimize_from=top_posts,
                existing_queue=context["existing_queue"],
                post_history=context["post_history"],
                analytics_data=context["analytics_data"],
                comment_insights=context["comment_insights"],
            )

        # ── Step 3: Generate image if needed and not already present ──
        post_text = post_data["text"]
        image_path = post_data.get("image_path", "")
        image_prompt = post_data.get("image_prompt", "")

        if not image_path and image_prompt:
            try:
                image_path = generate_post_image(image_prompt, post_data.get("pillar", ""))
            except Exception as img_err:
                logger.warning(f"Image generation failed, posting text-only: {img_err}")
                image_path = ""

        # ── Step 4: Post to LinkedIn ──
        if image_path and Path(image_path).exists():
            result = linkedin.create_image_post(post_text, image_path)
        else:
            result = linkedin.create_text_post(post_text)

        post_id = result.get("id", "unknown")
        logger.info(f"Post published ({source}): {post_id} | Pillar: {post_data.get('pillar', '?')}")

        # ── Step 5: Save to post history for future intelligence ──
        from config import POST_HISTORY_FILE
        history = []
        if POST_HISTORY_FILE.exists():
            try:
                with open(POST_HISTORY_FILE) as f:
                    history = json.load(f)
            except (json.JSONDecodeError, IOError):
                history = []

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
        with open(POST_HISTORY_FILE, "w") as f:
            json.dump(history, f, indent=2, default=str)

        logger.info(f"Post saved to history. Total posts: {len(history)}")

    except Exception as e:
        logger.error(f"Failed to create and post: {e}")


def check_comments():
    """Monitor and reply to comments."""
    try:
        manager = CommentManager()
        manager.monitor_and_reply()
    except Exception as e:
        logger.error(f"Comment check failed: {e}")


def collect_metrics():
    """Collect analytics metrics."""
    try:
        analytics = AnalyticsEngine()
        analytics.collect_metrics()
    except Exception as e:
        logger.error(f"Metrics collection failed: {e}")


def weekly_report():
    """Generate weekly performance report."""
    try:
        analytics = AnalyticsEngine()
        analytics.generate_weekly_report()
    except Exception as e:
        logger.error(f"Weekly report failed: {e}")


def refill_queue():
    """Auto-refill content queue when running low. Uses full intelligence."""
    try:
        import json
        queue = []
        if CONTENT_QUEUE_FILE.exists():
            with open(CONTENT_QUEUE_FILE) as f:
                queue = json.load(f)

        if len(queue) < 3:
            logger.info("Queue running low, generating intelligent new content...")
            # generate_weekly_content now handles all context loading internally
            generate_weekly_content()
    except Exception as e:
        logger.error(f"Queue refill failed: {e}")


def run_scheduler():
    """Background thread: runs the scheduled automation tasks."""
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

    # Comment monitoring every 30 minutes
    sched_lib.every(30).minutes.do(check_comments)

    # Analytics collection every 6 hours
    sched_lib.every(ANALYTICS_SETTINGS["track_interval_hours"]).hours.do(collect_metrics)

    # Weekly report — also convert to UTC
    report_day = ANALYTICS_SETTINGS["report_day"]
    report_time_wat = ANALYTICS_SETTINGS["report_time"]
    report_time_utc = wat_to_utc(report_time_wat)
    getattr(sched_lib.every(), report_day).at(report_time_utc).do(weekly_report)

    # Queue refill check daily at midnight WAT (23:00 UTC)
    sched_lib.every().day.at("23:00").do(refill_queue)

    logger.info("All tasks scheduled. Running loop...")
    while True:
        sched_lib.run_pending()
        time.sleep(30)


if __name__ == "__main__":
    # Start scheduler in background thread
    scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
    scheduler_thread.start()
    logger.info("Scheduler thread started")

    # Run dashboard in main thread (Railway needs this for the PORT)
    logger.info("Starting dashboard...")
    run_dashboard()
