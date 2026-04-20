"""
LinkedIn API Client
===================
Handles all LinkedIn API interactions: posting, comments, analytics.
Uses LinkedIn's Community Management API (rest/posts).

Updated April 2026: Migrated from deprecated ugcPosts to rest/posts API.
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
    """Client for LinkedIn's Community Management API."""

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

    # ─── Posting (Community Management API) ─────────────────

    def create_text_post(self, text: str) -> dict:
        """Create a text-only post using the rest/posts API."""
        payload = {
            "author": self.person_urn,
            "commentary": text,
            "visibility": "PUBLIC",
            "distribution": {
                "feedDistribution": "MAIN_FEED",
                "targetEntities": [],
                "thirdPartyDistributionChannels": [],
            },
            "lifecycleState": "PUBLISHED",
        }

        resp = requests.post(
            f"{REST_BASE}/posts", headers=self.headers, json=payload
        )

        if resp.status_code == 422:
            # Log the full error for debugging
            logger.error(f"LinkedIn API 422 error: {resp.text}")

        resp.raise_for_status()

        # rest/posts returns 201 with x-restli-id header (no JSON body)
        post_id = resp.headers.get("x-restli-id", resp.headers.get("X-RestLi-Id", "unknown"))
        result = {"id": post_id}

        # Log to history
        post_record = {
            "id": post_id,
            "text": text[:200],
            "created_at": datetime.now(timezone.utc).isoformat(),
            "type": "text",
            "metrics": {},
        }
        self.post_history.append(post_record)
        self._save_json(POST_HISTORY_FILE, self.post_history)

        logger.info(f"Text post created: {post_id}")
        return result

    def create_image_post(self, text: str, image_path: str) -> dict:
        """Create a post with an image using the rest/images + rest/posts API."""

        # Step 1: Initialize the image upload
        init_payload = {
            "initializeUploadRequest": {
                "owner": self.person_urn,
            }
        }
        resp = requests.post(
            f"{REST_BASE}/images?action=initializeUpload",
            headers=self.headers,
            json=init_payload,
        )
        resp.raise_for_status()
        upload_data = resp.json()

        upload_url = upload_data["value"]["uploadUrl"]
        image_urn = upload_data["value"]["image"]

        logger.info(f"Image upload initialized: {image_urn}")

        # Step 2: Upload the image binary
        with open(image_path, "rb") as img_file:
            upload_headers = {
                "Authorization": f"Bearer {self.access_token}",
            }
            resp = requests.put(upload_url, headers=upload_headers, data=img_file)
            resp.raise_for_status()

        logger.info(f"Image binary uploaded successfully")

        # Step 3: Create the post with the uploaded image
        payload = {
            "author": self.person_urn,
            "commentary": text,
            "visibility": "PUBLIC",
            "distribution": {
                "feedDistribution": "MAIN_FEED",
                "targetEntities": [],
                "thirdPartyDistributionChannels": [],
            },
            "content": {
                "media": {
                    "title": "Post image",
                    "id": image_urn,
                }
            },
            "lifecycleState": "PUBLISHED",
        }

        resp = requests.post(
            f"{REST_BASE}/posts", headers=self.headers, json=payload
        )

        if resp.status_code == 422:
            logger.error(f"LinkedIn API 422 error on image post: {resp.text}")

        resp.raise_for_status()

        post_id = resp.headers.get("x-restli-id", resp.headers.get("X-RestLi-Id", "unknown"))
        result = {"id": post_id}

        post_record = {
            "id": post_id,
            "text": text[:200],
            "image": str(image_path),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "type": "image",
            "metrics": {},
        }
        self.post_history.append(post_record)
        self._save_json(POST_HISTORY_FILE, self.post_history)

        logger.info(f"Image post created: {post_id}")
        return result

    # ─── Comments ───────────────────────────────────────────

    def get_post_comments(self, post_urn: str) -> list:
        """Get all comments on a specific post."""
        resp = requests.get(
            f"{REST_BASE}/socialActions/{post_urn}/comments",
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
            f"{REST_BASE}/socialActions/{post_urn}/comments",
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
        stats = {}
        for action in ["likes", "comments"]:
            resp = requests.get(
                f"{REST_BASE}/socialActions/{post_urn}/{action}",
                headers=self.headers,
                params={"count": 0},
            )
            if resp.status_code == 200:
                data = resp.json()
                stats[action] = data.get("paging", {}).get("total", 0)

        return stats

    def get_all_posts(self, count: int = 50) -> list:
        """Get recent posts by the authenticated user."""
        resp = requests.get(
            f"{REST_BASE}/posts",
            headers=self.headers,
            params={
                "q": "author",
                "author": self.person_urn,
                "count": count,
            },
        )
        if resp.status_code == 200:
            return resp.json().get("elements", [])
        logger.warning(f"Could not fetch posts: {resp.status_code}")
        return []

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
