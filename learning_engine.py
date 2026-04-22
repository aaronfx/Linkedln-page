"""
Learning Engine
================
Persistent learning model that remembers what works.
Stores insights about best hooks, optimal lengths, top hashtags,
best posting times, and content patterns that drive growth.

This is the brain's memory - without it, the system forgets
everything it learns between restarts.
"""

import json
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path
from filelock import FileLock

from config import DATA_DIR

logger = logging.getLogger("learning_engine")

LEARNING_STATE_FILE = DATA_DIR / "learning_state.json"
LEARNING_LOCK = FileLock(str(LEARNING_STATE_FILE) + ".lock", timeout=10)

DEFAULT_STATE = {
    "version": 1,
    "last_updated": None,
    "follower_snapshots": [],
    "best_hooks": [],
    "best_hashtags": {},
    "best_posting_times": {},
    "optimal_post_length": {"min": 800, "max": 1500, "sweet_spot": 1100},
    "top_performing_pillars": {},
    "top_performing_formats": {},
    "engagement_patterns": {
        "best_day_of_week": None,
        "best_hour_of_day": None,
        "avg_engagement_rate": 0,
    },
    "content_insights": [],
    "dead_letter_queue": [],
    "system_health": {
        "last_successful_post": None,
        "last_failed_post": None,
        "consecutive_failures": 0,
        "token_expiry_warning": False,
        "alerts": [],
    },
    "ab_test_results": [],
}


def _load_state():
    """Load learning state from disk with file locking."""
    with LEARNING_LOCK:
        if LEARNING_STATE_FILE.exists():
            try:
                with open(LEARNING_STATE_FILE) as f:
                    state = json.load(f)
                # Merge with defaults for any missing keys
                for key, val in DEFAULT_STATE.items():
                    if key not in state:
                        state[key] = val
                return state
            except (json.JSONDecodeError, Exception) as e:
                logger.error(f"Failed to load learning state: {e}")
                return DEFAULT_STATE.copy()
        return DEFAULT_STATE.copy()


def _save_state(state):
    """Save learning state to disk with file locking."""
    state["last_updated"] = datetime.now(timezone.utc).isoformat()
    with LEARNING_LOCK:
        with open(LEARNING_STATE_FILE, "w") as f:
            json.dump(state, f, indent=2, default=str)


def record_post_result(post_text, pillar, format_type, success, error_msg=None, post_id=None):
    """Record whether a post succeeded or failed."""
    state = _load_state()

    if success:
        state["system_health"]["last_successful_post"] = datetime.now(timezone.utc).isoformat()
        state["system_health"]["consecutive_failures"] = 0

        # Track pillar performance
        if pillar:
            state["top_performing_pillars"].setdefault(pillar, {"posts": 0, "successes": 0})
            state["top_performing_pillars"][pillar]["posts"] += 1
            state["top_performing_pillars"][pillar]["successes"] += 1

        # Track format performance
        if format_type:
            state["top_performing_formats"].setdefault(format_type, {"posts": 0, "successes": 0})
            state["top_performing_formats"][format_type]["posts"] += 1
            state["top_performing_formats"][format_type]["successes"] += 1

        # Track post length
        post_len = len(post_text) if post_text else 0
        if post_len > 0:
            current = state["optimal_post_length"]
            # Weighted moving average
            current["sweet_spot"] = int(current["sweet_spot"] * 0.8 + post_len * 0.2)

        # Extract and track hook (first line)
        if post_text:
            hook = post_text.split("\n")[0][:100]
            state["best_hooks"].append({
                "hook": hook,
                "posted_at": datetime.now(timezone.utc).isoformat(),
                "post_id": post_id,
            })
            # Keep only last 50 hooks
            state["best_hooks"] = state["best_hooks"][-50:]

        # Track posting time
        now = datetime.now(timezone.utc)
        hour = str(now.hour)
        day = now.strftime("%A")
        state["best_posting_times"].setdefault(hour, {"posts": 0, "day_counts": {}})
        state["best_posting_times"][hour]["posts"] += 1
        state["best_posting_times"][hour]["day_counts"].setdefault(day, 0)
        state["best_posting_times"][hour]["day_counts"][day] += 1

    else:
        state["system_health"]["last_failed_post"] = datetime.now(timezone.utc).isoformat()
        state["system_health"]["consecutive_failures"] += 1

        # Add to dead letter queue
        state["dead_letter_queue"].append({
            "text": post_text[:500] if post_text else "",
            "pillar": pillar,
            "error": str(error_msg)[:200],
            "failed_at": datetime.now(timezone.utc).isoformat(),
            "retry_count": 0,
        })
        # Keep only last 20 failed posts
        state["dead_letter_queue"] = state["dead_letter_queue"][-20:]

        # Add alert if consecutive failures
        if state["system_health"]["consecutive_failures"] >= 3:
            add_alert("HIGH", f"3+ consecutive post failures. Last error: {str(error_msg)[:100]}")

    _save_state(state)


