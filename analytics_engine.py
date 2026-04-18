"""
Analytics Engine
=================
Tracks post performance, identifies patterns, and generates optimization reports.
"""

import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from config import (
    ANALYTICS_FILE, POST_HISTORY_FILE, ANALYTICS_SETTINGS, ANALYTICS_DIR
)
from linkedin_api import LinkedInAPI
from content_engine import analyze_performance

logger = logging.getLogger("analytics")


class AnalyticsEngine:
    """Tracks and analyzes LinkedIn post performance."""

    def __init__(self, linkedin: LinkedInAPI = None):
        self.linkedin = linkedin or LinkedInAPI()
        self.analytics = self._load_json(ANALYTICS_FILE, {"posts": [], "reports": []})
        self.post_history = self._load_json(POST_HISTORY_FILE, [])

    # ─── Data Collection ────────────────────────────────────

    def collect_metrics(self):
        """Collect latest metrics for all tracked posts."""
        logger.info("Collecting post metrics...")
        updated_count = 0

        for post in self.post_history:
            post_id = post.get("id")
            if not post_id:
                continue

            try:
                stats = self.linkedin.get_post_stats(post_id)
                post["metrics"] = stats
                post["metrics_updated"] = datetime.now(timezone.utc).isoformat()

                # Calculate engagement rate
                impressions = stats.get("impressions", 0)
                if impressions > 0:
                    total_engagement = (
                        stats.get("likes", 0)
                        + stats.get("comments", 0) * 3  # Comments weighted 3x
                        + stats.get("shares", 0) * 5    # Shares weighted 5x
                    )
                    post["engagement_rate"] = round(total_engagement / impressions * 100, 2)
                else:
                    post["engagement_rate"] = 0.0

                updated_count += 1

            except Exception as e:
                logger.error(f"Failed to get metrics for {post_id}: {e}")

        self._save_json(POST_HISTORY_FILE, self.post_history)
        logger.info(f"Updated metrics for {updated_count} posts")
        return updated_count

    # ─── Analysis ───────────────────────────────────────────

    def get_top_posts(self, n: int = 5, days: int = 30) -> list:
        """Get top-performing posts by engagement rate."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)

        recent_posts = [
            p for p in self.post_history
            if p.get("created_at") and
            datetime.fromisoformat(p["created_at"].replace("Z", "+00:00")) > cutoff
        ]

        sorted_posts = sorted(
            recent_posts,
            key=lambda p: p.get("engagement_rate", 0),
            reverse=True,
        )

        return sorted_posts[:n]

    def get_pillar_performance(self) -> dict:
        """Get average performance by content pillar."""
        pillar_stats = {}

        for post in self.post_history:
            pillar = post.get("pillar", "Unknown")
            if pillar not in pillar_stats:
                pillar_stats[pillar] = {
                    "count": 0,
                    "total_impressions": 0,
                    "total_likes": 0,
                    "total_comments": 0,
                    "total_shares": 0,
                    "total_engagement_rate": 0,
                }

            stats = pillar_stats[pillar]
            metrics = post.get("metrics", {})
            stats["count"] += 1
            stats["total_impressions"] += metrics.get("impressions", 0)
            stats["total_likes"] += metrics.get("likes", 0)
            stats["total_comments"] += metrics.get("comments", 0)
            stats["total_shares"] += metrics.get("shares", 0)
            stats["total_engagement_rate"] += post.get("engagement_rate", 0)

        # Calculate averages
        for pillar, stats in pillar_stats.items():
            count = stats["count"]
            if count > 0:
                stats["avg_impressions"] = round(stats["total_impressions"] / count)
                stats["avg_likes"] = round(stats["total_likes"] / count)
                stats["avg_comments"] = round(stats["total_comments"] / count, 1)
                stats["avg_shares"] = round(stats["total_shares"] / count, 1)
                stats["avg_engagement_rate"] = round(stats["total_engagement_rate"] / count, 2)

        return pillar_stats

    def get_time_performance(self) -> dict:
        """Analyze which posting times get best engagement."""
        time_stats = {}

        for post in self.post_history:
            created = post.get("created_at", "")
            if not created:
                continue

            try:
                dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
                hour = dt.hour
                day = dt.strftime("%A")
                key = f"{day} {hour:02d}:00"
            except ValueError:
                continue

            if key not in time_stats:
                time_stats[key] = {"count": 0, "total_engagement": 0}

            time_stats[key]["count"] += 1
            time_stats[key]["total_engagement"] += post.get("engagement_rate", 0)

        # Calculate averages
        for key, stats in time_stats.items():
            if stats["count"] > 0:
                stats["avg_engagement"] = round(stats["total_engagement"] / stats["count"], 2)

        return dict(sorted(
            time_stats.items(),
            key=lambda x: x[1].get("avg_engagement", 0),
            reverse=True,
        ))

    # ─── Reports ────────────────────────────────────────────

    def generate_weekly_report(self) -> dict:
        """Generate a comprehensive weekly performance report using Claude."""
        # Collect fresh metrics
        self.collect_metrics()

        # Get recent posts (last 7 days)
        cutoff = datetime.now(timezone.utc) - timedelta(days=7)
        recent_posts = [
            p for p in self.post_history
            if p.get("created_at") and
            datetime.fromisoformat(p["created_at"].replace("Z", "+00:00")) > cutoff
        ]

        if not recent_posts:
            logger.warning("No posts found in the last 7 days")
            return {"error": "No recent posts to analyze"}

        # Claude-powered analysis
        analysis = analyze_performance(recent_posts)

        # Add our own calculated metrics
        analysis["period"] = {
            "start": cutoff.isoformat(),
            "end": datetime.now(timezone.utc).isoformat(),
        }
        analysis["pillar_breakdown"] = self.get_pillar_performance()
        analysis["time_performance"] = self.get_time_performance()
        analysis["top_posts"] = [
            {
                "text_preview": p.get("text", "")[:150],
                "engagement_rate": p.get("engagement_rate", 0),
                "impressions": p.get("metrics", {}).get("impressions", 0),
                "pillar": p.get("pillar", "Unknown"),
            }
            for p in self.get_top_posts(3, 7)
        ]

        # Save report
        report_filename = f"report_{datetime.now().strftime('%Y%m%d')}.json"
        report_path = ANALYTICS_DIR / report_filename
        self._save_json(report_path, analysis)

        # Append to analytics history
        self.analytics["reports"].append({
            "date": datetime.now(timezone.utc).isoformat(),
            "file": report_filename,
            "posts_analyzed": len(recent_posts),
        })
        self._save_json(ANALYTICS_FILE, self.analytics)

        logger.info(f"Weekly report saved: {report_path}")
        return analysis

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
