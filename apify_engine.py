"""
            "author_followers": item.get("user_followers", item.get("followers_count", 0)),
Apify integration -- LinkedIn metrics and comments scraping.

Replaces the broken LinkedIn read API (r_member_social scope / hanging calls).
Two actors:
  - apimaestro/linkedin-post-comments-replies-engagements-scraper-no-cookies
    -> comments, replies, reaction counts per post
  - vulnv/linkedin-posts-scraper
    -> post-level stats: likes, shares, views, reactions
"""
import os
import time
import logging
from typing import Optional

import requests as _requests

logger = logging.getLogger(__name__)

APIFY_BASE = "https://api.apify.com/v2"
ACTOR_COMMENTS = "apimaestro~linkedin-post-comments-replies-engagements-scraper-no-cookies"
ACTOR_POSTS    = "vulnv~linkedin-posts-scraper"


def _api_key():
    key = os.environ.get("APIFY_API_KEY", "")
    if not key:
        try:
            from config import APIFY_API_KEY
            key = APIFY_API_KEY
        except Exception:
            pass
    return key or None


def urn_to_url(post_urn):
    if post_urn.startswith("http"):
        return post_urn
    return f"https://www.linkedin.com/feed/update/{post_urn}/"


def _run_actor(actor_id, payload, timeout_s=180):
    api_key = _api_key()
    if not api_key:
        logger.warning("APIFY_API_KEY not configured -- skipping Apify sync")
        return []
    try:
        run_resp = _requests.post(
            f"{APIFY_BASE}/acts/{actor_id}/runs",
            params={"token": api_key},
            json=payload,
            timeout=30,
        )
        run_resp.raise_for_status()
        run_data = run_resp.json().get("data", {})
        run_id = run_data.get("id")
        dataset_id = run_data.get("defaultDatasetId")
        if not run_id:
            logger.error(f"Apify: no runId from {actor_id}: {run_resp.text[:300]}")
            return []
        logger.info(f"Apify run started: {run_id} ({actor_id})")
        poll_url = f"{APIFY_BASE}/actor-runs/{run_id}"
        deadline = time.time() + timeout_s
        status = "RUNNING"
        while time.time() < deadline:
            time.sleep(12)
            try:
                s = _requests.get(poll_url, params={"token": api_key}, timeout=15)
                status = s.json().get("data", {}).get("status", "RUNNING")
            except Exception:
                pass
            if status in ("SUCCEEDED", "FAILED", "ABORTED", "TIMED-OUT"):
                break
        if status != "SUCCEEDED":
            logger.warning(f"Apify run {run_id} ended: {status}")
            return []
        items_resp = _requests.get(
            f"{APIFY_BASE}/datasets/{dataset_id}/items",
            params={"token": api_key, "format": "json", "clean": "true"},
            timeout=30,
        )
        return items_resp.json() if items_resp.ok else []
    except Exception as e:
        logger.error(f"Apify _run_actor error ({actor_id}): {e}")
        return []


def get_post_comments(post_urns, limit=50):
    if not post_urns:
        return {}
    post_urls = [urn_to_url(u) for u in post_urns]
    url_to_urn = {url: urn for urn, url in zip(post_urns, post_urls)}
    items = _run_actor(
        ACTOR_COMMENTS,
        {"postIds": post_urls, "sortOrder": "most recent", "limit": limit},
    )
    results = {urn: {"comments": [], "total_comments": 0} for urn in post_urns}
    for item in items:
        if "summary" in item:
            continue
        post_input = item.get("post_input", "")
        matching_urn = None
        for url, urn in url_to_urn.items():
            if url in post_input or post_input in url:
                matching_urn = urn
                break
        if not matching_urn:
            if len(post_urns) == 1:
                matching_urn = post_urns[0]
            else:
                continue
        if item.get("text") or item.get("comment_id"):
            results[matching_urn]["comments"].append({
                "id": item.get("comment_id", ""),
                "text": item.get("text", ""),
                "author": item.get("author", {}).get("name", ""),
                "author_profile": item.get("author", {}).get("profile_url", ""),
                "created_at": item.get("posted_at", {}).get("date", ""),
                "likes": item.get("stats", {}).get("total_reactions", 0),
                "replies": item.get("replies", []),
            })
            tc = item.get("totalComments", 0)
            if tc:
                results[matching_urn]["total_comments"] = tc
    return results


def get_post_stats(post_urns):
    if not post_urns:
        return {}
    post_urls = [urn_to_url(u) for u in post_urns]
    url_to_urn = {url: urn for urn, url in zip(post_urns, post_urls)}
    items = _run_actor(ACTOR_POSTS, {"urls": post_urls})
    results = {urn: {} for urn in post_urns}
    for item in items:
        item_url = item.get("url", item.get("postUrl", item.get("linkedinUrl", "")))
        matching_urn = None
        for url, urn in url_to_urn.items():
            if url in item_url or item_url in url:
                matching_urn = urn
                break
        if not matching_urn and len(post_urns) == 1:
            matching_urn = post_urns[0]
        if not matching_urn:
            continue
        results[matching_urn] = {
            "likes":     item.get("likeCount",     item.get("likes",     0)),
            "comments":  item.get("commentCount",  item.get("comments",  0)),
            "shares":    item.get("shareCount",    item.get("shares",    item.get("reposts", 0))),
            "views":     item.get("viewCount",     item.get("views",     0)),
            "reactions": item.get("reactionCount", item.get("totalReactions", 0)),
        }
    return results



ACTOR_PROFILE = "sourabhbgp~linkedin-profile-scraper"


def get_profile_stats(profile_url):
    """
    Fetch LinkedIn profile stats (followers, connections, headline) via Apify.
    Requires LINKEDIN_PROFILE_URL env var set to your LinkedIn vanity URL.
    Returns a dict; empty dict on failure or missing URL.
    """
    if not profile_url:
        logger.info("Apify profile sync: LINKEDIN_PROFILE_URL not set -- skipping")
        return {}
    items = _run_actor(ACTOR_PROFILE, {"profiles": [profile_url], "maxResults": 1})
    if not items:
        logger.warning(f"Apify profile sync: no data for {profile_url}")
        return {}
    item = items[0]
    import datetime as _dt
    return {
        "followers":   item.get("followersCount", item.get("followers", 0)),
        "connections": item.get("connectionsCount", item.get("connections", 0)),
        "name":        item.get("fullName", item.get("name", "")),
        "headline":    item.get("headline", ""),
        "profile_url": profile_url,
        "synced_at":   _dt.datetime.utcnow().isoformat() + "Z",
    }

def sync_all_post_data(post_urns, limit_comments=30):
    if not post_urns:
        return {}
    logger.info(f"Apify: syncing {len(post_urns)} posts (comments + stats)")
    comments_data = get_post_comments(post_urns, limit=limit_comments)
    stats_data = get_post_stats(post_urns)
    merged = {}
    for urn in post_urns:
        merged[urn] = {
            **comments_data.get(urn, {"comments": [], "total_comments": 0}),
            "stats": stats_data.get(urn, {}),
        }
    return merged
