"""
Content Engine — Intelligent Growth Machine Powered by Claude
==============================================================
Generates LinkedIn posts, comment replies, and performance analysis
using the Anthropic Claude API.

INTELLIGENCE FEATURES:
- Reads existing content queue to avoid duplicate topics/angles
- Reads full post history to never repeat hooks or stories
- Reads analytics data to double down on what performs best
- Reads comment themes to understand what the audience wants
- Tracks which viral templates were recently used
- Adjusts content strategy based on real performance data
- Assigns real calendar dates to scheduled posts
"""

import json
import random
import logging
from datetime import datetime, timedelta, timezone
from collections import Counter
from anthropic import Anthropic
from config import (
    ANTHROPIC_API_KEY, CLAUDE_SETTINGS, PROFILE,
    CONTENT_PILLARS, CONTENT_QUEUE_FILE, POST_HISTORY_FILE,
    COMMENT_LOG_FILE, ANALYTICS_FILE, ANALYTICS_DIR
)
from knowledge_base import (
    BRAND_VOICE, GROWTH_STRATEGY, VIRAL_TEMPLATES,
    SAMPLE_POSTS, HASHTAG_STRATEGY, ENGAGEMENT_RULES
)
from pathlib import Path

logger = logging.getLogger("content_engine")

client = Anthropic(api_key=ANTHROPIC_API_KEY)


# ─── Context Intelligence Layer ────────────────────────────

def _load_json_safe(path, default=None):
    """Safely load a JSON file, returning default on any error."""
    path = Path(path)
    if path.exists():
        try:
            with open(path) as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return default if default is not None else []


def _get_next_weekday(target_day: str) -> datetime:
    """
    Get the next occurrence of a weekday from today.
    If today IS that weekday, returns today.
    Returns a timezone-aware datetime (UTC).
    """
    days_map = {
        "monday": 0, "tuesday": 1, "wednesday": 2,
        "thursday": 3, "friday": 4, "saturday": 5, "sunday": 6,
    }
    target = days_map.get(target_day.lower(), 0)
    today = datetime.now(timezone.utc)
    today_weekday = today.weekday()

    days_ahead = target - today_weekday
    if days_ahead < 0:
        days_ahead += 7  # Next week

    return today + timedelta(days=days_ahead)


def _build_duplicate_guard(existing_queue: list, post_history: list) -> str:
    """
    Build a context block listing recent topics, hooks, and angles
    so Claude knows exactly what NOT to repeat.
    """
    seen_hooks = []
    seen_topics = []
    seen_pillars_recent = []
    seen_templates = []

    # From existing queue (not yet posted — highest priority to avoid)
    for post in (existing_queue or []):
        hook = post.get("hook", "")
        if hook:
            seen_hooks.append(hook[:120])
        text = post.get("text", "")
        if text:
            seen_topics.append(text[:200])
        pillar = post.get("pillar", "")
        if pillar:
            seen_pillars_recent.append(pillar)
        template = post.get("template_used", "")
        if template:
            seen_templates.append(template)

    # From post history (last 30 posts)
    recent_history = (post_history or [])[-30:]
    for post in recent_history:
        hook = post.get("hook", "")
        if hook:
            seen_hooks.append(hook[:120])
        text = post.get("text", "")
        if text:
            seen_topics.append(text[:200])
        pillar = post.get("pillar", "")
        if pillar:
            seen_pillars_recent.append(pillar)
        template = post.get("template_used", "")
        if template:
            seen_templates.append(template)

    context = ""

    if seen_hooks:
        context += "\n\nHOOKS ALREADY USED (DO NOT repeat or closely paraphrase these):\n"
        for i, hook in enumerate(seen_hooks[-20:], 1):
            context += f"  {i}. {hook}\n"

    if seen_topics:
        context += "\n\nRECENT POST TOPICS (create DIFFERENT angles, stories, and data points):\n"
        for i, topic in enumerate(seen_topics[-15:], 1):
            context += f"  {i}. {topic}...\n"

    if seen_templates:
        template_counts = Counter(seen_templates)
        overused = [t for t, c in template_counts.items() if c >= 2]
        if overused:
            context += f"\n\nOVERUSED TEMPLATES (avoid these): {', '.join(overused)}\n"

    return context


