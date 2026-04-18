"""
LinkedIn API Client
===================
Handles all LinkedIn API interactions: posting, comments, analytics.
Uses LinkedIn's Marketing API v2 / Community Management API.
"""

import json
import time
import requests
import logging
from datetime import datetime, timezone
from pathlib import Path
from config import (
    LINKEDIN_ACCESS_TOKEN, LINKEDIN_PERSON_URN,
    LINKEDIN_CLIENT_ID, LINKEDIN_CLIENT_SECRET,
    POST_HISTORY_FILE, COMMENT_LOG_FILE
)

logger = logging.getLogger("linkedin_api")

BASE_URL = "https://api.linkedin.com/v2"
REST_BASE = "https://api.linkedin.com/rest"


class LinkedInAPI:
    """Client for LinkedIn's API."""

    def __init__(self, access_token: str = None):
        self.access_token = access_token or LINKEDIN_ACCESS_TOKEN
        self.person_urn = LINKEDIN_PERSON_URN
        self.headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
            "X-Restli-Protocol-Version": "2.0.0",
            "LinkedIn-Version": "202401",
        }
        self.post_history = self._load_json(POST_HISTORY_FILE, [])
        self.comment_log = self._load_json(COMMENT_LOG_FILE, [])

    # ─── Authentication ─────────────────────────────────────

    @staticmethod
    def get_auth_url(redirect_uri: str = "http://localhost:8080/callback") -> str:
        """Generate the OAuth 2.0 authorization URL."""
        scopes = "openid%20profile%20w_member_social%20r_organization_social"
        return (
            f"https://www.linkedin.com/oauth/v2/authorization?"
            f"response_type=code&client_id={LINKEDIN_CLIENT_ID}"
            f"&redirect_uri={redirect_uri}&scope={scopes}"
        )

    @staticmethod
    def exchange_code_for_token(code: str, redirect_uri: str = "http://localhost:8080/callback") -> dict:
        """Exchange authorization code for access token."""
        resp = requests.post(
            "https://www.linkedin.com/oauth/v2/accessToken",
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": redirect_uri,
                "client_id": LINKEDIN_CLIENT_ID,
                "client_secret": LINKEDIN_CLIENT_SECRET,
            },
        )
        resp.raise_for_status()
        return resp.json()

    # ─── Profile ────────────────────────────────────────────

    def get_profile(self) -> dict:
        """Get the authenticated user's profile."""
        resp = requests.get(f"{BASE_URL}/userinfo", headers=self.headers)
        resp.raise_for_status()
        return resp.json()

    def get_person_urn(self) -> str:
        """Get the person URN for the authenticated user."""
        profile = self.get_profile()
        return f"urn:li:person:{profile['sub']}"

    # ─── Posting ────────────────────────────────────────────

    def create_text_post(self, text: str) -> dict:
        """Create a text-only post."""
        payload = {
            "author": self.person_urn,
            "lifecycleState": "PUBLISHED",
            "specificContent": {
                "com.linkedin.ugc.ShareContent": {
                    "shareCommentary": {"text": text},
                    "shareMediaCategory": "NONE",
                }
            },
            "visibility": {
                "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"
            },
        }
        resp = requests.post(
            f"{BASE_URL}/ugcPosts", headers=self.headers, json=payload
        )
        resp.raise_for_status()
        result = resp.json()

        # Log to history
        post_record = {
            "id": result.get("id"),
            "text": text[:200],
            "created_at": datetime.now(timezone.utc).isoformat(),
            "type": "text",
            "metrics": {},
        }
        self.post_history.append(post_record)
        self._save_json(POST_HISTORY_FILE, self.post_history)

        logger.info(f"Text post created: {result.get('id')}")
        return result

    def create_image_post(self, text: str, image_path: str) -> dict:
        """Create a post with an image."""
        # Step 1: Register the image upload
        register_payload = {
            "registerUploadRequest": {
                "recipes": ["urn:li:digitalmediaRecipe:feedshare-image"],
                "owner": self.person_urn,
                "serviceRelationships": [
                    {
                        "relationshipType": "OWNER",
                        "identifier": "urn:li:userGeneratedContent",
                    }
                ],
            }
        }
        resp = requests.post(
            f"{BASE_URL}/assets?action=registerUpload",
            headers=self.headers,
            json=register_payload,
        )
        resp.raise_for_status()
        upload_data = resp.json()

        upload_url = upload_data["value"]["uploadMechanism"][
            "com.linkedin.digitalmedia.uploading.MediaUploadHttpRequest"
        ]["uploadUrl"]
        asset = upload_data["value"]["asset"]

        # Step 2: Upload the image binary
        with open(image_path, "rb") as img_file:
            upload_headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/octet-stream",
            }
            resp = requests.put(upload_url, headers=upload_headers, data=img_file)
            resp.raise_for_status()

        # Step 3: Create the post with the uploaded image
        payload = {
            "author": self.person_urn,
            "lifecycleState": "PUBLISHED",
            "specificContent": {
                "com.linkedin.ugc.ShareContent": {
                    "shareCommentary": {"text": text},
                    "shareMediaCategory": "IMAGE",
                    "media": [
                        {
                            "status": "READY",
                            "media": asset,
                        }
                    ],
                }
            },
            "visibility": {
                "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"
            },
        }
        resp = requests.post(
            f"{BASE_URL}/ugcPosts", headers=self.headers, json=payload
        )
        resp.raise_for_status()
        result = resp.json()

        post_record = {
            "id": result.get("id"),
            "text": text[:200],
            "image": str(image_path),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "type": "image",
            "metrics": {},
        }
        self.post_history.append(post_record)
        self._save_json(POST_HISTORY_FILE, self.post_history)

        logger.info(f"Image post created: {result.get('id')}")
        return result

    # ─── Comments ───────────────────────────────────────────

    def get_post_comments(self, post_urn: str) -> list:
        """Get all comments on a specific post."""
        resp = requests.get(
            f"{BASE_URL}/socialActions/{post_urn}/comments",
            headers=self.headers,
            params={"count": 100},
        )
        resp.raise_for_status()
        return resp.json().get("elements", [])

    def reply_to_comment(self, post_urn: str, comment_urn: str, reply_text: str) -> dict:
        """Reply to a specific comment on a post."""
        payload = {
            "actor": self.person_urn,
            "message": {"text": reply_text},
            "parentComment": comment_urn,
        }
        resp = requests.post(
            f"{BASE_URL}/socialActions/{post_urn}/comments",
            headers=self.headers,
            json=payload,
        )
        resp.raise_for_status()
        result = resp.json()

        # Log the reply
        reply_record = {
            "post_urn": post_urn,
            "comment_urn": comment_urn,
            "reply_text": reply_text,
            "replied_at": datetime.now(timezone.utc).isoformat(),
        }
        self.comment_log.append(reply_record)
        self._save_json(COMMENT_LOG_FILE, self.comment_log)

        logger.info(f"Replied to comment {comment_urn}")
        return result

    # ─── Analytics ──────────────────────────────────────────

    def get_post_stats(self, post_urn: str) -> dict:
        """Get engagement statistics for a specific post."""
        # Get social actions (likes, comments, shares)
        stats = {}
        for action in ["likes", "comments"]:
            resp = requests.get(
                f"{BASE_URL}/socialActions/{post_urn}/{action}",
                headers=self.headers,
                params={"count": 0},  # We just want the total
            )
            if resp.status_code == 200:
                data = resp.json()
                stats[action] = data.get("paging", {}).get("total", 0)

        # Get share statistics
        resp = requests.get(
            f"{BASE_URL}/organizationalEntityShareStatistics",
            headers=self.headers,
            params={"q": "organizationalEntity", "shares": [post_urn]},
        )
        if resp.status_code == 200:
            elements = resp.json().get("elements", [])
            if elements:
                total_stats = elements[0].get("totalShareStatistics", {})
                stats["impressions"] = total_stats.get("impressionCount", 0)
                stats["clicks"] = total_stats.get("clickCount", 0)
                stats["shares"] = total_stats.get("shareCount", 0)
                stats["engagement"] = total_stats.get("engagement", 0)

        return stats

    def get_all_posts(self, count: int = 50) -> list:
        """Get recent posts by the authenticated user."""
        resp = requests.get(
            f"{BASE_URL}/ugcPosts",
            headers=self.headers,
            params={
                "q": "authors",
                "authors": f"List({self.person_urn})",
                "count": count,
            },
        )
        resp.raise_for_status()
        return resp.json().get("elements", [])

    # ─── Utility ────────────────────────────────────────────

    @staticmethod
    def _load_json(path: Path, default=None):
        if path.exists():
            with open(path) as f:
                return json.load(f)
        return default if default is not None else {}

    @staticmethod
    def _save_json(path: Path, data):
        with open(path, "w") as f:
            json.dump(data, f, indent=2, default=str)
