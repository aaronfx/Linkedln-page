"""
Facebook Graph API Client
==========================
Handles all Facebook Page API interactions: posting text, images, and reading insights.
Uses Facebook's Graph API v25.0.
"""

import json
import logging
import requests
from datetime import datetime, timezone
from pathlib import Path
from config import (
    FACEBOOK_PAGE_ACCESS_TOKEN, FACEBOOK_PAGE_ID,
    DATA_DIR
)

logger = logging.getLogger("facebook_api")

GRAPH_API_VERSION = "v25.0"
GRAPH_BASE_URL = f"https://graph.facebook.com/{GRAPH_API_VERSION}"

FB_POST_HISTORY_FILE = DATA_DIR / "fb_post_history.json"


class FacebookAPI:
    """Client for Facebook's Graph API — Page posting and insights."""

    def __init__(self, access_token: str = None, page_id: str = None):
        self.access_token = access_token or FACEBOOK_PAGE_ACCESS_TOKEN
        self.page_id = page_id or FACEBOOK_PAGE_ID
        self.post_history = self._load_json(FB_POST_HISTORY_FILE, [])

    # ─── Helpers ───────────────────────────────────────────────

    @staticmethod
    def _load_json(path, default):
        try:
            if Path(path).exists():
                with open(path) as f:
                    return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
        return default

    def _save_post_history(self):
        with open(FB_POST_HISTORY_FILE, "w") as f:
            json.dump(self.post_history, f, indent=2)

    def _make_request(self, method, endpoint, **kwargs):
        """Make a Graph API request with error handling."""
        url = f"{GRAPH_BASE_URL}/{endpoint}"
        params = kwargs.pop("params", {})
        params["access_token"] = self.access_token

        resp = requests.request(method, url, params=params, **kwargs)

        if resp.status_code != 200:
            error_data = resp.json().get("error", {})
            logger.error(
                f"Facebook API error: {error_data.get('message', resp.text)} "
                f"(code: {error_data.get('code')}, type: {error_data.get('type')})"
            )
            resp.raise_for_status()

        return resp.json()

    # ─── Page Info ─────────────────────────────────────────────

    def get_page_info(self) -> dict:
        """Get basic page information."""
        return self._make_request(
            "GET", self.page_id,
            params={"fields": "id,name,fan_count,followers_count,category"}
        )

    # ─── Posting ───────────────────────────────────────────────

    def create_text_post(self, message: str) -> dict:
        """
        Publish a text-only post to the Facebook Page.

        Args:
            message: The post text content.

        Returns:
            dict with 'id' of the created post.
        """
        logger.info(f"Publishing text post to Facebook ({len(message)} chars)")

        result = self._make_request(
            "POST", f"{self.page_id}/feed",
            params={"message": message}
        )

        post_id = result.get("id", "")
        logger.info(f"Facebook text post published: {post_id}")

        # Save to history
        self.post_history.append({
            "id": post_id,
            "type": "text",
            "text": message[:200],
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "platform": "facebook",
        })
        self._save_post_history()

        return result

    def create_image_post(self, message: str, image_path: str) -> dict:
        """
        Publish a post with an image to the Facebook Page.

        Args:
            message: The post text content.
            image_path: Local path to the image file.

        Returns:
            dict with 'id' and 'post_id' of the created post.
        """
        logger.info(f"Publishing image post to Facebook ({len(message)} chars)")

        with open(image_path, "rb") as img_file:
            result = self._make_request(
                "POST", f"{self.page_id}/photos",
                params={"message": message},
                files={"source": img_file}
            )

        post_id = result.get("post_id", result.get("id", ""))
        logger.info(f"Facebook image post published: {post_id}")

        # Save to history
        self.post_history.append({
            "id": post_id,
            "type": "image",
            "text": message[:200],
            "image_path": image_path,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "platform": "facebook",
        })
        self._save_post_history()

        return result

    def create_link_post(self, message: str, link: str) -> dict:
        """
        Publish a post with a link to the Facebook Page.

        Args:
            message: The post text content.
            link: URL to include in the post.

        Returns:
            dict with 'id' of the created post.
        """
        logger.info(f"Publishing link post to Facebook")

        result = self._make_request(
            "POST", f"{self.page_id}/feed",
            params={"message": message, "link": link}
        )

        post_id = result.get("id", "")
        logger.info(f"Facebook link post published: {post_id}")

        self.post_history.append({
            "id": post_id,
            "type": "link",
            "text": message[:200],
            "link": link,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "platform": "facebook",
        })
        self._save_post_history()

        return result

    # ─── Insights / Analytics ──────────────────────────────────

    def get_post_insights(self, post_id: str) -> dict:
        """Get engagement metrics for a specific post."""
        try:
            result = self._make_request(
                "GET", post_id,
                params={"fields": "message,created_time,shares,likes.summary(true),comments.summary(true)"}
            )
            return {
                "id": post_id,
                "message": result.get("message", ""),
                "created_time": result.get("created_time", ""),
                "shares": result.get("shares", {}).get("count", 0),
                "likes": result.get("likes", {}).get("summary", {}).get("total_count", 0),
                "comments": result.get("comments", {}).get("summary", {}).get("total_count", 0),
            }
        except Exception as e:
            logger.warning(f"Failed to get insights for {post_id}: {e}")
            return {"id": post_id, "error": str(e)}

    def get_page_insights(self, period: str = "day", metrics: list = None) -> dict:
        """Get page-level insights."""
        if metrics is None:
            metrics = [
                "page_impressions", "page_engaged_users",
                "page_fan_adds", "page_views_total"
            ]
        try:
            result = self._make_request(
                "GET", f"{self.page_id}/insights",
                params={
                    "metric": ",".join(metrics),
                    "period": period,
                }
            )
            return result
        except Exception as e:
            logger.warning(f"Failed to get page insights: {e}")
            return {"error": str(e)}

    def get_recent_posts(self, limit: int = 10) -> list:
        """Get recent posts from the page."""
        try:
            result = self._make_request(
                "GET", f"{self.page_id}/feed",
                params={
                    "fields": "id,message,created_time,shares,likes.summary(true),comments.summary(true)",
                    "limit": limit,
                }
            )
            return result.get("data", [])
        except Exception as e:
            logger.warning(f"Failed to get recent posts: {e}")
            return []

    # ─── Delete / Trash ────────────────────────────────────────

    def delete_post(self, post_id: str) -> dict:
        """Delete a post from the page."""
        logger.info(f"Deleting Facebook post: {post_id}")
        return self._make_request("DELETE", post_id)