def _build_analytics_intelligence(analytics_data: dict, post_history: list) -> str:
    """
    Build a context block with performance insights so Claude
    can optimize for what actually works.
    """
    context = ""

    # Extract insights from the latest analytics report
    reports_dir = Path(ANALYTICS_DIR)
    latest_report = None
    if reports_dir.exists():
        report_files = sorted(reports_dir.glob("report_*.json"), reverse=True)
        if report_files:
            try:
                with open(report_files[0]) as f:
                    latest_report = json.load(f)
            except (json.JSONDecodeError, IOError):
                pass

    if latest_report:
        summary = latest_report.get("summary", "")
        if summary:
            context += f"\n\nLATEST PERFORMANCE SUMMARY:\n{summary}\n"

        top_pillars = latest_report.get("top_performing_pillars", [])
        if top_pillars:
            context += f"\nBEST PERFORMING PILLARS (lean into these): {', '.join(top_pillars[:3])}\n"

        hook_patterns = latest_report.get("hook_patterns", "")
        if hook_patterns:
            context += f"\nHOOK STYLES THAT WORK BEST: {hook_patterns}\n"

        double_down = latest_report.get("topics_to_double_down", [])
        if double_down:
            context += f"\nTOPICS TO DOUBLE DOWN ON: {', '.join(double_down[:5])}\n"

        avoid = latest_report.get("topics_to_avoid", [])
        if avoid:
            context += f"\nTOPICS THAT UNDERPERFORMED (avoid or reinvent): {', '.join(avoid[:5])}\n"

        optimal_length = latest_report.get("optimal_post_length", "")
        if optimal_length:
            context += f"\nOPTIMAL POST LENGTH: {optimal_length}\n"

        trend = latest_report.get("engagement_trend", "")
        if trend:
            context += f"\nENGAGEMENT TREND: {trend}\n"

        recs = latest_report.get("content_recommendations", [])
        if recs:
            context += "\nAI-GENERATED RECOMMENDATIONS FROM LAST ANALYSIS:\n"
            for rec in recs[:5]:
                context += f"  - {rec}\n"

        suggestions = latest_report.get("next_week_suggestions", [])
        if suggestions:
            context += "\nSUGGESTED TOPICS FROM ANALYTICS:\n"
            for s in suggestions[:3]:
                context += f"  - [{s.get('pillar', '?')}] {s.get('topic_hint', '?')} — {s.get('why', '')}\n"

    # Build pillar performance breakdown from history
    if post_history:
        pillar_stats = {}
        for post in post_history:
            pillar = post.get("pillar", "Unknown")
            engagement = post.get("engagement_rate", 0)
            if pillar not in pillar_stats:
                pillar_stats[pillar] = {"count": 0, "total_engagement": 0, "best_hook": "", "best_engagement": 0}
            pillar_stats[pillar]["count"] += 1
            pillar_stats[pillar]["total_engagement"] += engagement
            if engagement > pillar_stats[pillar]["best_engagement"]:
                pillar_stats[pillar]["best_engagement"] = engagement
                pillar_stats[pillar]["best_hook"] = post.get("hook", post.get("text", "")[:100])

        if pillar_stats:
            context += "\n\nPILLAR PERFORMANCE DATA:\n"
            for pillar, stats in sorted(pillar_stats.items(), key=lambda x: x[1]["total_engagement"], reverse=True):
                avg = stats["total_engagement"] / stats["count"] if stats["count"] > 0 else 0
                context += (
                    f"  {pillar}: {stats['count']} posts, "
                    f"avg engagement {avg:.1f}%, "
                    f"best: {stats['best_engagement']:.1f}%\n"
                )
                if stats["best_hook"]:
                    context += f"    Top hook: \"{stats['best_hook'][:100]}\"\n"

    return context


