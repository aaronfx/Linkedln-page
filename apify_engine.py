"""
Apify integration -- LinkedIn metrics, profile scraping, and feed targeting.

Replaces the broken LinkedIn read API (r_member_social scope / hanging calls).

Actors (harvestapi -- 4.8-4.9 stars, 99.9% success rate):
  harvestapi~linkedin-profile-scraper   -> profile stats: followers, connections, headline
  harvestapi~linkedin-profile-posts     -> recent posts per profile (feed targeting + post stats)
  apimaestro~linkedin-post-comments-replies-engagements-scraper-no-cookies -> comments + reactions
"""
import os
import time
import logging
import datetime as _dt
import requests as _requests

logger = logging.getLogger(__name__)

APIFY_BASE = "https://api.apify.com/v2"
ACTOR_PROFILE  = "harvestapi~linkedin-profile-scraper"
ACTOR_POSTS    = "harvestapi~linkedin-profile-posts"
ACTOR_COMMENTS = "apimaestro~linkedin-post-comments-replies-engagements-scraper-no-cookies"


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
    """Start actor, poll until done, return dataset items. Returns [] on any failure."""
    api_key = _api_key()
    if not api_key:
        logger.warning("APIFY_API_KEY not configured -- skipping Apify call")
        return []
    try:
        run_resp = _requests.post(
            f"{APIFY_BASE}/acts/{actor_id}/runs",
            params={"token": api_key}, json=payload, timeout=30,
        )
        run_resp.raise_for_status()
        run_data   = run_resp.json().get("data", {})
        run_id     = run_data.get("id")
        dataset_id = run_data.get("defaultDatasetId")
        if not run_id:
            logger.error(f"Apify: no runId from {actor_id}: {run_resp.text[:300]}")
            return []
        logger.info(f"Apify run started: {run_id}  actor={actor_id}")
        poll_url = f"{APIFY_BASE}/actor-runs/{run_id}"
        deadline = time.time() + timeout_s
        status   = "RUNNING"
        while time.time() < deadline:
            time.sleep(10)
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
            params={"token": api_key, "format": "json", "clean": "true"}, timeout=30,
        )
        items = items_resp.json() if items_resp.ok else []
        logger.info(f"Apify run {run_id} returned {len(items)} items")
        return items
    except Exception as e:
        logger.error(f"Apify _run_actor error ({actor_id}): {e}")
        return []


def get_profile_stats(profile_url):
    """Fetch LinkedIn profile stats (followers, connections, headline). Returns {} on failure."""
    if not profile_url:
        return {}
    items = _run_actor(
        ACTOR_PROFILE,
        {"queries": [profile_url], "profileScraperMode": "Profile details no email ($4 per 1k)"},
    )
    if not items:
        logger.warning(f"Apify profile sync: no data for {profile_url}")
        return {}
    item = items[0]
    return {
        "followers":   item.get("followersCount",   item.get("followers",    0)),
        "connections": item.get("connectionsCount", item.get("connections",  0)),
        "name":        item.get("fullName",         item.get("name",         "")),
        "headline":    item.get("headline",         ""),
        "profile_url": profile_url,
        "synced_at":   _dt.datetime.utcnow().isoformat() + "Z",
        "source":      "apify",
    }


def get_feed_targets(target_profile_urls, max_posts=5, time_limit="24h"):
    """Scrape recent posts from target profiles for Claude engagement targeting."""
    if not target_profile_urls:
        return []
    items = _run_actor(
        ACTOR_POSTS,
        {
            "targetUrls": target_profile_urls, "maxPosts": max_posts, "postedLimit": time_limit,
            "scrapeComments": False, "scrapeReactions": False, "includeReposts": False,
        },
    )
    targets = []
    for item in items:
        author_raw  = item.get("author", {})
        author_name = (author_raw.get("name", "") if isinstance(author_raw, dict) else str(author_raw))
        post_url    = item.get("url", item.get("postUrl", item.get("linkedinUrl", "")))
        targets.append({
            "post_url":   post_url,
            "author":     author_name,
            "author_url": (author_raw.get("url", "") if isinstance(author_raw, dict) else ""),
            "text":       item.get("text", item.get("content", ""))[:500],
            "likes":      item.get("likeCount",    item.get("numLikes",    0)),
            "comments":   item.get("commentCount", item.get("numComments", 0)),
            "shares":     item.get("repostCount",  item.get("numShares",   0)),
            "posted_at":  item.get("postedAt",     item.get("date",        "")),
        })
    logger.info(f"Apify feed_targets: {len(targets)} posts from {len(target_profile_urls)} profiles")
    return targets


def get_post_stats(post_urns):
    """Get engagement stats for post URNs. Returns {urn: {likes, comments, shares, views}}."""
    if not post_urns:
        return {}
    post_urls  = [urn_to_url(u) for u in post_urns]
    url_to_urn = {url: urn for urn, url in zip(post_urns, post_urls)}
    items      = _run_actor(ACTOR_POSTS, {"targetUrls": post_urls, "maxPosts": len(post_urls), "scrapeComments": False, "scrapeReactions": False})
    results    = {urn: {} for urn in post_urns}
    for item in items:
        item_url = item.get("url", item.get("postUrl", item.get("linkedinUrl", "")))
        match    = next((urn for url, urn in url_to_urn.items() if url in item_url or item_url in url), None)
        if not match and len(post_urns) == 1: match = post_urns[0]
        if not match: continue
        results[match] = {
            "likes":    item.get("likeCount",    item.get("likes",    0)),
            "comments": item.get("commentCount", item.get("comments", 0)),
            "shares":   item.get("repostCount",  item.get("shares",   0)),
            "views":    item.get("viewCount",    item.get("views",    0)),
        }
    return results


def get_post_comments(post_urns, limit=50):
    """Scrape comments for post URNs. Returns {urn: {comments, total_comments}}."""
    if not post_urns:
        return {}
    post_urls  = [urn_to_url(u) for u in post_urns]
    url_to_urn = {url: urn for urn, url in zip(post_urns, post_urls)}
    items      = _run_actor(ACTOR_COMMENTS, {"postIds": post_urls, "sortOrder": "most recent", "limit": limit})
    results    = {urn: {"comments": [], "total_comments": 0} for urn in post_urns}
    for item in items:
        if "summary" in item: continue
        post_input = item.get("post_input", "")
        match      = next((urn for url, urn in url_to_urn.items() if url in post_input or post_input in url), None)
        if not match:
            if len(post_urns) == 1: match = post_urns[0]
            else: continue
        if item.get("text") or item.get("comment_id"):
            results[match]["comments"].append({
                "id": item.get("comment_id", ""), "text": item.get("text", ""),
                "author": item.get("author", {}).get("name", ""),
                "author_profile": item.get("author", {}).get("profile_url", ""),
                "created_at": item.get("posted_at", {}).get("date", ""),
                "likes": item.get("stats", {}).get("total_reactions", 0),
                "replies": item.get("replies", []),
            })
        if item.get("totalComments"): results[match]["total_comments"] = item["totalComments"]
    return results


def sync_all_post_data(post_urns, limit_comments=30):
    """Full sync: comments + stats per post URN."""
    if not post_urns: return {}
    comments_data = get_post_comments(post_urns, limit=limit_comments)
    stats_data    = get_post_stats(post_urns)
    return {urn: {**comments_data.get(urn, {"comments": [], "total_comments": 0}), "stats": stats_data.get(urn, {})} for urn in post_urns}
