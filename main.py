#!/usr/bin/env python3
"""
LinkedIn Automation Agent — Main Runner
========================================
Orchestrates all automation modules:
  - Content generation (Claude)
  - Image generation (OpenAI DALL-E)
  - Auto-posting to LinkedIn
  - Comment monitoring & auto-reply
  - Analytics tracking & optimization

Usage:
  python main.py run          # Full automation loop (runs continuously)
  python main.py post         # Generate and post one piece of content now
  python main.py generate     # Generate a week of content (no posting)
  python main.py comments     # Monitor and reply to comments
  python main.py analytics    # Collect metrics and generate report
  python main.py setup        # Interactive setup and auth
  python main.py test         # Test all connections
"""

import sys
import time
import json
import logging
import argparse
import schedule as sched_lib
from datetime import datetime, timezone
from pathlib import Path

# Local modules
from config import (
    POSTING_SCHEDULE, TIMEZONE, ANALYTICS_SETTINGS,
    CONTENT_QUEUE_FILE, POST_HISTORY_FILE, LOGS_DIR
)
from linkedin_api import LinkedInAPI
from content_engine import generate_post, generate_weekly_content, analyze_performance
from image_generator import generate_post_image
from analytics_engine import AnalyticsEngine
from comment_manager import CommentManager

# ─── Logging Setup ──────────────────────────────────────────

log_file = LOGS_DIR / f"automation_{datetime.now().strftime('%Y%m%d')}.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("main")


# ─── Core Functions ─────────────────────────────────────────