def _build_comment_intelligence(comment_log: list) -> str:
    """
    Extract audience themes and interests from comment data
    so Claude can write about what people actually care about.
    """
    if not comment_log:
        return ""

    recent_comments = comment_log[-100:]

    questions = []
    appreciation_topics = []
    disagreements = []
    requested_topics = []

    for entry in recent_comments:
        classification = entry.get("classification", {})
        comment_text = entry.get("comment_text", "")
        category = classification.get("category", "")
        sentiment = classification.get("sentiment", "")

        if category == "question" or sentiment == "question":
            questions.append(comment_text[:150])
        elif category == "appreciation":
            appreciation_topics.append(comment_text[:100])
        elif category == "disagreement":
            disagreements.append(comment_text[:100])

        lower = comment_text.lower()
        if any(phrase in lower for phrase in ["can you write about", "post about", "talk about", "cover", "discuss"]):
            requested_topics.append(comment_text[:150])

    context = ""

    if questions:
        context += "\n\nQUESTIONS YOUR AUDIENCE IS ASKING (address these in upcoming posts):\n"
        for q in questions[-10:]:
            context += f"  - {q}\n"

    if requested_topics:
        context += "\n\nTOPICS YOUR AUDIENCE HAS REQUESTED:\n"
        for t in requested_topics[-5:]:
            context += f"  - {t}\n"

    if disagreements:
        context += "\n\nPOINTS OF DISAGREEMENT (opportunity for engaging content):\n"
        for d in disagreements[-5:]:
            context += f"  - {d}\n"

    if appreciation_topics:
        context += f"\n\nMOST APPRECIATED CONTENT THEMES: {len(appreciation_topics)} positive comments recently\n"

    if len(recent_comments) > 0:
        context += f"\nTOTAL COMMENT INTERACTIONS LOGGED: {len(comment_log)}\n"

    return context


def _select_smart_template(existing_queue: list, post_history: list) -> dict:
    """
    Select a viral template intelligently — avoiding recently overused ones.
    """
    recent_templates = []
    for post in (existing_queue or [])[-6:]:
        t = post.get("template_used", "")
        if t:
            recent_templates.append(t)
    for post in (post_history or [])[-10:]:
        t = post.get("template_used", "")
        if t:
            recent_templates.append(t)

    template_counts = Counter(recent_templates)

    weighted_templates = []
    for template in VIRAL_TEMPLATES:
        usage_count = template_counts.get(template["name"], 0)
        weight = max(1, 5 - usage_count)
        weighted_templates.append((template, weight))

    templates, weights = zip(*weighted_templates)
    selected = random.choices(templates, weights=weights, k=1)[0]

    logger.info(f"Smart template selection: {selected['name']} (used {template_counts.get(selected['name'], 0)} times recently)")
    return selected


def _build_growth_phase_context(post_history: list) -> str:
    """Determine current growth phase and provide phase-specific guidance."""
    total_posts = len(post_history) if post_history else 0

    if total_posts < 30:
        phase = "PHASE 1 — Foundation Building"
        guidance = (
            "You are in the FOUNDATION phase. Focus on:\n"
            "  - Establishing authority and voice consistency\n"
            "  - Testing all content pillars to see what resonates\n"
            "  - Creating cornerstone content that can be referenced later\n"
            "  - Building initial engagement patterns\n"
            "  - Every post should introduce who you are and what you stand for"
        )
    elif total_posts < 80:
        phase = "PHASE 2 — Viral Growth"
        guidance = (
            "You are in the VIRAL GROWTH phase. Focus on:\n"
            "  - Doubling down on top-performing pillars and hooks\n"
            "  - Creating more controversial/debate-sparking content\n"
            "  - Leveraging data and stories that invite shares\n"
            "  - Referencing previous posts to build continuity\n"
            "  - Making every hook scroll-stopping"
        )
    else:
        phase = "PHASE 3 — Authority & Scale"
        guidance = (
            "You are in the AUTHORITY phase. Focus on:\n"
            "  - Thought leadership and original frameworks\n"
            "  - Cross-referencing your growing body of work\n"
            "  - More nuanced, experienced takes\n"
            "  - Building series and recurring formats your audience expects\n"
            "  - Collaboration-friendly content that influencers want to engage with"
        )

    return f"\n\nGROWTH PHASE: {phase}\nTotal posts published: {total_posts}\n{guidance}\n"


# ─── Post Generation ────────────────────────────────────────

