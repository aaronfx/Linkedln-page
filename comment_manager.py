"""
Comment Manager
================
Monitors LinkedIn posts for new comments, classifies them,
and generates + posts intelligent replies using Claude.
"""

import json
import time
import logging
from datetime import datetime, timezone
from config import REPLY_SETTINGS, COMMENT_LOG_FILE, POST_HISTORY_FILE
from linkedin_api import LinkedInAPI
from content_engine import generate_reply, classify_comment
from pathlib import Path

logger = logging.getLogger("comment_manager")


class CommentManager:
    """Manages automated comment monitoring and replies."""

    def __init__(self, linkedin: LinkedInAPI = None):
        self.linkedin = linkedin or LinkedInAPI()
        self.replied_comments = self._load_replied_ids()
        self.reply_count_this_hour = 0
        self.hour_start = datetime.now(timezone.utc)

    # ─── Main Loop ──────────────────────────────────────────

    def monitor_and_reply(self, post_urns: list = None):
        """
        Check all recent posts for new comments and reply.

        Args:
            post_urns: Specific post URNs to monitor (None = all recent posts)
        """
        if post_urns is None:
            post_urns = self._get_recent_post_urns()

        if not post_urns:
            logger.info("No posts to monitor")
            return

        logger.info(f"Monitoring {len(post_urns)} posts for comments...")

        for post_urn in post_urns:
            self._process_post_comments(post_urn)

    def _process_post_comments(self, post_urn: str):
        """Process all comments on a single post."""
        try:
            comments = self.linkedin.get_post_comments(post_urn)
        except Exception as e:
            logger.error(f"Failed to get comments for {post_urn}: {e}")
            return

        # Get original post text for context
        original_text = self._get_post_text(post_urn)

        new_comments = [
            c for c in comments
            if c.get("$URN", c.get("id", "")) not in self.replied_comments
        ]

        if not new_comments:
            return

        logger.info(f"Found {len(new_comments)} new comments on {post_urn}")

        for comment in new_comments:
            self._handle_comment(post_urn, comment, original_text)

    def _handle_comment(self, post_urn: str, comment: dict, original_text: str):
        """Handle a single comment: classify, generate reply, post."""
        comment_urn = comment.get("$URN", comment.get("id", ""))
        comment_text = comment.get("message", {}).get("text", "")
        commenter = comment.get("actor", "Someone")

        # Extract commenter name (simplified — in production, look up via API)
        commenter_name = commenter if isinstance(commenter, str) else "Someone"

        # Skip checks
        if not self._should_reply(comment_text):
            logger.info(f"Skipping comment: {comment_text[:50]}")
            self._mark_replied(comment_urn)
            return

        # Rate limiting
        if not self._check_rate_limit():
            logger.warning("Rate limit reached, pausing replies")
            return

        # Classify the comment
        classification = classify_comment(comment_text)
        sentiment = classification.get("sentiment", "neutral")
        priority = classification.get("priority", "medium")

        logger.info(
            f"Comment classified — Sentiment: {sentiment}, "
            f"Priority: {priority}, Text: {comment_text[:80]}"
        )

        # Generate reply using Claude
        reply_text = generate_reply(
            comment_text=comment_text,
            commenter_name=commenter_name,
            original_post_text=original_text,
            comment_sentiment=sentiment,
        )

        # Add human-like delay
        if REPLY_SETTINGS["reply_delay_minutes"] > 0:
            delay = REPLY_SETTINGS["reply_delay_minutes"] * 60
            logger.info(f"Waiting {REPLY_SETTINGS['reply_delay_minutes']}min before replying...")
            time.sleep(delay)

        # Post the reply
        if REPLY_SETTINGS["auto_reply"]:
            try:
                self.linkedin.reply_to_comment(post_urn, comment_urn, reply_text)
                logger.info(f"Replied to {commenter_name}: {reply_text[:80]}...")
                self.reply_count_this_hour += 1
            except Exception as e:
                logger.error(f"Failed to post reply: {e}")
        else:
            logger.info(f"[DRAFT] Reply to {commenter_name}: {reply_text}")

        # Mark as handled
        self._mark_replied(comment_urn)

        # Log the interaction
        self._log_interaction(
            post_urn, comment_urn, comment_text,
            commenter_name, reply_text, classification
        )

    # ─── Filtering & Rate Limiting ──────────────────────────

    def _should_reply(self, comment_text: str) -> bool:
        """Determine if a comment warrants a reply."""
        # Too short
        if len(comment_text.strip()) < REPLY_SETTINGS["min_comment_length"]:
            return False

        # Contains skip keywords (spam/promotion)
        text_lower = comment_text.lower()
        for keyword in REPLY_SETTINGS["skip_keywords"]:
            if keyword.lower() in text_lower:
                return False

        return True

    def _check_rate_limit(self) -> bool:
        """Check if we're within the hourly rate limit."""
        now = datetime.now(timezone.utc)
        # Reset counter every hour
        if (now - self.hour_start).total_seconds() > 3600:
            self.reply_count_this_hour = 0
            self.hour_start = now

        return self.reply_count_this_hour < REPLY_SETTINGS["max_replies_per_hour"]

    # ─── Data Management ────────────────────────────────────

    def _get_recent_post_urns(self) -> list:
        """Get URNs of recent posts from history.
        Only checks last 5 posts (was 20 — too many API calls).
        """
        history = self._load_json(POST_HISTORY_FILE, [])
        return [p["id"] for p in history[-5:] if p.get("id")]

    def _get_post_text(self, post_urn: str) -> str:
        """Get the original text of a post."""
        history = self._load_json(POST_HISTORY_FILE, [])
        for post in history:
            if post.get("id") == post_urn:
                return post.get("text", "")
        return ""

    def _mark_replied(self, comment_urn: str):
        """Mark a comment as replied to."""
        self.replied_comments.add(comment_urn)
        self._save_replied_ids()

    def _load_replied_ids(self) -> set:
        """Load set of already-replied comment IDs."""
        log = self._load_json(COMMENT_LOG_FILE, [])
        return {entry.get("comment_urn", "") for entry in log}

    def _save_replied_ids(self):
        """Persist replied IDs (handled via comment log)."""
        pass  # Already handled by linkedin_api.reply_to_comment

    def _log_interaction(
        self, post_urn, comment_urn, comment_text,
        commenter_name, reply_text, classification
    ):
        """Log a comment interaction for analytics."""
        log = self._load_json(COMMENT_LOG_FILE, [])
        log.append({
            "post_urn": post_urn,
            "comment_urn": comment_urn,
            "commenter": commenter_name,
            "comment_text": comment_text,
            "reply_text": reply_text,
            "classification": classification,
            "replied_at": datetime.now(timezone.utc).isoformat(),
        })
        self._save_json(COMMENT_LOG_FILE, log)

    @staticmethod
    def _load_json(path, default=None):
        path = Path(path)
        if path.exists():
            with open(path) as f:
                return json.load(f)
        return default if default is not None else {}

    @staticmethod
    def _save_json(path, data):
        path = Path(path)
        with open(path, "w") as f:
            json.dump(data, f, indent=2, default=str)
