"""
Instagram Graph API Client
============================
Handles all Instagram Business API interactions: publishing posts (single image,
carousel, reels) and reading insights. Uses Facebook's Graph API v25.0 since
Instagram's Content Publishing API is accessed through the Facebook Graph API.

Requirements:
- Instagram Business/Creator account linked to a Facebook Page
- Facebook Page Access Token with instagram_basic + instagram_content_publish permissions
- Instagram Business Account ID (obtained via /{page-id}?fields=instagram_business_account)
"""

import json
import logging
import time
import requests
from datetime import datetime, timezone
from pathlib import Path
from config import (
    FACEBOOK_PAGE_ACCESS_TOKEN,
    INSTAGRAM_BUSINESS_ACCOUNT_ID,
    DATA_DIR,
)

logger = logging.getLogger("instagram_api")

GRAPH_API_VERSION = "v25.0"
GRAPH_BASE_URL = f"https://graph.facebook.com/{GRAPH_API_VERSION}"

IG_POST_HISTORY_FILE = DATA_DIR / "ig_post_history.json"


class InstagramAPI:
    """Client for Instagram's Content Publishing API via Facebook Graph API."""

    def __init__(self, access_token: str = None, ig_account_id: str = None):
        self.access_token = access_token or FACEBOOK_PAGE_ACCESS_TOKEN
        self.ig_account_id = ig_account_id or INSTAGRAM_BUSINESS_ACCOUNT_ID
        self.post_history = self._load_json(IG_POST_HISTORY_FILE, [])

    # Ã¢ÂÂÃ¢ÂÂÃ¢ÂÂ Helpers Ã¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂ

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
        with open(IG_POST_HISTORY_FILE, "w") as f:
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
                f"Instagram API error: {error_data.get('message', resp.text)} "
                f"(code: {error_data.get('code')}, type: {error_data.get('type')})"
            )
            resp.raise_for_status()

        return resp.json()

    # Ã¢ÂÂÃ¢ÂÂÃ¢ÂÂ Account Info Ã¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂ

    def get_account_info(self) -> dict:
        """Get Instagram Business Account information."""
        return self._make_request(
            "GET", self.ig_account_id,
            params={"fields": "id,username,name,profile_picture_url,followers_count,media_count,biography"}
        )

    # Ã¢ÂÂÃ¢ÂÂÃ¢ÂÂ Publishing Ã¢ÂÂ Single Image Post Ã¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂ

    def create_image_post(self, image_url: str, caption: str) -> dict:
        """
        Publish a single image post to Instagram.

        Instagram Content Publishing API is a two-step process:
        1. Create a media container with the image URL and caption
        2. Publish the container

        Args:
            image_url: Public URL of the image (must be accessible by Facebook servers).
            caption: Post caption text (max 2200 chars).

        Returns:
            dict with 'id' of the published post.
        """
        logger.info(f"Publishing image post to Instagram ({len(caption)} chars)")

        # Step 1: Create media container (send image_url+caption in POST body to avoid URL encoding issues)
        container = self._make_request(
            "POST", f"{self.ig_account_id}/media",
            data={
                "image_url": image_url,
                "caption": caption,
            }
        )
        container_id = container.get("id")
        logger.info(f"Media container created: {container_id}")

        # Wait for media processing
        self._wait_for_container(container_id)

        # Step 2: Publish the container
        result = self._make_request(
            "POST", f"{self.ig_account_id}/media_publish",
            params={"creation_id": container_id}
        )

        post_id = result.get("id", "")
        logger.info(f"Instagram image post published: {post_id}")

        # Save to history
        self.post_history.append({
            "id": post_id,
            "type": "image",
            "caption": caption[:200],
            "image_url": image_url,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "platform": "instagram",
        })
        self._save_post_history()

        return result

    # Ã¢ÂÂÃ¢ÂÂÃ¢ÂÂ Publishing Ã¢ÂÂ Carousel Post Ã¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂ

    def create_carousel_post(self, items: list, caption: str) -> dict:
        """
        Publish a carousel post to Instagram.

        Args:
            items: List of dicts with 'image_url' (and optionally 'video_url') for each slide.
                   Each item: {"image_url": "https://..."} or {"video_url": "https://..."}
            caption: Post caption text.

        Returns:
            dict with 'id' of the published post.
        """
        logger.info(f"Publishing carousel post to Instagram ({len(items)} slides)")

        # Step 1: Create individual item containers
        child_ids = []
        for i, item in enumerate(items):
            params = {"is_carousel_item": True}
            if "video_url" in item:
                params["media_type"] = "VIDEO"
                params["video_url"] = item["video_url"]
            else:
                params["image_url"] = item["image_url"]

            child = self._make_request(
                "POST", f"{self.ig_account_id}/media",
                params=params
            )
            child_ids.append(child["id"])
            logger.info(f"Carousel item {i+1}/{len(items)} created: {child['id']}")

        # Wait for all items to process
        for cid in child_ids:
            self._wait_for_container(cid)

        # Step 2: Create carousel container
        carousel = self._make_request(
            "POST", f"{self.ig_account_id}/media",
            params={
                "media_type": "CAROUSEL",
                "children": ",".join(child_ids),
                "caption": caption,
            }
        )
        carousel_id = carousel.get("id")
        logger.info(f"Carousel container created: {carousel_id}")

        self._wait_for_container(carousel_id)

        # Step 3: Publish
        result = self._make_request(
            "POST", f"{self.ig_account_id}/media_publish",
            params={"creation_id": carousel_id}
        )

        post_id = result.get("id", "")
        logger.info(f"Instagram carousel published: {post_id}")

        self.post_history.append({
            "id": post_id,
            "type": "carousel",
            "caption": caption[:200],
            "slide_count": len(items),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "platform": "instagram",
        })
        self._save_post_history()

        return result

    # Ã¢ÂÂÃ¢ÂÂÃ¢ÂÂ Publishing Ã¢ÂÂ Reel Ã¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂ

    def create_reel(self, video_url: str, caption: str, cover_url: str = None, share_to_feed: bool = True) -> dict:
        """
        Publish a Reel to Instagram.

        Args:
            video_url: Public URL of the video file.
            caption: Reel caption text.
            cover_url: Optional cover image URL.
            share_to_feed: Whether to also share to the feed (default True).

        Returns:
            dict with 'id' of the published reel.
        """
        logger.info(f"Publishing reel to Instagram ({len(caption)} chars)")

        params = {
            "media_type": "REELS",
            "video_url": video_url,
            "caption": caption,
            "share_to_feed": str(share_to_feed).lower(),
        }
        if cover_url:
            params["cover_url"] = cover_url

        # Step 1: Create reel container
        container = self._make_request(
            "POST", f"{self.ig_account_id}/media",
            params=params
        )
        container_id = container.get("id")
        logger.info(f"Reel container created: {container_id}")

        # Reels take longer to process
        self._wait_for_container(container_id, max_wait=120)

        # Step 2: Publish
        result = self._make_request(
            "POST", f"{self.ig_account_id}/media_publish",
            params={"creation_id": container_id}
        )

        post_id = result.get("id", "")
        logger.info(f"Instagram reel published: {post_id}")

        self.post_history.append({
            "id": post_id,
            "type": "reel",
            "caption": caption[:200],
            "video_url": video_url,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "platform": "instagram",
        })
        self._save_post_history()

        return result

    # Ã¢ÂÂÃ¢ÂÂÃ¢ÂÂ Container Status Polling Ã¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂ

    def _wait_for_container(self, container_id: str, max_wait: int = 60):
        """
        Poll container status until it's ready for publishing.
        Instagram processes media asynchronously.
        """
        start = time.time()
        while time.time() - start < max_wait:
            status = self._make_request(
                "GET", container_id,
                params={"fields": "status_code,status"}
            )
            code = status.get("status_code")
            if code == "FINISHED":
                logger.info(f"Container {container_id} ready")
                return
            elif code == "ERROR":
                error_msg = status.get("status", "Unknown error")
                raise Exception(f"Media processing failed: {error_msg}")

            logger.debug(f"Container {container_id} status: {code}, waiting...")
            time.sleep(3)

        raise TimeoutError(f"Container {container_id} not ready after {max_wait}s")

    # Ã¢ÂÂÃ¢ÂÂÃ¢ÂÂ Insights / Analytics Ã¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂ

    def get_post_insights(self, media_id: str) -> dict:
        """Get engagement metrics for a specific Instagram post."""
        try:
            result = self._make_request(
                "GET", media_id,
                params={"fields": "id,caption,timestamp,like_count,comments_count,media_type,permalink"}
            )
            return {
                "id": media_id,
                "caption": result.get("caption", "")[:100],
                "timestamp": result.get("timestamp", ""),
                "likes": result.get("like_count", 0),
                "comments": result.get("comments_count", 0),
                "media_type": result.get("media_type", ""),
                "permalink": result.get("permalink", ""),
            }
        except Exception as e:
            logger.warning(f"Failed to get insights for {media_id}: {e}")
            return {"id": media_id, "error": str(e)}

    def get_account_insights(self, metric: str = "impressions", period: str = "day") -> dict:
        """Get account-level insights."""
        try:
            result = self._make_request(
                "GET", f"{self.ig_account_id}/insights",
                params={
                    "metric": metric,
                    "period": period,
                }
            )
            return result
        except Exception as e:
            logger.warning(f"Failed to get account insights: {e}")
            return {"error": str(e)}

    def get_recent_media(self, limit: int = 10) -> list:
        """Get recent media from the Instagram account."""
        try:
            result = self._make_request(
                "GET", f"{self.ig_account_id}/media",
                params={
                    "fields": "id,caption,timestamp,like_count,comments_count,media_type,permalink",
                    "limit": limit,
                }
            )
            return result.get("data", [])
        except Exception as e:
            logger.warning(f"Failed to get recent media: {e}")
            return []

    def get_comments(self, media_id: str) -> list:
        """Fetch comments on an Instagram media object."""
        try:
            resp = self._make_request(
                "GET", f"{media_id}/comments",
                params={"fields": "id,text,username,timestamp,replies{id,text,username,timestamp}"}
            )
            return resp.get("data", [])
        except Exception as e:
            logger.warning(f"Could not fetch comments for {media_id}: {e}")
            return []

    def reply_to_comment(self, comment_id: str, reply_text: str) -> dict:
        """Reply to an Instagram comment."""
        return self._make_request(
            "POST", f"{comment_id}/replies",
            data={"message": reply_text}
        )

