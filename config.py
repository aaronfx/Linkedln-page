"""
LinkedIn Automation Configuration
=================================
Fill in your API keys and preferences below.
"""

import os
from pathlib import Path

# âââ API Keys âââââââââââââââââââââââââââââââââââââââââââââââ
# Set these as environment variables or hardcode below (env vars recommended)

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "your-anthropic-api-key-here")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "your-openai-api-key-here")

# LinkedIn OAuth 2.0 credentials
# Get these from https://www.linkedin.com/developers/apps
LINKEDIN_CLIENT_ID = os.getenv("LINKEDIN_CLIENT_ID", "your-client-id-here")
LINKEDIN_CLIENT_SECRET = os.getenv("LINKEDIN_CLIENT_SECRET", "your-client-secret-here")
LINKEDIN_ACCESS_TOKEN = os.getenv("LINKEDIN_ACCESS_TOKEN", "your-access-token-here")
LINKEDIN_PERSON_URN = os.getenv("LINKEDIN_PERSON_URN", "your-person-urn-here")  # e.g., "urn:li:person:ABC123"

# âââ Profile Configuration ââââââââââââââââââââââââââââââââââ
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

# âââ Content Pillars ââââââââââââââââââââââââââââââââââââââââ
CONTENT_PILLARS = [
    {
        "name": "Forex Education",
        "weight": 0.30,
        "description": (
            "Technical analysis tips, chart patterns, trading psychology insights, "
            "risk management frameworks, common mistakes and corrections, trading setup breakdowns. "
            "Posting frequency: 1-2 per week."
        ),
    },
    {
        "name": "AI in Trading",
        "weight": 0.20,
        "description": (
            "AI trading indicators and tools, how AI improves trader accuracy, "
            "automation vs manual trading debates, future of AI in African markets. "
            "Brand integration: include Gopipways in 2-3 posts monthly without being salesy. "
            "Posting frequency: 1 per week."
        ),
    },
    {
        "name": "African Markets & Financial Literacy",
        "weight": 0.20,
        "description": (
            "African economic trends and market impacts, currency analysis (NGN, GHS, KES, ZAR), "
            "financial literacy for underserved communities, success stories of African traders, "
            "cross-regional African market insights. Posting frequency: 1 per week."
        ),
    },
    {
        "name": "Personal Story & Behind-the-Scenes",
        "weight": 0.15,
        "description": (
            "Founder journey and lessons learned, day-in-the-life content, challenges overcome, "
            "team spotlights, gratitude/milestone celebrations. "
            "Posting frequency: 0.5-1 per week."
        ),
    },
    {
        "name": "Industry Commentary",
        "weight": 0.15,
        "description": (
            "Market commentary on major moves, economic calendar analysis, geopolitical impacts on forex, "
            "industry trends and predictions, volatility analysis. "
            "Posting frequency: 0.5-1 per week."
        ),
    },
]

# âââ Posting Schedule âââââââââââââââââââââââââââââââââââââââ
# Days and times (WAT - West Africa Time, UTC+1)
POSTING_SCHEDULE = {
    "monday":    {"time": "09:00", "pillar_preference": "Personal Story & Behind-the-Scenes", "post_type": "Controversial Take or Myth vs. Reality"},
    "tuesday":   {"time": "11:00", "pillar_preference": "Forex Education", "post_type": "Educational Deep Dive or Data/Stats Hook"},
    "wednesday": {"time": "08:00", "pillar_preference": "African Markets & Financial Literacy", "post_type": "Poll or Community Question"},
    "thursday":  {"time": "09:00", "pillar_preference": "AI in Trading", "post_type": "Personal Story or Lesson Learned"},
    "friday":    {"time": "10:00", "pillar_preference": "African Markets & Financial Literacy", "post_type": "Market Commentary or Data-Driven Insight"},
    "saturday": {"time": "10:00", "pillar_preference": "Industry Commentary", "post_type": "Weekend Insight or Practical Framework"},
    "sunday":    {"time": "19:00", "pillar_preference": "Personal Story & Behind-the-Scenes", "post_type": "Motivational or Week-Ahead Mindset"},
    # Sunday: rest day â content batching and review
}

TIMEZONE = "Africa/Lagos"  # WAT

# âââ Image Generation Settings ââââââââââââââââââââââââââââââ
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

# âââ Claude Settings ââââââââââââââââââââââââââââââââââââââââ
CLAUDE_SETTINGS = {
    "model": "claude-sonnet-4-20250514",
    "max_tokens_post": 2000,
    "max_tokens_reply": 500,
    "max_tokens_analysis": 3000,
    "temperature_post": 0.8,
    "temperature_reply": 0.6,
    "temperature_analysis": 0.3,
}

# âââ Comment Reply Settings âââââââââââââââââââââââââââââââââ
REPLY_SETTINGS = {
    "auto_reply": True,
    "reply_delay_minutes": 5,       # Wait before replying (looks more human)
    "max_replies_per_hour": 5,      # Reduced from 20 â too aggressive
    "min_comment_length": 3,        # Skip very short comments like "Nice"
    "skip_keywords": ["spam", "DM me", "check my profile"],
    "priority_keywords": ["how", "what", "why", "help", "question", "advice"],
}

# âââ Analytics Settings âââââââââââââââââââââââââââââââââââââ
ANALYTICS_SETTINGS = {
    "track_interval_hours": 12,     # Increased from 6 â less API pressure
    "report_day": "sunday",
    "report_time": "20:00",
    "metrics": ["impressions", "likes", "comments", "shares", "engagement_rate"],
    "optimization_lookback_days": 30,
}

# âââ File Paths âââââââââââââââââââââââââââââââââââââââââââââ
BASE_DIR = Path(__file__).parent

# Use Railway persistent volume if available (survives deploys)
PERSISTENT_DIR = Path("/app/persistent") if Path("/app/persistent").exists() else None

# Directories that need persistence (images, data, analytics, logs)
if PERSISTENT_DIR:
    DATA_DIR = PERSISTENT_DIR / "data"
    LOGS_DIR = PERSISTENT_DIR / "logs"
    IMAGES_DIR = PERSISTENT_DIR / "images"
    ANALYTICS_DIR = PERSISTENT_DIR / "analytics"
else:
    DATA_DIR = BASE_DIR / "data"
    LOGS_DIR = BASE_DIR / "logs"
    IMAGES_DIR = BASE_DIR / "images"
    ANALYTICS_DIR = BASE_DIR / "analytics"

for d in [DATA_DIR, LOGS_DIR, IMAGES_DIR, ANALYTICS_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# On first deploy with volume, copy existing data from repo to volume
if PERSISTENT_DIR:
    import shutil
    _repo_data = BASE_DIR / "data"
    if _repo_data.exists():
        for f in _repo_data.glob("*.json"):
            dest = DATA_DIR / f.name
            if not dest.exists():
                shutil.copy2(f, dest)

CONTENT_QUEUE_FILE = DATA_DIR / "content_queue.json"
ANALYTICS_FILE = ANALYTICS_DIR / "analytics.json"
COMMENT_LOG_FILE = DATA_DIR / "comment_log.json"
POST_HISTORY_FILE = DATA_DIR / "post_history.json"
