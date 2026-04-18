"""
LinkedIn Automation Configuration
=================================
Fill in your API keys and preferences below.
"""

import os
from pathlib import Path

# ─── API Keys ───────────────────────────────────────────────
# Set these as environment variables or hardcode below (env vars recommended)

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "your-anthropic-api-key-here")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "your-openai-api-key-here")

# LinkedIn OAuth 2.0 credentials
# Get these from https://www.linkedin.com/developers/apps
LINKEDIN_CLIENT_ID = os.getenv("LINKEDIN_CLIENT_ID", "your-client-id-here")
LINKEDIN_CLIENT_SECRET = os.getenv("LINKEDIN_CLIENT_SECRET", "your-client-secret-here")
LINKEDIN_ACCESS_TOKEN = os.getenv("LINKEDIN_ACCESS_TOKEN", "your-access-token-here")
LINKEDIN_PERSON_URN = os.getenv("LINKEDIN_PERSON_URN", "your-person-urn-here")  # e.g., "urn:li:person:ABC123"

# ─── Profile Configuration ──────────────────────────────────
PROFILE = {
    "name": "Dr. Aaron Akwu",
    "title": "Forex Educator | Built Africa's #1 AI-Powered Forex Academy",
    "company": "Gopipways",
    "niche": "Forex education, AI-powered trading, African fintech",
    "audience": "Aspiring and intermediate forex traders in Africa",
    "tone": "Authoritative yet approachable. Data-driven. Story-led. Pan-African pride.",
    "hashtag_pool": [
        "#ForexTrading", "#ForexEducation", "#FinancialLiteracy",
        "#AfricaFintech", "#TradingPsychology", "#RiskManagement",
        "#ArtificialIntelligence", "#EdTech", "#NigeriaFintech",
        "#AfricanStartups", "#FinancialMarkets", "#TradingMindset",
        "#SubSaharanAfrica", "#Leadership", "#SkillsDevelopment",
        "#TechnicalAnalysis"
    ],
}

# ─── Content Pillars ────────────────────────────────────────
CONTENT_PILLARS = [
    {
        "name": "Personal Story & Behind-the-Scenes",
        "weight": 0.20,
        "description": "Founder journey, lessons learned, student transformations",
    },
    {
        "name": "Forex Education",
        "weight": 0.25,
        "description": "Trading strategies, risk management, practical frameworks",
    },
    {
        "name": "AI in Trading",
        "weight": 0.15,
        "description": "How AI enhances trading, myth-busting, Gopipways tech",
    },
    {
        "name": "African Markets & Financial Literacy",
        "weight": 0.20,
        "description": "Africa fintech opportunity, local currency pairs, financial inclusion",
    },
    {
        "name": "Community & Interactive",
        "weight": 0.10,
        "description": "Polls, questions, engagement-driven posts",
    },
    {
        "name": "Industry Commentary",
        "weight": 0.10,
        "description": "Market analysis, weekend insights, trending topics",
    },
]

# ─── Posting Schedule ───────────────────────────────────────
# Days and times (WAT - West Africa Time, UTC+1)
POSTING_SCHEDULE = {
    "monday":    {"time": "09:00", "pillar_preference": "Personal Story & Behind-the-Scenes"},
    "tuesday":   {"time": "11:00", "pillar_preference": "Forex Education"},
    "wednesday": {"time": "14:00", "pillar_preference": "Community & Interactive"},
    "thursday":  {"time": "09:00", "pillar_preference": "AI in Trading"},
    "friday":    {"time": "10:00", "pillar_preference": "African Markets & Financial Literacy"},
    "saturday":  {"time": "18:00", "pillar_preference": "Industry Commentary"},
    # Sunday: rest day
}

TIMEZONE = "Africa/Lagos"  # WAT

# ─── Image Generation Settings ──────────────────────────────
IMAGE_SETTINGS = {
    "model": "dall-e-3",
    "size": "1792x1024",  # 16:9 landscape for LinkedIn feed
    "quality": "hd",       # HD for photorealistic quality
    "style": "natural",    # Natural style for photorealism (not "vivid")
    "default_theme": (
        "Photorealistic editorial photography. Natural lighting. "
        "Real-world settings and real people. No text, words, logos, or watermarks. "
        "Professional, authentic, documentary style. "
        "Shot on a professional camera with shallow depth of field."
    ),
}

# ─── Claude Settings ────────────────────────────────────────
CLAUDE_SETTINGS = {
    "model": "claude-sonnet-4-20250514",
    "max_tokens_post": 2000,
    "max_tokens_reply": 500,
    "max_tokens_analysis": 3000,
    "temperature_post": 0.8,
    "temperature_reply": 0.6,
    "temperature_analysis": 0.3,
}

# ─── Comment Reply Settings ─────────────────────────────────
REPLY_SETTINGS = {
    "auto_reply": True,
    "reply_delay_minutes": 5,       # Wait before replying (looks more human)
    "max_replies_per_hour": 20,
    "min_comment_length": 3,        # Skip very short comments like "Nice"
    "skip_keywords": ["spam", "DM me", "check my profile"],
    "priority_keywords": ["how", "what", "why", "help", "question", "advice"],
}

# ─── Analytics Settings ─────────────────────────────────────
ANALYTICS_SETTINGS = {
    "track_interval_hours": 6,
    "report_day": "sunday",
    "report_time": "20:00",
    "metrics": ["impressions", "likes", "comments", "shares", "engagement_rate"],
    "optimization_lookback_days": 30,
}

# ─── File Paths ─────────────────────────────────────────────
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
LOGS_DIR = BASE_DIR / "logs"
IMAGES_DIR = BASE_DIR / "images"
ANALYTICS_DIR = BASE_DIR / "analytics"

for d in [DATA_DIR, LOGS_DIR, IMAGES_DIR, ANALYTICS_DIR]:
    d.mkdir(exist_ok=True)

CONTENT_QUEUE_FILE = DATA_DIR / "content_queue.json"
ANALYTICS_FILE = ANALYTICS_DIR / "analytics.json"
COMMENT_LOG_FILE = DATA_DIR / "comment_log.json"
POST_HISTORY_FILE = DATA_DIR / "post_history.json"
