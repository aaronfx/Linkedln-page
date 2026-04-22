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

    # Ã¢ÂÂÃ¢ÂÂÃ¢ÂÂ Data Collection Ã¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂ

    def collect_metrics(self):
        """Collect latest metrics for recent posts only (last 7 days).
        Was collecting for ALL posts Ã¢ÂÂ caused hundreds of unnecessary API calls.
        """
        logger.info("Collecting post metrics (last 7 days only)...")
        updated_count = 0
        cutoff = datetime.now(timezone.utc) - timedelta(days=7)

        for post in self.post_history:
            post_id = post.get("id")
            if not post_id:
                continue

            # Skip old posts Ã¢ÂÂ no need to re-fetch their stats constantly
            created_at = post.get("created_at", "")
            if created_at:
                try:
                    post_date = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                    if post_date < cutoff:
                        continue
                except (ValueError, TypeError):
                    pass

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

    # Ã¢ÂÂÃ¢ÂÂÃ¢ÂÂ Analysis Ã¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂ

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

    # Ã¢ÂÂÃ¢ÂÂÃ¢ÂÂ Reports Ã¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂ

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

    # Ã¢ÂÂÃ¢ÂÂÃ¢ÂÂ Utility Ã¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂ

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

    # --- Performance Intelligence Loop ---

    def detect_winners(self, threshold_multiplier=2.0):
        """Identify viral posts with engagement significantly above average."""
        if not self.post_history:
            return []

        # Calculate average engagement
        total_likes = 0
        total_comments = 0
        counted = 0
        for p in self.post_history:
            stats = p.get("stats", {})
            if stats:
                total_likes += stats.get("likes", 0)
                total_comments += stats.get("comments", 0)
                counted += 1

        if counted == 0:
            return []

        avg_likes = total_likes / counted
        avg_comments = total_comments / counted
        avg_engagement = avg_likes + avg_comments

        # Find posts that exceed threshold
        winners = []
        for p in self.post_history:
            stats = p.get("stats", {})
            if not stats:
                continue
            likes = stats.get("likes", 0)
            comments = stats.get("comments", 0)
            engagement = likes + comments

            if engagement > avg_engagement * threshold_multiplier:
                winners.append({
                    "post": p,
                    "likes": likes,
                    "comments": comments,
                    "engagement_score": engagement,
                    "vs_average": round(engagement / max(avg_engagement, 1), 1),
                    "pillar": p.get("pillar", "unknown"),
                    "template": p.get("template", "unknown"),
                    "hook": (p.get("content", "")[:80] + "...") if p.get("content") else "",
                    "posted_at": p.get("created_at", "unknown")
                })

        winners.sort(key=lambda w: w["engagement_score"], reverse=True)
        logger.info(f"Detected {len(winners)} winner posts (>{threshold_multiplier}x avg engagement)")
        return winners

    def get_performance_insights(self):
        """Analyze all posts and generate actionable insights for content generation."""
        if not self.post_history:
            return {"insights_text": "No post history yet. Creating baseline content.", "winners": [], "pillar_ranking": [], "template_ranking": []}

        # Collect fresh metrics first
        self.collect_metrics()

        # Analyze by pillar
        pillar_stats = {}
        for p in self.post_history:
            pillar = p.get("pillar", "unknown")
            stats = p.get("stats", {})
            if pillar not in pillar_stats:
                pillar_stats[pillar] = {"total_likes": 0, "total_comments": 0, "count": 0}
            pillar_stats[pillar]["total_likes"] += stats.get("likes", 0)
            pillar_stats[pillar]["total_comments"] += stats.get("comments", 0)
            pillar_stats[pillar]["count"] += 1

        pillar_ranking = []
        for pillar, s in pillar_stats.items():
            avg_eng = (s["total_likes"] + s["total_comments"]) / max(s["count"], 1)
            pillar_ranking.append({"pillar": pillar, "avg_engagement": round(avg_eng, 1), "post_count": s["count"]})
        pillar_ranking.sort(key=lambda x: x["avg_engagement"], reverse=True)

        # Analyze by template
        template_stats = {}
        for p in self.post_history:
            template = p.get("template", "unknown")
            stats = p.get("stats", {})
            if template not in template_stats:
                template_stats[template] = {"total_likes": 0, "total_comments": 0, "count": 0}
            template_stats[template]["total_likes"] += stats.get("likes", 0)
            template_stats[template]["total_comments"] += stats.get("comments", 0)
            template_stats[template]["count"] += 1

        template_ranking = []
        for tmpl, s in template_stats.items():
            avg_eng = (s["total_likes"] + s["total_comments"]) / max(s["count"], 1)
            template_ranking.append({"template": tmpl, "avg_engagement": round(avg_eng, 1), "post_count": s["count"]})
        template_ranking.sort(key=lambda x: x["avg_engagement"], reverse=True)

        # Detect winners
        winners = self.detect_winners()

        # Extract top hooks from winners
        top_hooks = [w["hook"] for w in winners[:5]]

        # Build natural language insights
        insights_parts = []
        insights_parts.append("PERFORMANCE INTELLIGENCE REPORT:")

        if pillar_ranking:
            best = pillar_ranking[0]
            worst = pillar_ranking[-1] if len(pillar_ranking) > 1 else None
            insights_parts.append(f"- Best performing content pillar: {best['pillar']} (avg {best['avg_engagement']} engagement per post)")
            if worst and worst['pillar'] != best['pillar']:
                insights_parts.append(f"- Lowest performing pillar: {worst['pillar']} (avg {worst['avg_engagement']} engagement) - consider refreshing approach")

        if template_ranking:
            best_t = template_ranking[0]
            insights_parts.append(f"- Best performing template: {best_t['template']} (avg {best_t['avg_engagement']} engagement)")

        if winners:
            insights_parts.append(f"- {len(winners)} viral posts detected (2x+ above average)")
            for w in winners[:3]:
                insights_parts.append(f"  * [{w['pillar']}/{w['template']}] {w['hook']} ({w['likes']} likes, {w['comments']} comments)")

        if top_hooks:
            insights_parts.append("- Top performing hooks/openings to emulate:")
            for h in top_hooks:
                insights_parts.append(f"  * {h}")

        insights_parts.append("\nACTION: Generate more content using the best-performing pillars, templates, and hook styles listed above.")

        insights_text = "\n".join(insights_parts)

        result = {
            "insights_text": insights_text,
            "winners": winners,
            "pillar_ranking": pillar_ranking,
            "template_ranking": template_ranking,
            "top_hooks": top_hooks
        }

        # Save insights to file for content engine to pick up
        insights_file = Path(ANALYTICS_DIR) / "performance_insights.json"
        try:
            import json as json_mod
            with open(insights_file, "w") as f:
                json_mod.dump(result, f, indent=2, default=str)
            logger.info(f"Performance insights saved to {insights_file}")
        except Exception as e:
            logger.error(f"Failed to save insights: {e}")

        return result

    def check_recent_performance(self, hours_ago=24):
        """Check metrics for recently published posts and flag winners early."""
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours_ago)
        recent = []
        for p in self.post_history:
            created = p.get("created_at", "")
            if created:
                try:
                    dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
                    if dt > cutoff:
                        recent.append(p)
                except (ValueError, TypeError):
                    pass

        if not recent:
            logger.info(f"No posts found in the last {hours_ago} hours")
            return []

        # Refresh stats for recent posts
        if self.linkedin:
            for p in recent:
                urn = p.get("urn")
                if urn:
                    try:
                        stats = self.linkedin.get_post_stats(urn)
                        if stats:
                            p["stats"] = stats
                    except Exception as e:
                        logger.error(f"Failed to get stats for {urn}: {e}")

            # Save updated history
            self._save_history()

        # Flag early winners (lower threshold for recent posts)
        flagged = []
        for p in recent:
            stats = p.get("stats", {})
            likes = stats.get("likes", 0)
            comments = stats.get("comments", 0)
            if likes >= 10 or comments >= 5:
                flagged.append({
                    "urn": p.get("urn"),
                    "content_preview": (p.get("content", "")[:80] + "...") if p.get("content") else "",
                    "likes": likes,
                    "comments": comments,
                    "pillar": p.get("pillar", "unknown"),
                    "hours_old": hours_ago
                })
                logger.info(f"Early winner flagged: {likes} likes, {comments} comments - {p.get('pillar')}")

        return flagged

    def _save_history(self):
        """Save updated post history back to file."""
        history_file = Path("data/post_history.json")
        try:
            import json as json_mod
            with open(history_file, "w") as f:
                json_mod.dump(self.post_history, f, indent=2, default=str)
        except Exception as e:
            logger.error(f"Failed to save post history: {e}")


    def track_follower_growth(self):
        """Track follower count and record in learning engine."""
        try:
            if not self.linkedin:
                return None
            
            count = self.linkedin.get_follower_count()
            if count > 0:
                try:
                    from learning_engine import LearningEngine
                    le = LearningEngine()
                    le.record_follower_snapshot(count)
                    logger.info(f"Follower count recorded: {count}")
                except ImportError:
                    pass
            return count
        except Exception as e:
            logger.error(f"Failed to track followers: {e}")
            return None

    def get_hashtag_performance(self) -> dict:
        """Analyze which hashtags correlate with higher engagement."""
        hashtag_stats = {}
        
        for post in self.post_history:
            hashtags = post.get("hashtags", [])
            if isinstance(hashtags, str):
                import re
                hashtags = re.findall(r'#(\w+)', hashtags)
            
            engagement = (
                post.get("likes", 0) + 
                post.get("comments", 0) * 3 +  # Comments weighted 3x
                post.get("shares", 0) * 5       # Shares weighted 5x
            )
            
            for tag in hashtags:
                tag = tag.lower().strip('#')
                if tag not in hashtag_stats:
                    hashtag_stats[tag] = {"uses": 0, "total_engagement": 0, "avg_engagement": 0}
                hashtag_stats[tag]["uses"] += 1
                hashtag_stats[tag]["total_engagement"] += engagement
        
        # Calculate averages and sort
        for tag, stats in hashtag_stats.items():
            if stats["uses"] > 0:
                stats["avg_engagement"] = round(stats["total_engagement"] / stats["uses"], 1)
        
        sorted_tags = dict(sorted(
            hashtag_stats.items(), 
            key=lambda x: x[1]["avg_engagement"], 
            reverse=True
        ))
        
        return sorted_tags

    def get_engagement_by_time(self) -> dict:
        """Analyze engagement patterns by posting time (hour of day in WAT)."""
        time_stats = {}
        
        for post in self.post_history:
            created = post.get("created_at", "")
            if not created:
                continue
            
            try:
                if isinstance(created, str):
                    dt = datetime.fromisoformat(created.replace('Z', '+00:00'))
                else:
                    dt = created
                
                # Convert UTC to WAT (UTC+1)
                wat_hour = (dt.hour + 1) % 24
                hour_key = f"{wat_hour:02d}:00"
                
                engagement = (
                    post.get("likes", 0) + 
                    post.get("comments", 0) * 3 + 
                    post.get("shares", 0) * 5
                )
                
                if hour_key not in time_stats:
                    time_stats[hour_key] = {"posts": 0, "total_engagement": 0, "avg_engagement": 0}
                time_stats[hour_key]["posts"] += 1
                time_stats[hour_key]["total_engagement"] += engagement
            except (ValueError, TypeError):
                continue
        
        # Calculate averages
        for hour, stats in time_stats.items():
            if stats["posts"] > 0:
                stats["avg_engagement"] = round(stats["total_engagement"] / stats["posts"], 1)
        
        # Sort by hour
        sorted_times = dict(sorted(time_stats.items()))
        return sorted_times

    def get_enhanced_insights(self) -> dict:
        """Get comprehensive analytics insights including new tracking."""
        insights = self.get_performance_insights()
        insights["hashtag_performance"] = self.get_hashtag_performance()
        insights["engagement_by_time"] = self.get_engagement_by_time()
        
        # Add follower tracking if available
        follower_count = self.track_follower_growth()
        if follower_count:
            insights["current_followers"] = follower_count
        
        return insights