def generate_post(
    pillar: str = None,
    topic_hint: str = None,
    optimize_from: list = None,
    existing_queue: list = None,
    post_history: list = None,
    analytics_data: dict = None,
    comment_insights: list = None,
) -> dict:
    """
    Generate a LinkedIn post using Claude with FULL context awareness.
    """
    if pillar is None:
        weights = [p["weight"] for p in CONTENT_PILLARS]
        pillar_obj = random.choices(CONTENT_PILLARS, weights=weights, k=1)[0]
        pillar = pillar_obj["name"]
    else:
        pillar_obj = next((p for p in CONTENT_PILLARS if p["name"] == pillar), CONTENT_PILLARS[0])

    # ── Intelligence Layer: Build rich context ──
    duplicate_guard = _build_duplicate_guard(existing_queue, post_history)
    analytics_context = _build_analytics_intelligence(analytics_data, post_history)
    comment_context = _build_comment_intelligence(comment_insights)
    growth_context = _build_growth_phase_context(post_history)
    template = _select_smart_template(existing_queue, post_history)

    optimization_context = ""
    if optimize_from:
        optimization_context = "\n\nTOP-PERFORMING POSTS (learn from their style, hooks, and structure):\n"
        for i, post in enumerate(optimize_from[:5], 1):
            optimization_context += f"\n--- TOP POST {i} (Engagement: {post.get('engagement_rate', 'N/A')}%) ---\n"
            optimization_context += f"Pillar: {post.get('pillar', 'N/A')}\n"
            optimization_context += f"{post.get('text', '')[:500]}\n"

    pillar_samples = [p for p in SAMPLE_POSTS if pillar.lower() in p.get("pillar", "").lower()]
    if not pillar_samples:
        pillar_samples = random.sample(SAMPLE_POSTS, min(3, len(SAMPLE_POSTS)))

    sample_text = "\n\n".join([
        f"--- EXAMPLE POST ({s['pillar']}) ---\n{s['text'][:600]}"
        for s in pillar_samples[:2]
    ])

    system_prompt = f"""You are a LinkedIn ghostwriter for {PROFILE['name']} — and you are an INTELLIGENT GROWTH MACHINE.

You don't just write posts. You analyze what's worked, what hasn't, what the audience is asking for,
and what's already been written — then you craft something ORIGINAL and OPTIMIZED for maximum growth.

{BRAND_VOICE}

PROFILE:
- Title: {PROFILE['title']}
- Company: {PROFILE['company']}
- Niche: {PROFILE['niche']}
- Target Audience: {PROFILE['audience']}
- Tone: {PROFILE['tone']}
{growth_context}

═══════════════════════════════════════════════
INTELLIGENCE BRIEFING — USE THIS TO WRITE BETTER
═══════════════════════════════════════════════
{duplicate_guard}
{analytics_context}
{comment_context}
{optimization_context}
═══════════════════════════════════════════════

VIRAL TEMPLATE TO USE (adapt creatively, don't copy):
Template: "{template['name']}"
Formula: {template['formula']}
Structure:
{template['structure'][:500]}

HASHTAG STRATEGY:
{json.dumps(HASHTAG_STRATEGY['rules'])}
Primary hashtags (use 1): {', '.join(HASHTAG_STRATEGY['primary'])}
Pillar-specific options: {json.dumps(HASHTAG_STRATEGY.get('pillar_specific', {}))}

EXAMPLE POSTS IN MY VOICE (for tone reference only — create FRESH content):
{sample_text}

CRITICAL RULES:
1. Write in first person as {PROFILE['name']}
2. Open with a UNIQUE, powerful hook (first 2 lines are critical — they show before "see more")
3. The hook MUST be completely different from all hooks listed in the Intelligence Briefing above
4. Use short paragraphs (1-3 sentences max)
5. Include a personal story or data point — but make it DIFFERENT from previous posts
6. End with a question or clear CTA to drive comments
7. Add 3-4 relevant hashtags following the hashtag strategy
8. Post length: 1200-2000 characters (LinkedIn sweet spot)
9. NO emojis in the main text (professional tone)
10. Use line breaks generously for readability
11. Reference Gopipways naturally — not forced promotion
12. If analytics show certain topics perform well, lean into those angles
13. If comments show audience questions, address one naturally in your post
14. Use the viral template structure but with COMPLETELY FRESH content
15. NEVER reuse a hook, opening line, or story that appears in the Intelligence Briefing

OUTPUT FORMAT (JSON):
{{
  "text": "The full post text ready to publish",
  "hook": "The opening 2 lines (for preview)",
  "pillar": "The content pillar used",
  "template_used": "{template['name']}",
  "image_prompt": "A detailed prompt for DALL-E to generate a matching LinkedIn post image (professional, no text overlays, African-inspired aesthetic)",
  "hashtags": ["list", "of", "hashtags", "used"],
  "estimated_engagement": "low/medium/high based on content type and analytics patterns",
  "topic_summary": "One sentence describing the core topic (for future duplicate detection)",
  "audience_question_addressed": "If this post addresses a question from comments, note it here. Otherwise null."
}}"""

    user_prompt = f"""Write a LinkedIn post for the "{pillar}" content pillar.
Pillar description: {pillar_obj['description']}

{"Topic/angle to explore: " + topic_hint if topic_hint else "Choose a compelling angle that would resonate with African forex traders. Use the Intelligence Briefing above to pick an angle that hasn't been covered recently."}

Today's date: {datetime.now().strftime('%A, %B %d, %Y')}

IMPORTANT: Your post must be ORIGINAL. Check the Intelligence Briefing for hooks and topics already used — do NOT repeat them.

Return ONLY valid JSON. No markdown code fences."""

    response = client.messages.create(
        model=CLAUDE_SETTINGS["model"],
        max_tokens=CLAUDE_SETTINGS["max_tokens_post"],
        temperature=CLAUDE_SETTINGS["temperature_post"],
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
    )

    result_text = response.content[0].text.strip()

    # Parse JSON (handle potential markdown fences)
    if result_text.startswith("```"):
        result_text = result_text.split("```")[1]
        if result_text.startswith("json"):
            result_text = result_text[4:]
        result_text = result_text.strip()

    try:
        post_data = json.loads(result_text)
    except json.JSONDecodeError:
        logger.error(f"Failed to parse Claude response as JSON: {result_text[:200]}")
        post_data = {
            "text": result_text,
            "pillar": pillar,
            "template_used": template["name"],
            "image_prompt": f"Professional LinkedIn post image about {pillar}, African fintech aesthetic",
            "hashtags": random.sample(PROFILE["hashtag_pool"], 3),
            "estimated_engagement": "medium",
        }

    post_data["generated_at"] = datetime.now().isoformat()
    post_data["pillar"] = pillar
    post_data["template_used"] = template["name"]
    logger.info(f"Generated intelligent post for pillar: {pillar} | template: {template['name']}")
    return post_data