def create_and_post(pillar: str = None, topic_hint: str = None):
    """Generate content + image and post to LinkedIn with full intelligence."""
    linkedin = LinkedInAPI()
    analytics = AnalyticsEngine(linkedin)

    # Get top posts for optimization
    top_posts = analytics.get_top_posts(5, 30)

    # Load full context for intelligent generation
    from content_engine import load_full_context
    context = load_full_context()

    # Step 1: Generate post content with Claude (fully context-aware)
    logger.info("Generating intelligent post content with Claude...")
    post_data = generate_post(
        pillar=pillar,
        topic_hint=topic_hint,
        optimize_from=top_posts,
        existing_queue=context["existing_queue"],
        post_history=context["post_history"],
        analytics_data=context["analytics_data"],
        comment_insights=context["comment_insights"],
    )

    post_text = post_data["text"]
    image_prompt = post_data.get("image_prompt", "")

    # Step 2: Generate image with DALL-E
    image_path = ""
    if image_prompt:
        logger.info("Generating image with DALL-E...")
        image_path = generate_post_image(
            image_prompt=image_prompt,
            pillar=post_data.get("pillar", ""),
        )

    # Step 3: Post to LinkedIn
    logger.info("Posting to LinkedIn...")
    if image_path and Path(image_path).exists():
        result = linkedin.create_image_post(post_text, image_path)
    else:
        result = linkedin.create_text_post(post_text)

    logger.info(f"Post published successfully! ID: {result.get('id')}")

    # Log the full post data
    post_record = {
        "id": result.get("id"),
        "text": post_text,
        "pillar": post_data.get("pillar"),
        "image_path": image_path,
        "image_prompt": image_prompt,
        "hook": post_data.get("hook"),
        "hashtags": post_data.get("hashtags"),
        "estimated_engagement": post_data.get("estimated_engagement"),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    return post_record


def generate_content_only():
    """Generate a week of content without posting (for review). Fully intelligent."""
    logger.info("Generating intelligent weekly content...")
    # generate_weekly_content now loads ALL context internally
    # (queue, history, analytics, comments) for duplicate-free, optimized content
    posts = generate_weekly_content()

    # Also generate images for all posts
    logger.info("Generating images for all posts...")
    for post in posts:
        image_prompt = post.get("image_prompt", "")
        if image_prompt:
            image_path = generate_post_image(
                image_prompt=image_prompt,
                pillar=post.get("pillar", ""),
            )
            post["image_path"] = image_path

    logger.info(f"Generated {len(posts)} intelligent posts.")
    print(f"\n{'='*60}")
    print(f"  WEEKLY CONTENT GENERATED — {len(posts)} posts ready")
    print(f"{'='*60}")
    for post in posts:
        print(f"\n  [{post.get('scheduled_day', '?').upper()}] {post.get('pillar', '')}")
        print(f"  Hook: {post.get('hook', post.get('text', '')[:100])}")
        print(f"  Image: {'Yes' if post.get('image_path') else 'No'}")
    print(f"\n  Review at: {CONTENT_QUEUE_FILE}")
    print(f"{'='*60}\n")

    return posts


def run_comment_monitor():
    """Run comment monitoring and auto-reply."""
    logger.info("Starting comment monitor...")
    manager = CommentManager()
    manager.monitor_and_reply()
    logger.info("Comment monitoring complete")


def run_analytics():
    """Collect metrics and generate performance report."""
    logger.info("Running analytics...")
    analytics = AnalyticsEngine()
    report = analytics.generate_weekly_report()

    print(f"\n{'='*60}")
    print(f"  WEEKLY PERFORMANCE REPORT")
    print(f"{'='*60}")
    print(f"\n  Summary: {report.get('summary', 'N/A')}")
    print(f"  Posts analyzed: {report.get('posts_analyzed', 0)}")
    print(f"  Engagement trend: {report.get('engagement_trend', 'N/A')}")

    if report.get("content_recommendations"):
        print(f"\n  Recommendations:")
        for rec in report["content_recommendations"]:
            print(f"    - {rec}")

    if report.get("next_week_suggestions"):
        print(f"\n  Next week topics:")
        for sug in report["next_week_suggestions"]:
            print(f"    - [{sug.get('pillar')}] {sug.get('topic_hint')}")
            print(f"      Why: {sug.get('why')}")

    print(f"\n{'='*60}\n")
    return report


def post_from_queue():
    """Post the next item from the content queue."""
    if not CONTENT_QUEUE_FILE.exists():
        logger.warning("No content queue found. Run 'generate' first.")
        return None

    with open(CONTENT_QUEUE_FILE) as f:
        queue = json.load(f)

    if not queue:
        logger.info("Content queue is empty. Run 'generate' to refill.")
        return None

    # Get the next post
    post_data = queue.pop(0)

    # Save remaining queue
    with open(CONTENT_QUEUE_FILE, "w") as f:
        json.dump(queue, f, indent=2)

    # Post it
    linkedin = LinkedInAPI()
    post_text = post_data["text"]
    image_path = post_data.get("image_path", "")

    if image_path and Path(image_path).exists():
        result = linkedin.create_image_post(post_text, image_path)
    else:
        result = linkedin.create_text_post(post_text)

    logger.info(f"Posted from queue: {result.get('id')}")
    logger.info(f"Remaining in queue: {len(queue)}")
    return result


# ─── Continuous Run Mode ────────────────────────────────────

def run_automation_loop():
    """
    Run the full automation loop continuously.
    Handles scheduled posting, comment monitoring, and analytics.
    """
    logger.info("Starting LinkedIn Automation Agent...")
    logger.info(f"Timezone: {TIMEZONE}")
    logger.info(f"Posting schedule: {json.dumps(POSTING_SCHEDULE, indent=2)}")

    # Schedule posts for each day
    for day, config in POSTING_SCHEDULE.items():
        post_time = config["time"]
        pillar = config["pillar_preference"]

        # schedule library uses lowercase day names
        getattr(sched_lib.every(), day).at(post_time).do(
            create_and_post, pillar=pillar
        )
        logger.info(f"Scheduled: {day} at {post_time} — {pillar}")

    # Schedule comment monitoring (every 30 minutes)
    sched_lib.every(30).minutes.do(run_comment_monitor)
    logger.info("Scheduled: Comment monitoring every 30 minutes")

    # Schedule analytics collection (every 6 hours)
    interval = ANALYTICS_SETTINGS["track_interval_hours"]
    sched_lib.every(interval).hours.do(
        lambda: AnalyticsEngine().collect_metrics()
    )
    logger.info(f"Scheduled: Analytics collection every {interval} hours")

    # Schedule weekly report
    report_day = ANALYTICS_SETTINGS["report_day"]
    report_time = ANALYTICS_SETTINGS["report_time"]
    getattr(sched_lib.every(), report_day).at(report_time).do(run_analytics)
    logger.info(f"Scheduled: Weekly report on {report_day} at {report_time}")

    # Generate initial content queue if empty
    if not CONTENT_QUEUE_FILE.exists() or _queue_is_low():
        logger.info("Content queue is low — generating new content...")
        generate_content_only()

    # Main loop
    print(f"\n{'='*60}")
    print(f"  LINKEDIN AUTOMATION AGENT — RUNNING")
    print(f"  Press Ctrl+C to stop")
    print(f"{'='*60}\n")

    try:
        while True:
            sched_lib.run_pending()
            time.sleep(60)  # Check every minute
    except KeyboardInterrupt:
        logger.info("Automation stopped by user")
        print("\nAutomation stopped. Goodbye!")


def _queue_is_low() -> bool:
    """Check if the content queue needs refilling."""
    if not CONTENT_QUEUE_FILE.exists():
        return True
    with open(CONTENT_QUEUE_FILE) as f:
        queue = json.load(f)
    return len(queue) < 3


# ─── Setup & Testing ───────────────────────────────────────

def run_setup():
    """Interactive setup wizard."""
    print(f"\n{'='*60}")
    print(f"  LINKEDIN AUTOMATION SETUP")
    print(f"{'='*60}")

    print("""
  Step 1: LinkedIn API Setup
  --------------------------
  1. Go to https://www.linkedin.com/developers/apps
  2. Create a new app (or use existing)
  3. Request the following products:
     - Share on LinkedIn
     - Sign In with LinkedIn using OpenID Connect
  4. Under Auth tab, add redirect URL: http://localhost:8080/callback
  5. Copy your Client ID and Client Secret

  Step 2: Get Access Token
  ------------------------""")

    auth_url = LinkedInAPI.get_auth_url()
    print(f"  Visit this URL to authorize:\n  {auth_url}\n")
    print("  After authorizing, you'll be redirected to localhost with a 'code' parameter.")

    code = input("  Paste the authorization code here: ").strip()
    if code:
        try:
            token_data = LinkedInAPI.exchange_code_for_token(code)
            print(f"\n  Access Token: {token_data['access_token'][:20]}...")
            print(f"  Expires in: {token_data.get('expires_in', 'Unknown')} seconds")
            print(f"\n  Add this to your .env file:")
            print(f"  LINKEDIN_ACCESS_TOKEN={token_data['access_token']}")
        except Exception as e:
            print(f"\n  Error: {e}")

    print(f"""
  Step 3: API Keys
  ----------------
  Set these environment variables (or update config.py):

  export ANTHROPIC_API_KEY="your-key"
  export OPENAI_API_KEY="your-key"
  export LINKEDIN_CLIENT_ID="your-id"
  export LINKEDIN_CLIENT_SECRET="your-secret"
  export LINKEDIN_ACCESS_TOKEN="your-token"
  export LINKEDIN_PERSON_URN="urn:li:person:YOUR_ID"

  Step 4: Test
  ------------
  Run: python main.py test
{'='*60}\n""")


def run_tests():
    """Test all API connections."""
    print(f"\n{'='*60}")
    print(f"  CONNECTION TESTS")
    print(f"{'='*60}\n")

    # Test Anthropic
    print("  [1/3] Testing Anthropic (Claude)...", end=" ")
    try:
        from anthropic import Anthropic
        from config import ANTHROPIC_API_KEY
        client = Anthropic(api_key=ANTHROPIC_API_KEY)
        resp = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=50,
            messages=[{"role": "user", "content": "Say 'Connected!' in one word."}],
        )
        print(f"OK — {resp.content[0].text.strip()}")
    except Exception as e:
        print(f"FAILED — {e}")

    # Test OpenAI
    print("  [2/3] Testing OpenAI (DALL-E)...", end=" ")
    try:
        from openai import OpenAI
        from config import OPENAI_API_KEY
        client = OpenAI(api_key=OPENAI_API_KEY)
        # Just test the connection without generating an image
        models = client.models.list()
        print(f"OK — {len(list(models))} models available")
    except Exception as e:
        print(f"FAILED — {e}")

    # Test LinkedIn
    print("  [3/3] Testing LinkedIn API...", end=" ")
    try:
        linkedin = LinkedInAPI()
        profile = linkedin.get_profile()
        name = profile.get("name", profile.get("sub", "Unknown"))
        print(f"OK — Authenticated as: {name}")
    except Exception as e:
        print(f"FAILED — {e}")

    print(f"\n{'='*60}\n")


# ─── CLI Entry Point ───────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="LinkedIn Automation Agent — Dr. Aaron Akwu",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Commands:
  run         Start the full automation loop (runs continuously)
  post        Generate and publish one post immediately
  generate    Generate a full week of content (saved to queue)
  comments    Monitor and reply to new comments
  analytics   Collect metrics and generate performance report
  setup       Interactive setup and LinkedIn OAuth
  test        Test all API connections
        """,
    )
    parser.add_argument(
        "command",
        choices=["run", "post", "generate", "comments", "analytics", "setup", "test"],
        help="Action to perform",
    )
    parser.add_argument("--pillar", type=str, help="Content pillar for 'post' command")
    parser.add_argument("--topic", type=str, help="Topic hint for 'post' command")

    args = parser.parse_args()

    if args.command == "run":
        run_automation_loop()
    elif args.command == "post":
        create_and_post(pillar=args.pillar, topic_hint=args.topic)
    elif args.command == "generate":
        generate_content_only()
    elif args.command == "comments":
        run_comment_monitor()
    elif args.command == "analytics":
        run_analytics()
    elif args.command == "setup":
        run_setup()
    elif args.command == "test":
        run_tests()


if __name__ == "__main__":
    main()
