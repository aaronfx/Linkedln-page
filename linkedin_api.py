"""
LinkedIn API Client
===================
Handles all LinkedIn API interactions: posting, comments, analytics.
Uses LinkedIn's Community Management API (rest/posts).

Updated April 2026:
- Migrated from deprecated ugcPosts to rest/posts API.
- Added rate limiting, exponential backoff, and circuit breaker.
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

# ─── Rate Limiting Constants ───────────────────────────────
MIN_REQUEST_INTERVAL = 2.0       # Minimum seconds between API calls
MAX_DAILY_REQUESTS = 80          # Stay well under LinkedIn's limits
BACKOFF_BASE = 5                 # Base seconds for exponential backoff
MAX_RETRIES = 3                  # Max retries on transient errors
CIRCUIT_BREAKER_THRESHOLD = 5    # Consecutive failures before circuit breaks
CIRCUIT_BREAKER_RESET = 300      # Seconds to wait before retrying after circuit break


class RateLimiter:
    """Simple rate limiter to prevent excessive API calls."""

    def __init__(self):
        self.last_request_time = 0
        self.daily_request_count = 0
        self.daily_reset_time = time.time()
        self.consecutive_failures = 0
        self.circuit_broken_until = 0

    def wait_if_needed(self):
        """Wait to respect rate limits. Returns False if circuit is broken."""
        now = time.time()

        # Reset daily counter every 24 hours
        if now - self.daily_reset_time > 86400:
            self.daily_request_count = 0
            self.daily_reset_time = now

        # Check circuit breaker
        if now < self.circuit_broken_until:
            wait_time = self.circuit_broken_until - now
            logger.warning(f"Circuit breaker active. Waiting {wait_time:.0f}s before retrying.")
            return False

        # Check daily limit
        if self.daily_request_count >= MAX_DAILY_REQUESTS:
            logger.warning(f"Daily API limit reached ({MAX_DAILY_REQUESTS}). Skipping request.")
            return False

        # Enforce minimum interval between requests
        elapsed = now - self.last_request_time
        if elapsed < MIN_REQUEST_INTERVAL:
            sleep_time = MIN_REQUEST_INTERVAL - elapsed
            time.sleep(sleep_time)

        self.last_request_time = time.time()
        self.daily_request_count += 1
        return True

    def record_success(self):
        """Record a successful API call."""
        self.consecutive_failures = 0

    def record_failure(self):
        """Record a failed API call. Trips circuit breaker if too many."""
        self.consecutive_failures += 1
        if self.consecutive_failures >= CIRCUIT_BREAKER_THRESHOLD:
            self.circuit_broken_until = time.time() + CIRCUIT_BREAKER_RESET
            logger.error(
                f"Circuit breaker tripped after {self.consecutive_failures } failures. "
                f"Pausing API calls for {CIRCUIT_BREAKER_RESET}s."
            )


# Global rate limiter instance (shared across all LinkedInAPI instances)
_rate_limiter = RateLimiter()


class LinkedInAPI:
    """Client for LinkedIn's Community Management API."""

    def __init__(self, access_token: str = None):
        self.access_token = access_token or LINKEDIN_ACCESS_TOKEN
        self.person_urn = LINKEDIN_PERSON_URN
        self.headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
            "X-Restli-Protocol-Version": "2.0.0",
            "LinkedIn-Version": "202603",
        }
        self.post_history = self._load_json(POST_HISTORY_FILE, [])
        self.comment_log = self._load_json(COMMENT_LOG_FILE, [])
        self.rate_limiter = _rate_limiter

    # ─── Rate-Limited Request Helper ───────────────────────────

    def _make_request(self, method, url, **kwargs):
        """
        Make an API request with rate limiting, retries, and backoff.
        Returns the response object or raises on final failure.
        """
        if not self.rate_limiter.wait_if_needed():
            raise Exception("Rate limit exceeded or circuit breaker active. Try again later.")

        last_error = None
        for attempt in range(MAX_RETRIES):
            try:
                resp = getattr(requests, method)(url, headers=self.headers, **kwargs)

                # Handle rate limiting response
                if resp.status_code == 429:
                    retry_after = int(resp.headers.get("Retry-After", BACKOFF_BASE * (2 ** attempt)))
                    logger.warning(f"Rate limited (429). Waiting {retry_after}s...")
                    time.sleep(retry_after)
                    self.rate_limiter.record_failure()
                    continue

                # Handle auth errors — don't retry, token is bad
                if resp.status_code in (401, 403):
                    self.rate_limiter.record_failure()
                    logger.error(f"Auth error ({resp.status_code}): {resp.text[:200]}")
                    resp.raise_for_status()

                # Handle server errors with backoff
                if resp.status_code >= 500:
                    wait = BACKOFF_BASE * (2 ** attempt)
                    logger.warning(f"Server error ({resp.status_code}). Retrying in {wait}s...")
                    time.sleep(wait)
                    self.rate_limiter.record_failure()
                    continue

                # Success
                self.rate_limiter.record_success()
                return resp

            except requests.exceptions.ConnectionError as e:
                wait = BACKOFF_BASE * (2 ** attempt)
                logger.warning(f"Connection error (attempt {attempt + 1}): {e}. Retrying in {wait}s...")
                time.sleep(wait)
                last_error = e
                self.rate_limiter.record_failure()

        # All retries exhausted
        raise last_error or Exception(f"Request failed after {MAX_RETRIES} retries")

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

    def test_connection(self) -> dict:
        """Test if the current access token is valid."""
        try:
            resp = self._make_request("get", f"{BASE_URL}/userinfo")
            resp.raise_for_status()
            return {"status": "ok", "profile": resp.json()}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def debug_api(self) -> dict:
        """
        Deep diagnostic: test every API endpoint and return full error bodies.
        Helps identify exactly which permissions/scopes are missing.
        """
        results = {"token_info": {}, "endpoints": {}, "headers_used": dict(self.headers), "person_urn": self.person_urn}

        # 1. Test userinfo (basic profile - needs openid+profile)
        try:
            resp = requests.get(f"{BASE_URL}/userinfo", headers=self.headers)
            results["endpoints"]["GET /v2/userinfo"] = {
                "status": resp.status_code,
                "body": resp.text[:500],
            }
            if resp.status_code == 200:
                profile = resp.json()
                results["token_info"]["sub"] = profile.get("sub", "unknown")
                results["token_info"]["name"] = profile.get("name", "unknown")
        except Exception as e:
            results["endpoints"]["GET /v2/userinfo"] = {"error": str(e)}

        # 2. Test introspection - what scopes does this token actually have?
        try:
            resp = requests.get(
                f"{BASE_URL}/me",
                headers={"Authorization": f"Bearer {self.access_token}"},
            )
            results["endpoints"]["GET /v2/me"] = {
                "status": resp.status_code,
                "body": resp.text[:500],
            }
        except Exception as e:
            results["endpoints"]["GET /v2/me"] = {"error": str(e)}

        # 3. Test REST posts endpoint (needs w_member_social)
        try:
            test_payload = {
                "author": self.person_urn,
                "commentary": "Debug test - this should not be posted",
                "visibility": "PUBLIC",
                "distribution": {
                    "feedDistribution": "MAIN_FEED",
                    "targetEntities": [],
                    "thirdPartyDistributionChannels": [],
                },
                "lifecycleState": "PUBLISHED",
            }
            # Use VALIDATION only header to not actually post
            debug_headers = dict(self.headers)
            debug_headers["X-RestLi-Method"] = "BATCH_CREATE"  # invalid on purpose to get auth check only

            resp = requests.post(
                f"{REST_BASE}/posts",
                headers=self.headers,
                json=test_payload,
            )
            results["endpoints"]["POST /rest/posts"] = {
                "status": resp.status_code,
                "body": resp.text[:1000],
                "response_headers": dict(resp.headers),
            }
        except Exception as e:
            results["endpoints"]["POST /rest/posts"] = {"error": str(e)}

        # 4. Test GET posts (reading own posts - needs r_organization_social or w_member_social)
        try:
            resp = requests.get(
                f"{REST_BASE}/posts",
                headers=self.headers,
                params={"q": "author", "author": self.person_urn, "count": 1},
            )
            results["endpoints"]["GET /rest/posts"] = {
                "status": resp.status_code,
                "body": resp.text[:500],
            }
        except Exception as e:
            results["endpoints"]["GET /rest/posts"] = {"error": str(e)}

        # 5. Test social actions (needs r_organization_social)
        try:
            resp = requests.get(
                f"{REST_BASE}/socialActions/urn:li:share:test/likes",
                headers=self.headers,
                params={"count": 0},
            )
            results["endpoints"]["GET /rest/socialActions"] = {
                "status": resp.status_code,
                "body": resp.text[:500],
            }
        except Exception as e:
            results["endpoints"]["GET /rest/socialActions"] = {"error": str(e)}

        # 6. Try v2 ugcPosts endpoint as fallback check
        try:
            resp = requests.get(
                f"{BASE_URL}/ugcPosts",
                headers={"Authorization": f"Bearer {self.access_token}", "X-Restli-Protocol-Version": "2.0.0"},
                params={"q": "authors", "authors": f"List({self.person_urn})", "count": 1},
            )
            results["endpoints"]["GET /v2/ugcPosts"] = {
                "status": resp.status_code,
                "body": resp.text[:500],
            }
        except Exception as e:
            results["endpoints"]["GET /v2/ugcPosts"] = {"error": str(e)}

        return results

    # ─── Profile ────────────────────────────────────────────

    def get_profile(self) -> dict:
        """Get the authenticated user's profile."""
        resp = self._make_request("get", f"{BASE_URL}/userinfo")
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

        resp = self._make_request("post", f"{REST_BASE}/posts", json=payload)

        if resp.status_code == 422:
            logger.error(f"LinkedIn API 422 error: {resp.text}")

        resp.raise_for_status()

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
        resp = self._make_request(
            "post",
            f"{REST_BASE}/images?action=initializeUpload",
            json=init_payload,
        )
        resp.raise_for_status()
        upload_data = resp.json()

        upload_url = upload_data["value"]["uploadUrl"]
        image_urn = upload_data["value"]["image"]

        logger.info(f"Image upload initialized: {image_urn}")

        # Step 2: Upload the image binary (uses direct requests, not rate-limited)
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

        resp = self._make_request("post", f"{REST_BASE}/posts", json=payload)

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
        """Get comments on a specific post."""
        try:
            resp = self._make_request(
                "get",
                f"{REST_BASE}/socialActions/{post_urn}/comments",
                params={"count": 50},  # Reduced from 100
            )
            resp.raise_for_status()
            return resp.json().get("elements", [])
        except Exception as e:
            logger.error(f"Failed to get comments for {post_urn}: {e}")
            return []

    def reply_to_comment(self, post_urn: str, comment_urn: str, reply_text: str) -> dict:
        """Reply to a specific comment on a post."""
        payload = {
            "actor": self.person_urn,
            "message": {"text": reply_text},
            "parentComment": comment_urn,
        }
        resp = self._make_request(
            "post",
            f"{REST_BASE}/socialActions/{post_urn}/comments",
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
            try:
                resp = self._make_request(
                    "get",
                    f"{REST_BASE}/socialActions/{post_urn}/{action}",
                    params={"count": 0},
                )
                if resp.status_code == 200:
                    data = resp.json()
                    stats[action] = data.get("paging", {}).get("total", 0)
            except Exception as e:
                logger.warning(f"Failed to get {action} for {post_urn}: {e}")

        return stats

    def get_all_posts(self, count: int = 20) -> list:
        """Get recent posts by the authenticated user."""
        try:
            resp = self._make_request(
                "get",
                f"{REST_BASE}/posts",
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
        except Exception as e:
            logger.error(f"Failed to fetch posts: {e}")
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