# ─── Comment Reply Generation ───────────────────────────────

def generate_reply(
    comment_text: str,
    commenter_name: str,
    original_post_text: str,
    comment_sentiment: str = "neutral"
) -> str:
    """Generate an intelligent reply to a LinkedIn comment using Claude."""
    system_prompt = f"""You are {PROFILE['name']}, replying to comments on your LinkedIn posts.

{BRAND_VOICE}

{ENGAGEMENT_RULES}"""

    user_prompt = f"""ORIGINAL POST:
{original_post_text[:500]}

COMMENT by {commenter_name}:
"{comment_text}"

Detected sentiment: {comment_sentiment}

Write a reply. Return ONLY the reply text, nothing else."""

    response = client.messages.create(
        model=CLAUDE_SETTINGS["model"],
        max_tokens=CLAUDE_SETTINGS["max_tokens_reply"],
        temperature=CLAUDE_SETTINGS["temperature_reply"],
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
    )

    reply = response.content[0].text.strip()
    if reply.startswith('"') and reply.endswith('"'):
        reply = reply[1:-1]

    logger.info(f"Generated reply to {commenter_name}: {reply[:80]}...")
    return reply


def classify_comment(comment_text: str) -> dict:
    """Classify a comment's sentiment and priority using Claude."""
    response = client.messages.create(
        model=CLAUDE_SETTINGS["model"],
        max_tokens=200,
        temperature=0.1,
        messages=[{
            "role": "user",
            "content": f"""Classify this LinkedIn comment. Return JSON only:
{{
  "sentiment": "positive|negative|neutral|question",
  "priority": "high|medium|low",
  "category": "question|appreciation|experience_share|disagreement|spam|promotion"
}}

Comment: "{comment_text}"

JSON:"""
        }],
    )

    try:
        result = response.content[0].text.strip()
        if result.startswith("```"):
            result = result.split("```")[1].replace("json", "").strip()
        return json.loads(result)
    except (json.JSONDecodeError, IndexError):
        return {"sentiment": "neutral", "priority": "medium", "category": "experience_share"}