def update_engagement_metrics(post_id, likes, comments, shares, impressions):
    """Update engagement data for a posted piece of content."""
    state = _load_state()

    engagement_rate = 0
    if impressions > 0:
        engagement_rate = round((likes + comments * 2 + shares * 3) / impressions * 100, 2)

    # Update average engagement rate (exponential moving average)
    current_avg = state["engagement_patterns"]["avg_engagement_rate"]
    state["engagement_patterns"]["avg_engagement_rate"] = round(current_avg * 0.7 + engagement_rate * 0.3, 2)

    _save_state(state)


def record_follower_snapshot(count):
    """Record daily follower count for growth tracking."""
    state = _load_state()
    state["follower_snapshots"].append({
        "count": count,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
    })
    # Keep last 365 snapshots
    state["follower_snapshots"] = state["follower_snapshots"][-365:]
    _save_state(state)


def get_growth_rate():
    """Calculate follower growth rate over various periods."""
    state = _load_state()
    snapshots = state["follower_snapshots"]
    if len(snapshots) < 2:
        return {"daily": 0, "weekly": 0, "monthly": 0, "total": 0}

    latest = snapshots[-1]["count"]
    result = {"total": latest}

    if len(snapshots) >= 2:
        result["daily"] = latest - snapshots[-2]["count"]
    if len(snapshots) >= 7:
        result["weekly"] = latest - snapshots[-7]["count"]
    if len(snapshots) >= 30:
        result["monthly"] = latest - snapshots[-30]["count"]

    return result


def track_hashtag_performance(hashtags, impressions, engagement):
    """Track which hashtags drive the most reach."""
    state = _load_state()
    for tag in hashtags:
        tag = tag.strip().lower()
        if not tag.startswith("#"):
            tag = "#" + tag
        state["best_hashtags"].setdefault(tag, {"uses": 0, "total_impressions": 0, "total_engagement": 0})
        state["best_hashtags"][tag]["uses"] += 1
        state["best_hashtags"][tag]["total_impressions"] += impressions
        state["best_hashtags"][tag]["total_engagement"] += engagement
    _save_state(state)


def get_top_hashtags(n=10):
    """Get top performing hashtags by average impressions."""
    state = _load_state()
    hashtags = state["best_hashtags"]
    ranked = []
    for tag, data in hashtags.items():
        if data["uses"] > 0:
            avg_imp = data["total_impressions"] / data["uses"]
            ranked.append({"tag": tag, "avg_impressions": avg_imp, "uses": data["uses"]})
    ranked.sort(key=lambda x: x["avg_impressions"], reverse=True)
    return ranked[:n]


def get_best_posting_times():
    """Analyze actual data to find optimal posting times."""
    state = _load_state()
    times = state["best_posting_times"]
    if not times:
        return {"best_hour": None, "best_day": None}

    best_hour = max(times.keys(), key=lambda h: times[h]["posts"]) if times else None

    # Aggregate days across all hours
    day_totals = {}
    for hour_data in times.values():
        for day, count in hour_data.get("day_counts", {}).items():
            day_totals.setdefault(day, 0)
            day_totals[day] += count
    best_day = max(day_totals.keys(), key=lambda d: day_totals[d]) if day_totals else None

    return {"best_hour": best_hour, "best_day": best_day}


def add_alert(severity, message):
    """Add a system alert."""
    state = _load_state()
    state["system_health"]["alerts"].append({
        "severity": severity,
        "message": message,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "acknowledged": False,
    })
    # Keep last 50 alerts
    state["system_health"]["alerts"] = state["system_health"]["alerts"][-50:]
    _save_state(state)


def get_alerts(unacknowledged_only=True):
    """Get system alerts."""
    state = _load_state()
    alerts = state["system_health"]["alerts"]
    if unacknowledged_only:
        return [a for a in alerts if not a.get("acknowledged")]
    return alerts


def acknowledge_alert(index):
    """Acknowledge an alert by index."""
    state = _load_state()
    if 0 <= index < len(state["system_health"]["alerts"]):
        state["system_health"]["alerts"][index]["acknowledged"] = True
        _save_state(state)


def get_dead_letter_queue():
    """Get failed posts that can be retried."""
    state = _load_state()
    return state["dead_letter_queue"]


def remove_from_dead_letter(index):
    """Remove a post from the dead letter queue (after retry or discard)."""
    state = _load_state()
    if 0 <= index < len(state["dead_letter_queue"]):
        state["dead_letter_queue"].pop(index)
        _save_state(state)


def record_ab_test(post_id, variant, hook_a, hook_b, chosen):
    """Record an A/B test result."""
    state = _load_state()
    state["ab_test_results"].append({
        "post_id": post_id,
        "variant": variant,
        "hook_a": hook_a[:100],
        "hook_b": hook_b[:100],
        "chosen": chosen,
        "tested_at": datetime.now(timezone.utc).isoformat(),
    })
    state["ab_test_results"] = state["ab_test_results"][-100:]
    _save_state(state)


