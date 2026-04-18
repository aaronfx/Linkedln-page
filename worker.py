"""
Worker Process
===============
Runs the automation scheduler in a background thread
alongside the Flask dashboard. Designed for Railway deployment.
"""

import threading
import time
import logging
import schedule as sched_lib
from datetime import datetime, timezone

from config import POSTING_SCHEDULE, ANALYTICS_SETTINGS, CONTENT_QUEUE_FILE
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


def create_and_post(pillar=None):
    """Generate content + image and post to LinkedIn."""
    try:
        linkedin = LinkedInAPI()
        analytics = AnalyticsEngine(linkedin)
        top_posts = analytics.get_top_posts(5, 30)

        logger.info(f"Generating post for pillar: {pillar}")
        post_data = generate_post(pillar=pillar, optimize_from=top_posts)
        post_text = post_data["text"]

        # Generate image
        image_path = ""
        image_prompt = post_data.get("image_prompt", "")
        if image_prompt:
            image_path = generate_post_image(image_prompt, post_data.get("pillar", ""))

        # Post to LinkedIn
        from pathlib import Path
        if image_path and Path(image_path).exists():
            result = linkedin.create_image_post(post_text, image_path)
        else:
            result = linkedin.create_text_post(post_text)

        logger.info(f"Post published: {result.get('id')}")
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
    """Auto-refill content queue when running low."""
    try:
        import json
        queue = []
        if CONTENT_QUEUE_FILE.exists():
            with open(CONTENT_QUEUE_FILE) as f:
                queue = json.load(f)

        if len(queue) < 3:
            logger.info("Queue running low, generating new content...")
            analytics = AnalyticsEngine()
            top_posts = analytics.get_top_posts(5, 30)
            generate_weekly_content(optimize_from=top_posts)
    except Exception as e:
        logger.error(f"Queue refill failed: {e}")


def run_scheduler():
    """Background thread: runs the scheduled automation tasks."""
    logger.info("Scheduler starting...")

    # Schedule posts for each day
    for day, config in POSTING_SCHEDULE.items():
        post_time = config["time"]
        pillar = config["pillar_preference"]
        getattr(sched_lib.every(), day).at(post_time).do(
            create_and_post, pillar=pillar
        )
        logger.info(f"Scheduled post: {day} at {post_time} — {pillar}")

    # Comment monitoring every 30 minutes
    sched_lib.every(30).minutes.do(check_comments)

    # Analytics collection every 6 hours
    sched_lib.every(ANALYTICS_SETTINGS["track_interval_hours"]).hours.do(collect_metrics)

    # Weekly report
    report_day = ANALYTICS_SETTINGS["report_day"]
    report_time = ANALYTICS_SETTINGS["report_time"]
    getattr(sched_lib.every(), report_day).at(report_time).do(weekly_report)

    # Queue refill check daily at midnight
    sched_lib.every().day.at("00:00").do(refill_queue)

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