# ─── Performance Analysis ──────────────────────────────────

def analyze_performance(posts_with_metrics: list) -> dict:
    """Analyze post performance and generate optimization recommendations."""
    posts_summary = ""
    for i, post in enumerate(posts_with_metrics, 1):
        posts_summary += f"\n--- Post {i} ---\n"
        posts_summary += f"Pillar: {post.get('pillar', 'Unknown')}\n"
        posts_summary += f"Template: {post.get('template_used', 'Unknown')}\n"
        posts_summary += f"Text preview: {post.get('text', '')[:300]}\n"
        posts_summary += f"Hook: {post.get('hook', 'N/A')}\n"
        posts_summary += f"Impressions: {post.get('metrics', {}).get('impressions', 'N/A')}\n"
        posts_summary += f"Likes: {post.get('metrics', {}).get('likes', 'N/A')}\n"
        posts_summary += f"Comments: {post.get('metrics', {}).get('comments', 'N/A')}\n"
        posts_summary += f"Shares: {post.get('metrics', {}).get('shares', 'N/A')}\n"
        posts_summary += f"Engagement Rate: {post.get('engagement_rate', 'N/A')}%\n"
        posts_summary += f"Posted: {post.get('created_at', 'N/A')}\n"

    response = client.messages.create(
        model=CLAUDE_SETTINGS["model"],
        max_tokens=CLAUDE_SETTINGS["max_tokens_analysis"],
        temperature=CLAUDE_SETTINGS["temperature_analysis"],
        messages=[{
            "role": "user",
            "content": f"""Analyze these LinkedIn post performance metrics for {PROFILE['name']} ({PROFILE['title']}).

{posts_summary}

Provide a detailed analysis in JSON format:
{{
  "summary": "2-3 sentence overall performance summary",
  "top_performing_pillars": ["ranked list of best content pillars"],
  "best_posting_times": ["times that got most engagement"],
  "hook_patterns": "what opening styles performed best",
  "content_recommendations": [
    "specific recommendation 1",
    "specific recommendation 2",
    "specific recommendation 3"
  ],
  "topics_to_double_down": ["topics/angles that resonated most"],
  "topics_to_avoid": ["topics/angles that underperformed"],
  "optimal_post_length": "recommended character range",
  "engagement_trend": "improving/declining/stable",
  "best_templates": ["which viral templates drove highest engagement"],
  "next_week_suggestions": [
    {{"pillar": "...", "topic_hint": "...", "why": "..."}},
    {{"pillar": "...", "topic_hint": "...", "why": "..."}}
  ]
}}

Return ONLY valid JSON."""
        }],
    )

    try:
        result = response.content[0].text.strip()
        if result.startswith("```"):
            result = result.split("```")[1].replace("json", "").strip()
        analysis = json.loads(result)
    except (json.JSONDecodeError, IndexError):
        analysis = {
            "summary": "Unable to parse analysis. Review raw data manually.",
            "content_recommendations": ["Continue current strategy while data builds."],
        }

    analysis["analyzed_at"] = datetime.now().isoformat()
    analysis["posts_analyzed"] = len(posts_with_metrics)
    logger.info(f"Performance analysis complete: {len(posts_with_metrics)} posts analyzed")
    return analysis


# ─── Intelligent Content Queue Management ──────────────────