def get_learning_summary():
    """Get a summary of what the system has learned - used by content engine."""
    state = _load_state()

    summary = []

    # Growth rate
    growth = get_growth_rate()
    if growth["total"] > 0:
        summary.append(f"Current followers: {growth['total']}. "
                       f"Growth: +{growth.get('weekly', 0)} this week, +{growth.get('monthly', 0)} this month.")

    # Best formats
    formats = state["top_performing_formats"]
    if formats:
        sorted_formats = sorted(formats.items(), key=lambda x: x[1]["successes"], reverse=True)
        top_formats = [f[0] for f in sorted_formats[:3]]
        summary.append(f"Top performing formats: {', '.join(top_formats)}.")

    # Best pillars
    pillars = state["top_performing_pillars"]
    if pillars:
        sorted_pillars = sorted(pillars.items(), key=lambda x: x[1]["successes"], reverse=True)
        top_pillars = [p[0] for p in sorted_pillars[:3]]
        summary.append(f"Top performing pillars: {', '.join(top_pillars)}.")

    # Optimal length
    length = state["optimal_post_length"]
    summary.append(f"Optimal post length: {length['sweet_spot']} chars (range: {length['min']}-{length['max']}).")

    # Top hashtags
    top_tags = get_top_hashtags(5)
    if top_tags:
        tags = [t["tag"] for t in top_tags]
        summary.append(f"Best hashtags by reach: {', '.join(tags)}.")

    # Best times
    times = get_best_posting_times()
    if times["best_hour"]:
        summary.append(f"Best posting hour (UTC): {times['best_hour']}:00. Best day: {times['best_day'] or 'N/A'}.")

    # Engagement rate
    avg_eng = state["engagement_patterns"]["avg_engagement_rate"]
    if avg_eng > 0:
        summary.append(f"Average engagement rate: {avg_eng}%.")

    # Health status
    health = state["system_health"]
    if health["consecutive_failures"] > 0:
        summary.append(f"WARNING: {health['consecutive_failures']} consecutive post failures.")

    return "\n".join(summary) if summary else "No learning data yet. System is in initial data collection phase."


def check_token_expiry_warning():
    """Check if token expiry warning should be raised."""
    state = _load_state()
    return state["system_health"].get("token_expiry_warning", False)


def set_token_expiry_warning(warning):
    """Set or clear token expiry warning."""
    state = _load_state()
    state["system_health"]["token_expiry_warning"] = warning
    if warning:
        add_alert("CRITICAL", "LinkedIn access token is expiring soon. Please refresh it.")
    _save_state(state)


def backup_to_dict():
    """Export full learning state for backup."""
    return _load_state()


# ═══ Class Wrapper for OOP usage ═══════════════════════════════════

class LearningEngine:
    """
    Object-oriented wrapper around the module-level learning functions.
    Provides the same interface but can be instantiated by worker.py and dashboard.py.
    """

    def record_post_result(self, post_id=None, pillar="", hook="", template="",
                           hashtags=None, success=True, error=None, engagement=None):
        """Record a post result with flexible parameters."""
        record_post_result(
            post_text=hook,
            pillar=pillar,
            format_type=template,
            success=success,
            error_msg=error,
            post_id=post_id,
        )
        # If engagement data provided, update metrics
        if engagement and post_id:
            update_engagement_metrics(
                post_id=post_id,
                likes=engagement.get("likes", 0),
                comments=engagement.get("comments", 0),
                shares=engagement.get("shares", 0),
                impressions=engagement.get("impressions", 0),
            )

    def record_follower_snapshot(self, count):
        record_follower_snapshot(count)

    def get_growth_rate(self):
        return get_growth_rate()

    def track_hashtag_performance(self, hashtag, engagement_score):
        track_hashtag_performance([hashtag], 0, engagement_score)

    def get_top_hashtags(self, n=10):
        return get_top_hashtags(n)

    def get_best_posting_times(self):
        return get_best_posting_times()

    def add_alert(self, severity, message):
        add_alert(severity, message)

    def get_alerts(self, limit=10):
        alerts = get_alerts(unacknowledged_only=False)
        return alerts[:limit] if limit else alerts

    def get_dead_letter_queue(self):
        return get_dead_letter_queue()

    def add_to_dead_letter(self, post_data, error, source="unknown"):
        """Add a failed post to the dead-letter queue."""
        state = _load_state()
        dl_entry = {
            "id": f"dl_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "post_data": post_data,
            "error": error,
            "source": source,
            "failed_at": datetime.now().isoformat(),
            "retry_count": 0,
        }
        state["dead_letter_queue"].append(dl_entry)
        _save_state(state)

    def remove_from_dead_letter(self, item_id):
        """Remove an item from dead-letter queue by ID."""
        state = _load_state()
        state["dead_letter_queue"] = [
            dl for dl in state["dead_letter_queue"]
            if dl.get("id") != item_id
        ]
        _save_state(state)

    def get_learning_summary(self):
        return get_learning_summary()

    def check_token_expiry_warning(self):
        return check_token_expiry_warning()

    def backup_to_dict(self):
        return backup_to_dict()
