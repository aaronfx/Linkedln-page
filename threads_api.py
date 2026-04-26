"""
Threads API — Meta Threads Graph API v1.0
==========================================
Handles all Threads publishing, insights, and reply monitoring.

Threads uses the same Meta infrastructure as Instagram/Facebook but
with its own access token and user ID.

Docs: https://developers.facebook.com/docs/threads
"""

import os
import json
import time
import logging
import requests
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger("threads_api")

THREADS_BASE_URL = "https://graph.threads.net/v1.0"
GRAPH_BASE_URL = "https://graph.facebook.com/v25.0"


class ThreadsAPI:
    """
    Threads Graph API client.

    Required env vars:
        THREADS_ACCESS_TOKEN  — long-lived Threads user token
        THREADS_USER_ID       — your Threads user ID (numeric)
    """

    def __init__(self):
        self.access_token = os.getenv("THREADS_ACCESS_TOKEN", "")
        self.user_id = os.getenv("THREADS_USER_ID", "")
        self.base_url = THREADS_BASE_URL

        if not self.access_token or not self.user_id:
            logger.warning(
                "THREADS_ACCESS_TOKEN or THREADS_USER_ID not set. "
                "Threads posting will fail."
            )

    # ── Core publishing ────────────────────────────────────────────────────────

    def create_text_post(self, text: str) -> dict:
        """
        Publish a text-only Threads post.

        Returns:
            {"success": True, "post_id": "...", "permalink": "..."}
        """
        logger.info(f"Publishing Threads text post ({len(text)} chars)...")

        container_id = self._create_container(media_type="TEXT", text=text)
        post_id = self._publish_container(container_id)
        permalink = self._get_permalink(post_id)
        logger.info(f"Threads post published: {post_id}")

        return {
            "success": True,
            "post_id": post_id,
            "permalink": permalink,
            "text": text,
            "type": "text",
            "platform": "threads",
            "posted_at": datetime.now(timezone.utc).isoformat(),
        }

    def create_image_post(self, image_url: str, text: str) -> dict:
        """
        Publish a Threads post with an image.

        Args:
            image_url: Publicly accessible URL of the image.
            text:      Caption text.
        """
        logger.info(f"Publishing Threads image post ({len(text)} chars)...")

        container_id = self._create_container(
            media_type="IMAGE", image_url=image_url, text=text
        )
        post_id = self._publish_container(container_id)
        permalink = self._get_permalink(post_id)

        logger.info(f"Threads image post published: {post_id}")
        return {
            "success": True,
            "post_id": post_id,
            "permalink": permalink,
            "text": text,
            "image_url": image_url,
            "type": "image",
            "platform": "threads",
            "posted_at": datetime.now(timezone.utc).isoformat(),
        }

    # ── Analytics ─────────────────────────────────────────────────────────────

    def get_post_insights(self, post_id: str) -> dict:
        """Get engagement metrics for a specific Threads post."""
        metrics = ["views", "likes", "replies", "reposts", "quotes"]
        resp = self._get(
            f"{post_id}/insights",
            params={"metric": ",".join(metrics)},
        )

        result = {"post_id": post_id}
        for item in resp.get("data", []):
            result[item["name"]] = item.get("values", [{}])[-1].get("value", 0)

        logger.info(f"Threads insights for {post_id}: {result}")
        return result

    def get_account_insights(self) -> dict:
        """Get account-level Threads insights (followers, views, etc.)."""
        metrics = ["followers_count", "views"]
        resp = self._get(
            f"{self.user_id}/threads_insights",
            params={
                "metric": ",".join(metrics),
                "period": "day",
            },
        )

        result = {}
        for item in resp.get("data", []):
            result[item["name"]] = item.get("values", [{}])[-1].get("value", 0)

        return result

    def get_recent_posts(self, limit: int = 10) -> list:
        """Get recent Threads posts with basic metrics."""
        resp = self._get(
            f"{self.user_id}/threads",
            params={
                "fields": "id,text,timestamp,permalink,media_type,like_count,reply_count",
                "limit": limit,
            },
        )
        return resp.get("data", [])

    # ── Reply monitoring ───────────────────────────────────────────────────────

    def get_replies(self, post_id: str, limit: int = 50) -> list:
        """Fetch replies to a Threads post."""
        resp = self._get(
            f"{post_id}/replies",
            params={
                "fields": "id,text,username,timestamp,has_replies",
                "limit": limit,
            },
        )
        return resp.get("data", [])

    def reply_to_post(self, post_id: str, text: str) -> dict:
        """Post a reply to a Threads post."""
        container_id = self._create_container(
            media_type="TEXT",
            text=text,
            reply_to_id=post_id,
        )
        reply_id = self._publish_container(container_id)
        logger.info(f"Threads reply posted: {reply_id} -> {post_id}")
        return {
            "success": True,
            "reply_id": reply_id,
            "parent_post_id": post_id,
            "text": text,
        }

    # ── Private helpers ────────────────────────────────────────────────────────

    def _create_container(
        self,
        media_type: str,
        text: str = "",
        image_url: str = "",
        reply_to_id: str = "",
    ) -> str:
        """Create a Threads media container. Returns container ID."""
        params = {
            "media_type": media_type,
            "access_token": self.access_token,
        }
        if text:
            params["text"] = text
        if image_url:
            params["image_url"] = image_url
        if reply_to_id:
            params["reply_to_id"] = reply_to_id

        resp = requests.post(
            f"{self.base_url}/{self.user_id}/threads",
            params=params,
            timeout=30,
        )
        self._raise_for_error(resp)
        container_id = resp.json().get("id")
        if not container_id:
            raise ValueError(f"No container ID in Threads response: {resp.text}")

        logger.debug(f"Threads container created: {container_id}")
        return container_id

    def _publish_container(self, container_id: str, max_wait: int = 30) -> str:
        """
        Publish a Threads container.
        Threads containers are usually ready immediately, but we add a small wait.
        """
        time.sleep(2)

        resp = requests.post(
            f"{self.base_url}/{self.user_id}/threads_publish",
            params={
                "creation_id": container_id,
                "access_token": self.access_token,
            },
            timeout=30,
        )
        self._raise_for_error(resp)
        post_id = resp.json().get("id")
        if not post_id:
            raise ValueError(f"No post ID in Threads publish response: {resp.text}")
        return post_id

    def _get_permalink(self, post_id: str) -> str:
        """Get the permalink URL for a published post."""
        try:
            resp = self._get(f"{post_id}", params={"fields": "permalink"})
            return resp.get("permalink", "")
        except Exception:
            return f"https://www.threads.net/@gopipways/post/{post_id}"

    def _get(self, endpoint: str, params: dict = None) -> dict:
        """Make an authenticated GET request to the Threads API."""
        if params is None:
            params = {}
        params["access_token"] = self.access_token

        if endpoint.startswith("http"):
            url = endpoint
        else:
            url = f"{self.base_url}/{endpoint}"

        resp = requests.get(url, params=params, timeout=30)
        self._raise_for_error(resp)
        return resp.json()

    def _raise_for_error(self, resp: requests.Response):
        """Raise a descriptive error if the API returned an error."""
        if resp.status_code >= 400:
            try:
                error = resp.json().get("error", {})
                msg = error.get("message", resp.text)
                code = error.get("code", resp.status_code)
                raise ValueError(f"Threads API error {code}: {msg}")
            except (json.JSONDecodeError, AttributeError):
                resp.raise_for_status()