def load_full_context() -> dict:
    """Load ALL available context for intelligent content generation."""
    existing_queue = _load_json_safe(CONTENT_QUEUE_FILE, [])
    post_history = _load_json_safe(POST_HISTORY_FILE, [])
    analytics_data = _load_json_safe(ANALYTICS_FILE, {})
    comment_log = _load_json_safe(COMMENT_LOG_FILE, [])

    logger.info(
        f"Context loaded — Queue: {len(existing_queue)} posts, "
        f"History: {len(post_history)} posts, "
        f"Comments: {len(comment_log)} entries"
    )

    return {
        "existing_queue": existing_queue,
        "post_history": post_history,
        "analytics_data": analytics_data,
        "comment_insights": comment_log,
    }


def generate_weekly_content(optimize_from: list = None, progress_callback=None) -> list:
    """
    Generate a full week of content (6 posts, Mon-Sat) with FULL intelligence.

    Each post is generated with awareness of all previously generated posts
    (including earlier posts in this batch), full history, analytics, and comments.

    Args:
        optimize_from: Past top-performing posts to learn from
        progress_callback: Optional function(message) for progress updates

    Returns:
        List of post dicts ready to schedule (with real calendar dates)
    """
    from config import POSTING_SCHEDULE

    def _progress(msg):
        if progress_callback:
            progress_callback(msg)
        logger.info(msg)

    _progress("Loading full context: queue, history, analytics, comments...")

    # Load full context ONCE
    context = load_full_context()
    existing_queue = context["existing_queue"]
    post_history = context["post_history"]
    analytics_data = context["analytics_data"]
    comment_insights = context["comment_insights"]

    # Get top posts for optimization if not provided
    if optimize_from is None:
        try:
            from analytics_engine import AnalyticsEngine
            analytics = AnalyticsEngine()
            optimize_from = analytics.get_top_posts(5, 30)
        except Exception as e:
            logger.warning(f"Could not load top posts for optimization: {e}")
            optimize_from = []

    weekly_posts = []
    running_queue = list(existing_queue)
    schedule_items = list(POSTING_SCHEDULE.items())
    total = len(schedule_items)

    for idx, (day, schedule) in enumerate(schedule_items):
        post_num = idx + 1
        _progress(f"Generating post {post_num}/{total}: {day.capitalize()} — {schedule['pillar_preference']}...")

        try:
            post = generate_post(
                pillar=schedule["pillar_preference"],
                optimize_from=optimize_from,
                existing_queue=running_queue,
                post_history=post_history,
                analytics_data=analytics_data,
                comment_insights=comment_insights,
            )

            # ── Assign REAL calendar dates ──
            post_date = _get_next_weekday(day)
            hour, minute = map(int, schedule["time"].split(":"))
            post_date = post_date.replace(hour=hour, minute=minute, second=0, microsecond=0)

            post["scheduled_day"] = day
            post["scheduled_time"] = schedule["time"]
            post["scheduled_date"] = post_date.strftime("%Y-%m-%d")
            post["scheduled_datetime"] = post_date.isoformat()
            post["display_date"] = post_date.strftime("%a, %b %d at %I:%M %p")

            weekly_posts.append(post)
            running_queue.append(post)

            _progress(f"Post {post_num}/{total} done: {post.get('pillar')} — {post.get('hook', '')[:50]}...")

        except Exception as e:
            logger.error(f"Failed to generate post {post_num}/{total} for {day}: {e}")
            _progress(f"Post {post_num}/{total} failed: {str(e)[:100]}. Continuing...")
            # Continue generating remaining posts instead of crashing
            continue

    # Save to content queue (append to existing)
    if weekly_posts:
        _save_content_queue(weekly_posts)

    _progress(f"Done! Generated {len(weekly_posts)}/{total} posts.")
    logger.info(f"Weekly content generation complete — {len(weekly_posts)} intelligent posts created")
    return weekly_posts


def _save_content_queue(posts: list):
    """Save posts to the content queue file."""
    existing = []
    if CONTENT_QUEUE_FILE.exists():
        try:
            with open(CONTENT_QUEUE_FILE) as f:
                existing = json.load(f)
        except (json.JSONDecodeError, IOError):
            existing = []

    existing.extend(posts)
    with open(CONTENT_QUEUE_FILE, "w") as f:
        json.dump(existing, f, indent=2)

    logger.info(f"Content queue updated: {len(existing)} total posts queued")
