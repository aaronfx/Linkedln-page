"""
Apify integration -- LinkedIn metrics, profile scraping, and feed targeting.

Replaces the broken LinkedIn read API (r_member_social scope / hanging calls).

Actors used (all harvestapi — verified 4.8-4.9★, 99.9% success rate):
  harvestapi~linkedin-profile-scraper    -> profile stats: followers, connections, headline
  harvestapi~linkedin-profile-posts      -> recent posts from any profile (feed targeting + post stats)
  apimaestro~linkedin-post-comments-replies-engagements-scraper-no-cookies  -> comments + reactions per post
"""
import os
import time
import logging
import datetime as _dt
from typing import Optional, List, Dict

import requests as _requests

logger = logging.getLogger(__name__)

APIFY_BASE = "https://api.apify.com/v2"

# ---------------------------------------------------------------------------
# Actor IDs  (format: username~actor-name  ==  Apify API slug notation)
# ---------------------------------------------------------------------------
ACTOR_PROFILE   = "harvestapi~linkedin-profile-scraper"   # followers, connections, headline
ACTOR_POSTS     = "harvestapi~linkedin-profile-posts"     # recent posts per profile (feed targeting)
ACTOR_COMMENTS  = "apimaestro~linkedin-post-comments-replies-engagements-scraper-no-cookies"


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _api_key() -> Optional[str]:
    key = os.environ.get("APIFY_API_KEY", "")
    if not key:
        try:
            from config import APIFY_API_KEY
            key = APIFY_API_KEY
        except Exception:
            pass
    return key or None


def urn_to_url(post_urn: str) -> str:
    if post_urn.startswith("http"):
        return post_urn
    return f"https://www.linkedin.com/feed/update/{post_urn}/"


def _run_actor(actor_id: str, payload: dict, timeout_s: int = 180) -> list:
    """
    Start an Apify actor run, poll until completion, return dataset items.
    Returns [] on any failure (key missing, timeout, actor error).
    """
    api_key = _api_key()
    if not api_key:
        logger.warning("APIFY_API_KEY not configured — skipping Apify call")
        return []

    try:
        run_resp = _requests.post(
            f"{APIFY_BASE}/acts/{actor_id}/runs",
            params={"token": api_key},
            json=payload,
            timeout=30,
        )
        run_resp.raise_for_status()
        run_data    = run_resp.json().get("data", {})
        run_id      = run_data.get("id")
        dataset_id  = run_data.get("defaultDatasetId")

        if not run_id:
            logger.error(f"Apify: no runId from {actor_id}: {run_resp.text[:300]}")
            return []

        logger.info(f"Apify run started: {run_id}  actor={actor_id}")

        # Poll for completion
        poll_url = f"{APIFY_BASE}/actor-runs/{run_id}"
        deadline = time.time() + timeout_s
        status   = "RUNNING"
        while time.time() < deadline:
            time.sleep(10)
            try:
                s      = _requests.get(poll_url, params={"token": api_key}, timeout=15)
                status = s.json().get("data", {}).get("status", "RUNNING")
            except Exception:
                pass
            if status in ("SUCCEEDED", "FAILED", "ABORTED", "TIMED-OUT"):
                break

        if status != "SUCCEEDED":
            logger.warning(f"Apify run {run_id} ended with status: {status}")
            return []

        items_resp = _requests.get(
            f"{APIFY_BASE}/datasets/{dataset_id}/items",
            params={"token": api_key, "format": "json", "clean": "true"},
            timeout=30,
        )
        items = items_resp.json() if items_resp.ok else []
        logger.info(f"Apify run {run_id} returned {len(items)} items")
        return items

    except Exception as e:
        logger.error(f"Apify _run_actor error ({actor_id}): {e}")
        return []


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_profile_stats(profile_url: str) -> dict:
    """
    Fetch LinkedIn profile stats (followers, connections, headline, name).
    Returns a dict; {} on failure.

    Input actor: harvestapi~linkedin-profile-scraper
    Input format: {"queries": [<profile_url_or_vanity_id>]}
    """
    if not profile_url:
        logger.info("Apify profile sync: profile_url not provided — skipping")
        return {}

    items = _run_actor(
        ACTOR_PROFILE,
        {"queries": [profile_url], "profileScraperMode": "Profile details no email ($4 per 1k)"},
    )
    if not items:
        logger.warning(f"Apify profile sync: no data returned for {profile_url}")
        return {}

    item = items[0]
    # harvestapi field names (verified from live actor output):
    # followerCount (no 's'), connectionsCount, firstName+lastName (no fullName)
    first = item.get("firstName", "")
    last  = item.get("lastName",  "")
    name  = (first + " " + last).strip() or item.get("name", item.get("fullName", ""))
    return {
        "followers":    item.get("followerCount",    item.get("followersCount",   item.get("followers",    0))),
        "connections":  item.get("connectionsCount", item.get("connections",  0)),
        "name":         name,
        "headline":     item.get("headline",         ""),
        "profile_url":  profile_url,
        "synced_at":    _dt.datetime.utcnow().isoformat() + "Z",
        "source":       "apify",
    }


