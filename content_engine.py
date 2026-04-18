"""
Content Engine — Powered by Claude
====================================
Generates LinkedIn posts, comment replies, and performance analysis
using the Anthropic Claude API.
"""

import json
import random
import logging
from datetime import datetime
from anthropic import Anthropic
from config import (
    ANTHROPIC_API_KEY, CLAUDE_SETTINGS, PROFILE,
    CONTENT_PILLARS, CONTENT_QUEUE_FILE, POST_HISTORY_FILE
)
from knowledge_base import (
    BRAND_VOICE, GROWTH_STRATEGY, VIRAL_TEMPLATES,
    SAMPLE_POSTS, HASHTAG_STRATEGY, ENGAGEMENT_RULES
)
from pathlib import Path

logger = logging.getLogger("content_engine")

client = Anthropic(api_key=ANTHROPIC_API_KEY)


# ─── Post Generation ────────────────────────────────────────

def generate_post(pillar: str = None, topic_hint: str = None, optimize_from: list = None) -> dict:
    """
    Generate a LinkedIn post using Claude.

    Args:
        pillar: Content pillar to write about (random if None)
        topic_hint: Optional specific topic or angle
        optimize_from: List of past top-performing posts to learn from

    Returns:
        dict with 'text', 'pillar', 'image_prompt', 'hashtags'
    """
    if pillar is None:
        weights = [p["weight"] for p in CONTENT_PILLARS]
        pillar_obj = random.choices(CONTENT_PILLARS, weights=weights, k=1)[0]
        pillar = pillar_obj["name"]
    else:
        pillar_obj = next((p for p in CONTENT_PILLARS if p["name"] == pillar), CONTENT_PILLARS[0])

    # Build optimization context from top posts
    optimization_context = ""
    if optimize_from:
        optimization_context = "\n\nHere are my top-performing posts for reference. Learn from their style, hooks, and structure:\n"
        for i, post in enumerate(optimize_from[:5], 1):
            optimization_context += f"\n--- TOP POST {i} (Engagement: {post.get('engagement_rate', 'N/A')}) ---\n"
            optimization_context += f"{post.get('text', '')[:500]}\n"

    # Select a random viral template to guide structure
    template = random.choice(VIRAL_TEMPLATES)

    # Get sample posts for the same pillar
    pillar_samples = [p for p in SAMPLE_POSTS if pillar.lower() in p.get("pillar", "").lower()]
    if not pillar_samples:
        pillar_samples = random.sample(SAMPLE_POSTS, min(3, len(SAMPLE_POSTS)))

    sample_text = "\n\n".join([
        f"--- EXAMPLE POST ({s['pillar']}) ---\n{s['text'][:600]}"
        for s in pillar_samples[:3]
    ])

    system_prompt = f"""You are a LinkedIn ghostwriter for {PROFILE['name']}.

{BRAND_VOICE}

PROFILE:
- Title: {PROFILE['title']}
- Company: {PROFILE['company']}
- Niche: {PROFILE['niche']}
- Target Audience: {PROFILE['audience']}
- Tone: {PROFILE['tone']}

VIRAL TEMPLATE TO USE (adapt, don't copy exactly):
Template: "{template['name']}"
Formula: {template['formula']}
Structure:
{template['structure'][:500]}

HASHTAG STRATEGY:
{json.dumps(HASHTAG_STRATEGY['rules'])}
Primary hashtags (use 1): {', '.join(HASHTAG_STRATEGY['primary'])}
Pillar-specific options: {json.dumps(HASHTAG_STRATEGY.get('pillar_specific', {}))}

EXAMPLE POSTS IN MY VOICE (learn from these):
{sample_text}

RULES:
1. Write in first person as {PROFILE['name']}
2. Open with a powerful hook (first 2 lines are critical — they show before "see more")
3. Use short paragraphs (1-3 sentences max)
4. Include a personal story or data point
5. End with a question or clear CTA to drive comments
6. Add 3-4 relevant hashtags following the hashtag strategy above
7. Post length: 1200-2000 characters (LinkedIn sweet spot)
8. NO emojis in the main text (professional tone)
9. Use line breaks generously for readability
10. Reference Gopipways naturally — not forced promotion
11. Make it DIFFERENT from the examples — new angles, new stories, new data points
12. Use the viral template structure but with FRESH content

OUTPUT FORMAT (JSON):
{{
  "text": "The full post text ready to publish",
  "hook": "The opening 2 lines (for preview)",
  "pillar": "The content pillar used",
  "image_prompt": "A detailed prompt for DALL-E to generate a matching LinkedIn post image (professional, no text overlays, African-inspired aesthetic)",
  "hashtags": ["list", "of", "hashtags", "used"],
  "estimated_engagement": "low/medium/high based on content type"
}}"""

    user_prompt = f"""Write a LinkedIn post for the "{pillar}" content pillar.
Pillar description: {pillar_obj['description']}

{"Topic/angle to explore: " + topic_hint if topic_hint else "Choose a compelling angle that would resonate with African forex traders."}
{optimization_context}

Today's date: {datetime.now().strftime('%A, %B %d, %Y')}

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
            "image_prompt": f"Professional LinkedIn post image about {pillar}, African fintech aesthetic",
            "hashtags": random.sample(PROFILE["hashtag_pool"], 3),
            "estimated_engagement": "medium",
        }

    post_data["generated_at"] = datetime.now().isoformat()
    post_data["pillar"] = pillar
    logger.info(f"Generated post for pillar: {pillar}")
    return post_data


# ─── Comment Reply Generation ───────────────────────────────

def generate_reply(
    comment_text: str,
    commenter_name: str,
    original_post_text: str,
    comment_sentiment: str = "neutral"
) -> str:
    """
    Generate an intelligent reply to a LinkedIn comment using Claude.

    Args:
        comment_text: The comment to reply to
        commenter_name: Name of the commenter
        original_post_text: The original post the comment is on
        comment_sentiment: Detected sentiment (positive/negative/neutral/question)

    Returns:
        Reply text string
    """
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
    # Remove quotes if Claude wrapped the reply
    if reply.startswith('"') and reply.endswith('"'):
        reply = reply[1:-1]

    logger.info(f"Generated reply to {commenter_name}: {reply[:80]}...")
    return reply


def classify_comment(comment_text: str) -> dict:
    """
    Classify a comment's sentiment and priority using Claude.

    Returns:
        dict with 'sentiment', 'priority', 'category'
    """
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
    """
    Analyze post performance and generate optimization recommendations using Claude.

    Args:
        posts_with_metrics: List of posts with their engagement metrics

    Returns:
        dict with analysis, top patterns, and recommendations
    """
    posts_summary = ""
    for i, post in enumerate(posts_with_metrics, 1):
        posts_summary += f"\n--- Post {i} ---\n"
        posts_summary += f"Pillar: {post.get('pillar', 'Unknown')}\n"
        posts_summary += f"Text preview: {post.get('text', '')[:300]}\n"
        posts_summary += f"Impressions: {post.get('metrics', {}).get('impressions', 'N/A')}\n"
        posts_summary += f"Likes: {post.get('metrics', {}).get('likes', 'N/A')}\n"
        posts_summary += f"Comments: {post.get('metrics', {}).get('comments', 'N/A')}\n"
        posts_summary += f"Shares: {post.get('metrics', {}).get('shares', 'N/A')}\n"
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


# ─── Content Queue Management ──────────────────────────────

def generate_weekly_content(optimize_from: list = None) -> list:
    """
    Generate a full week of content (6 posts, Mon-Sat).

    Args:
        optimize_from: Past top-performing posts to learn from

    Returns:
        List of post dicts ready to schedule
    """
    from config import POSTING_SCHEDULE

    weekly_posts = []
    for day, schedule in POSTING_SCHEDULE.items():
        post = generate_post(
            pillar=schedule["pillar_preference"],
            optimize_from=optimize_from,
        )
        post["scheduled_day"] = day
        post["scheduled_time"] = schedule["time"]
        weekly_posts.append(post)
        logger.info(f"Generated {day} post: {post.get('pillar')}")

    # Save to content queue
    _save_content_queue(weekly_posts)
    return weekly_posts


def _save_content_queue(posts: list):
    """Save posts to the content queue file."""
    existing = []
    if CONTENT_QUEUE_FILE.exists():
        with open(CONTENT_QUEUE_FILE) as f:
            existing = json.load(f)

    existing.extend(posts)
    with open(CONTENT_QUEUE_FILE, "w") as f:
        json.dump(existing, f, indent=2)