def get_feed_targets(target_profile_urls: List[str], max_posts: int = 5,
                     time_limit: str = "24h") -> List[dict]:
    """
    Scrape recent posts from target LinkedIn profiles.
    Returns a list of post dicts suitable for Claude engagement targeting.

    Input actor: harvestapi~linkedin-profile-posts
    Input: {"targetUrls": [...], "maxPosts": N, "postedLimit": "24h"|"week"|"month"}
    """
    if not target_profile_urls:
        return []

    items = _run_actor(
        ACTOR_POSTS,
        {
            "targetUrls":        target_profile_urls,
            "maxPosts":          max_posts,
            "postedLimit":       time_limit,
            "scrapeComments":    False,
            "scrapeReactions":   False,
            "includeReposts":    False,
        },
    )

    targets = []
    for item in items:
        author_raw = item.get("author", {})
        author_name = (
            author_raw.get("name", "")
            if isinstance(author_raw, dict)
            else str(author_raw)
        )
        # harvestapi field names (verified from live actor output):
        # post URL -> linkedinUrl, text -> content, engagement -> nested obj
        post_url = item.get("linkedinUrl", item.get("url", item.get("postUrl", "")))
        engagement = item.get("engagement", {}) if isinstance(item.get("engagement"), dict) else {}
        posted_at_raw = item.get("postedAt", item.get("date", ""))
        posted_at = (
            posted_at_raw.get("date", "") if isinstance(posted_at_raw, dict) else posted_at_raw
        )
        targets.append({
            "post_url":   post_url,
            "author":     author_name,
            "author_url": (author_raw.get("linkedinUrl", author_raw.get("url", "")) if isinstance(author_raw, dict) else ""),
            "text":       item.get("content", item.get("text", ""))[:500],
            "likes":      engagement.get("likes",    item.get("likeCount",    item.get("numLikes",    0))),
            "comments":   engagement.get("comments", item.get("commentCount", item.get("numComments", 0))),
            "shares":     engagement.get("shares",   item.get("repostCount",  item.get("numShares",   0))),
            "posted_at":  posted_at,
        })

    logger.info(f"Apify feed_targets: fetched {len(targets)} posts from {len(target_profile_urls)} profiles")
    return targets


def get_post_stats(post_urns: List[str]) -> Dict[str, dict]:
    """
    Get engagement stats (likes, comments, shares, views) for specific post URNs.
    Uses harvestapi~linkedin-profile-posts with direct post URLs.
    Returns {urn: {likes, comments, shares, views}} dict.
    """
    if not post_urns:
        return {}

    post_urls   = [urn_to_url(u) for u in post_urns]
    url_to_urn  = {url: urn for urn, url in zip(post_urns, post_urls)}

    items = _run_actor(
        ACTOR_POSTS,
        {
            "targetUrls":      post_urls,
            "maxPosts":        len(post_urls),
            "scrapeComments":  False,
            "scrapeReactions": False,
        },
    )

    results = {urn: {} for urn in post_urns}
    for item in items:
        item_url = item.get("linkedinUrl", item.get("url", item.get("postUrl", "")))
        matching_urn = None
        for url, urn in url_to_urn.items():
            if url in item_url or item_url in url:
                matching_urn = urn
                break
        if not matching_urn and len(post_urns) == 1:
            matching_urn = post_urns[0]
        if not matching_urn:
            continue

        eng = item.get("engagement", {}) if isinstance(item.get("engagement"), dict) else {}
        results[matching_urn] = {
            "likes":    eng.get("likes",    item.get("likeCount",    item.get("likes",    0))),
            "comments": eng.get("comments", item.get("commentCount", item.get("comments", 0))),
            "shares":   eng.get("shares",   item.get("repostCount",  item.get("shares",   0))),
            "views":    item.get("viewCount", item.get("views", 0)),
        }

    return results


def get_post_comments(post_urns: List[str], limit: int = 50) -> Dict[str, dict]:
    """
    Scrape comments + reactions for specific post URNs.
    Returns {urn: {comments: [...], total_comments: N}} dict.
    """
    if not post_urns:
        return {}

    post_urls   = [urn_to_url(u) for u in post_urns]
    url_to_urn  = {url: urn for urn, url in zip(post_urns, post_urls)}

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
                "id":             item.get("comment_id", ""),
                "text":           item.get("text", ""),
                "author":         item.get("author", {}).get("name", ""),
                "author_profile": item.get("author", {}).get("profile_url", ""),
                "created_at":     item.get("posted_at", {}).get("date", ""),
                "likes":          item.get("stats",  {}).get("total_reactions", 0),
                "replies":        item.get("replies", []),
            })

        tc = item.get("totalComments", 0)
        if tc:
            results[matching_urn]["total_comments"] = tc

    return results


def sync_all_post_data(post_urns: List[str], limit_comments: int = 30) -> Dict[str, dict]:
    """
    Full sync: comments + stats for each post URN.
    Returns merged {urn: {comments, total_comments, stats}} dict.
    """
    if not post_urns:
        return {}

    logger.info(f"Apify: full sync for {len(post_urns)} posts (comments + stats)")
    comments_data = get_post_comments(post_urns, limit=limit_comments)
    stats_data    = get_post_stats(post_urns)

    merged = {}
    for urn in post_urns:
        merged[urn] = {
            **comments_data.get(urn, {"comments": [], "total_comments": 0}),
            "stats": stats_data.get(urn, {}),
        }
    return merged
