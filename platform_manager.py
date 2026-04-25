"""
Platform Management Module for Gopipways Social Hub

Manages multi-platform social media content generation and distribution.
Handles platform-specific configurations, content generation, and formatting.

Author: Gopipways Engineering
Version: 1.0.0
"""

import logging
import json
from enum import Enum
from dataclasses import dataclass
from typing import Optional, Dict, List, Any
from anthropic import Anthropic

# Configure module logger
logger = logging.getLogger("platform_manager")
logger.setLevel(logging.INFO)


# ============================================================================
# ENUMS & CONSTANTS
# ============================================================================

class PlatformStatus(Enum):
    """Platform availability status."""
    ACTIVE = "ACTIVE"
    COMING_SOON = "COMING_SOON"
    INACTIVE = "INACTIVE"


class ContentPillar(Enum):
    """Content pillars for different platforms."""
    # LinkedIn pillars
    FOREX_EDUCATION = "Forex Education"
    AI_IN_TRADING = "AI in Trading"
    AFRICAN_MARKETS = "African Markets"
    PERSONAL_STORY = "Personal Story"
    INDUSTRY_COMMENTARY = "Industry Commentary"

    # WhatsApp pillars
    EDUCATE = "EDUCATE"
    PROVE = "PROVE"
    INSPIRE = "INSPIRE"
    ENGAGE = "ENGAGE"
    CONVERT = "CONVERT"


class PlatformVoice(Enum):
    """Content voice for different platforms."""
    FIRST_PERSON = "first_person"  # "I", personal brand
    COMPANY = "company"  # "we", company brand


# Platform character limits
CHARACTER_LIMITS = {
    "LinkedIn": 3000,
    "WhatsApp Status": 700,
    "Instagram": 2200,
    "X": 280,
    "Threads": 500,
    "Facebook": 63206,
}


# ============================================================================
# DATA CLASSES
# ============================================================================

@dataclass
class PlatformConfig:
    """Configuration for a social media platform."""
    name: str
    status: PlatformStatus
    voice: PlatformVoice
    brand: str  # Personal brand or company name
    character_limit: int
    auto_posting: bool
    pillars: Dict[str, float]  # pillar -> percentage distribution
    posting_method: str  # "api" or "manual"

    def to_dict(self) -> Dict[str, Any]:
        """Convert config to dictionary."""
        return {
            "name": self.name,
            "status": self.status.value,
            "voice": self.voice.value,
            "brand": self.brand,
            "character_limit": self.character_limit,
            "auto_posting": self.auto_posting,
            "pillars": self.pillars,
            "posting_method": self.posting_method,
        }


@dataclass
class WhatsAppStatus:
    """WhatsApp Status content structure."""
    text: str
    pillar: str
    visual_direction: str
    hashtags: List[str]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "text": self.text,
            "pillar": self.pillar,
            "visual_direction": self.visual_direction,
            "hashtags": self.hashtags,
        }


# ============================================================================
# PLATFORM CONFIGURATIONS
# ============================================================================

PLATFORM_CONFIGS = {
    "LinkedIn": PlatformConfig(
        name="LinkedIn",
        status=PlatformStatus.ACTIVE,
        voice=PlatformVoice.FIRST_PERSON,
        brand="Dr. Aaron Akwu",
        character_limit=CHARACTER_LIMITS["LinkedIn"],
        auto_posting=True,
        pillars={
            "Forex Education": 0.30,
            "AI in Trading": 0.20,
            "African Markets": 0.20,
            "Personal Story": 0.15,
            "Industry Commentary": 0.15,
        },
        posting_method="api",
    ),
    "WhatsApp Status": PlatformConfig(
        name="WhatsApp Status",
        status=PlatformStatus.ACTIVE,
        voice=PlatformVoice.COMPANY,
        brand="Gopipways",
        character_limit=CHARACTER_LIMITS["WhatsApp Status"],
        auto_posting=False,
        pillars={
            "EDUCATE": 0.35,
            "PROVE": 0.25,
            "INSPIRE": 0.15,
            "ENGAGE": 0.15,
            "CONVERT": 0.10,
        },
        posting_method="manual",
    ),
    "Instagram": PlatformConfig(
        name="Instagram",
        status=PlatformStatus.ACTIVE,
        voice=PlatformVoice.COMPANY,
        brand="Gopipways",
        character_limit=CHARACTER_LIMITS["Instagram"],
        auto_posting=True,
        pillars={
            "Education / Trading Tips": 0.35,
            "AI in Trading / Product": 0.15,
            "African Markets / Financial Literacy": 0.20,
            "Behind the Scenes / Personal Brand": 0.15,
            "Social Proof / Results": 0.10,
            "Engagement / Community": 0.05,
        },
        posting_method="api",
    ),
    "X": PlatformConfig(
        name="X",
        status=PlatformStatus.COMING_SOON,
        voice=PlatformVoice.COMPANY,
        brand="Gopipways",
        character_limit=CHARACTER_LIMITS["X"],
        auto_posting=False,
        pillars={},
        posting_method="manual",
    ),
    "Threads": PlatformConfig(
        name="Threads",
        status=PlatformStatus.COMING_SOON,
        voice=PlatformVoice.COMPANY,
        brand="Gopipways",
        character_limit=CHARACTER_LIMITS["Threads"],
        auto_posting=False,
        pillars={},
        posting_method="manual",
    ),
    "Facebook": PlatformConfig(
        name="Facebook",
        status=PlatformStatus.ACTIVE,
        voice=PlatformVoice.COMPANY,
        brand="Gopipways",
        character_limit=CHARACTER_LIMITS["Facebook"],
        auto_posting=True,
        pillars={
            "Education / Trading Tips": 0.35,
            "AI in Trading / Product": 0.15,
            "African Markets / Financial Literacy": 0.20,
            "Behind the Scenes / Personal Brand": 0.15,
            "Social Proof / Results": 0.10,
            "Engagement / Community": 0.05,
        },
        posting_method="api",
    ),
}


# Brand guidelines for Gopipways
BRAND_GUIDELINES = {
    "mission": "Democratise forex trading education and empower retail traders with AI-driven insights",
    "voice": "Professional yet approachable, educational, empowering",
    "personas": {
        "Curious Beginner": {
            "age_range": "18-28",
            "traits": "New to trading, seeking foundational knowledge, tech-savvy",
        },
        "Struggling Intermediate": {
            "age_range": "24-35",
            "traits": "Has some trading experience, looking to improve, frustrated with losses",
        },
        "Aspiring Professional": {
            "age_range": "28-45",
            "traits": "Advanced trader, seeking edge, interested in AI and automation",
        },
    },
    "key_messages": [
        "Forex education simplified",
        "AI-powered trading insights",
        "Risk management first",
        "Community-driven learning",
    ],
}


# ============================================================================
# PLATFORM UTILITIES
# ============================================================================

def get_platform_config(platform: str) -> Optional[PlatformConfig]:
    """
    Retrieve configuration for a specific platform.

    Args:
        platform: Platform name (e.g., "LinkedIn", "WhatsApp Status")

    Returns:
        PlatformConfig object or None if platform not found

    Raises:
        ValueError: If platform name is invalid
    """
    if platform not in PLATFORM_CONFIGS:
        logger.error(f"Platform '{platform}' not found in configurations")
        raise ValueError(f"Unknown platform: {platform}")

    return PLATFORM_CONFIGS[platform]


def get_active_platforms() -> List[str]:
    """
    Get list of currently active platforms.

    Returns:
        List of active platform names
    """
    active = [
        name for name, config in PLATFORM_CONFIGS.items()
        if config.status == PlatformStatus.ACTIVE
    ]
    logger.info(f"Retrieved {len(active)} active platforms: {active}")
    return active


def get_all_platforms() -> Dict[str, str]:
    """
    Get all platforms with their status.

    Returns:
        Dictionary mapping platform names to status strings
    """
    platforms = {name: config.status.value for name, config in PLATFORM_CONFIGS.items()}
    logger.debug(f"Retrieved all platforms: {platforms}")
    return platforms


def get_platform_pillars(platform: str) -> Dict[str, float]:
    """
    Get content pillars for a platform with their percentage distributions.

    Args:
        platform: Platform name

    Returns:
        Dictionary mapping pillar names to percentage values (0-1)

    Raises:
        ValueError: If platform not found
    """
    config = get_platform_config(platform)
    logger.debug(f"Retrieved pillars for {platform}: {config.pillars}")
    return config.pillars


def format_for_platform(text: str, platform: str) -> str:
    """
    Apply platform-specific formatting to content.

    Handles character limits, hashtag rules, and formatting conventions.

    Args:
        text: Content text to format
        platform: Target platform name

    Returns:
        Formatted content suitable for the platform

    Raises:
        ValueError: If platform not found
    """
    config = get_platform_config(platform)

    # Get character limit for platform
    char_limit = config.character_limit

    # Truncate if necessary
    if len(text) > char_limit:
        logger.warning(
            f"Content for {platform} exceeds limit ({len(text)}/{char_limit}). Truncating."
        )
        # Truncate and add ellipsis if applicable
        if platform != "X":  # X doesn't benefit from ellipsis due to char limit
            text = text[:char_limit - 3] + "..."
        else:
            text = text[:char_limit]

    # Platform-specific formatting
    if platform == "LinkedIn":
        # LinkedIn supports line breaks and formatting
        text = text.strip()
    elif platform == "WhatsApp Status":
        # WhatsApp has 700 char limit, optimize for mobile
        text = text.strip()
    elif platform == "X":
        # Twitter/X requires exact char counting due to URL encoding
        text = text.strip()

    logger.debug(f"Formatted content for {platform} ({len(text)}/{char_limit} chars)")
    return text


# ============================================================================
# WHATSAPP STATUS CONTENT GENERATION
# ============================================================================

def generate_whatsapp_status(
    pillar: Optional[str] = None,
    topic: Optional[str] = None,
    api_key: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Generate WhatsApp Status content using Claude API.

    Creates engaging, educational WhatsApp Status content that adheres to
    Gopipways brand guidelines and content pillars. Content is optimized
    for the WhatsApp Status format (max 700 characters).

    Args:
        pillar: Content pillar (EDUCATE, PROVE, INSPIRE, ENGAGE, CONVERT).
               If None, randomly selects from available pillars.
        topic: Optional specific topic for the status
        api_key: Anthropic API key. If None, expects environment variable.

    Returns:
        Dictionary containing:
            - text: Generated status text (max 700 chars)
            - pillar: Pillar used for generation
            - visual_direction: Suggested visual style
            - hashtags: Relevant hashtags

    Raises:
        ValueError: If required API key not available
        Exception: If API call fails
    """
    try:
        # Import config here to avoid circular dependencies
        try:
            from config import ANTHROPIC_API_KEY, CLAUDE_SETTINGS
            effective_api_key = api_key or ANTHROPIC_API_KEY
            claude_settings = CLAUDE_SETTINGS
        except ImportError:
            logger.warning("config.py not found, using provided API key or environment")
            effective_api_key = api_key
            claude_settings = {
                "model": "claude-sonnet-4-20250514",
                "max_tokens": 1000,
                "temperature": 0.8,
            }

        if not effective_api_key:
            logger.error("No API key provided and none found in config.py or environment")
            raise ValueError("ANTHROPIC_API_KEY required but not provided")

        # Initialize Anthropic client
        client = Anthropic(api_key=effective_api_key)

        # Select pillar if not provided
        whatsapp_pillars = get_platform_pillars("WhatsApp Status")
        if pillar is None:
            import random
            pillar = random.choice(list(whatsapp_pillars.keys()))
            logger.info(f"No pillar specified, randomly selected: {pillar}")

        if pillar not in whatsapp_pillars:
            logger.error(f"Invalid pillar: {pillar}")
            raise ValueError(f"Invalid pillar: {pillar}. Must be one of {list(whatsapp_pillars.keys())}")

        # Build prompt for Claude
        topic_context = f"\nSpecific topic: {topic}" if topic else ""

        prompt = f"""You are a social media content creator for Gopipways, a forex trading education platform.

Create engaging WhatsApp Status content that:
- Has maximum 700 characters
- Follows the '{pillar}' pillar theme
- Uses "we" voice (company brand: Gopipways)
- References the brand mission: {BRAND_GUIDELINES['mission']}
- Targets one of these personas: {', '.join(BRAND_GUIDELINES['personas'].keys())}
- Includes a clear call-to-action
- Drives Academy sign-ups or AI tool adoption{topic_context}

Brand voice: {BRAND_GUIDELINES['voice']}

For signal-related content, include: "⚠️ Risk Disclaimer: Trading involves risk. Past performance ≠ future results. Do your own research."

Return ONLY a valid JSON object with no additional text:
{{
  "text": "...",
  "visual_direction": "...",
  "hashtags": ["..."]
}}

Visual directions should be concise (e.g., "Animated chart with uptrend", "Person at trading desk", "Globe with market indicators").
Hashtags should be 3-5 relevant tags for WhatsApp.
"""

        logger.debug(f"Calling Claude API for {pillar} pillar content")

        # Call Claude API
        response = client.messages.create(
            model=claude_settings.get("model", "claude-sonnet-4-20250514"),
            max_tokens=claude_settings.get("max_tokens", 1000),
            temperature=claude_settings.get("temperature", 0.8),
            messages=[
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
        )

        # Parse response
        response_text = response.content[0].text.strip()

        # Extract JSON from response (in case API returns markdown)
        if response_text.startswith("```"):
            json_start = response_text.find("{")
            json_end = response_text.rfind("}") + 1
            if json_start != -1 and json_end > json_start:
                response_text = response_text[json_start:json_end]

        generated_content = json.loads(response_text)

        # Validate character limit
        text = generated_content.get("text", "")
        if len(text) > 700:
            logger.warning(f"Generated text exceeds 700 char limit ({len(text)} chars). Truncating.")
            text = text[:697] + "..."
            generated_content["text"] = text

        # Build result
        result = {
            "text": generated_content.get("text", ""),
            "pillar": pillar,
            "visual_direction": generated_content.get("visual_direction", ""),
            "hashtags": generated_content.get("hashtags", []),
        }

        logger.info(f"Successfully generated WhatsApp Status for pillar: {pillar}")
        return result

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse Claude API response as JSON: {str(e)}")
        raise ValueError(f"Invalid JSON response from API: {str(e)}")
    except Exception as e:
        logger.error(f"Error generating WhatsApp status: {str(e)}")
        raise


# ============================================================================
# CONTENT DISTRIBUTION
# ============================================================================

def get_platform_posting_method(platform: str) -> str:
    """
    Get the posting method for a platform (api or manual).

    Args:
        platform: Platform name

    Returns:
        Posting method: "api" for automatic posting via Railway, "manual" for user download

    Raises:
        ValueError: If platform not found
    """
    config = get_platform_config(platform)
    logger.debug(f"{platform} posting method: {config.posting_method}")
    return config.posting_method


def is_platform_auto_posting(platform: str) -> bool:
    """
    Check if a platform uses automatic posting.

    Args:
        platform: Platform name

    Returns:
        True if platform auto-posts via API, False if manual

    Raises:
        ValueError: If platform not found
    """
    config = get_platform_config(platform)
    return config.auto_posting


# ============================================================================
# VALIDATION & HEALTH CHECKS
# ============================================================================

def validate_platform_config(platform: str) -> bool:
    """
    Validate that a platform configuration is complete and valid.

    Args:
        platform: Platform name

    Returns:
        True if configuration is valid

    Raises:
        ValueError: If configuration is invalid
    """
    try:
        config = get_platform_config(platform)

        # Validate required fields
        if not config.name:
            raise ValueError(f"{platform}: Missing name")
        if not config.brand:
            raise ValueError(f"{platform}: Missing brand")
        if config.character_limit <= 0:
            raise ValueError(f"{platform}: Invalid character limit")

        # For active platforms, validate pillars
        if config.status == PlatformStatus.ACTIVE:
            if not config.pillars:
                raise ValueError(f"{platform}: Active platform must have pillars defined")

            # Validate pillar percentages sum to approximately 1.0
            total = sum(config.pillars.values())
            if not (0.99 <= total <= 1.01):
                raise ValueError(
                    f"{platform}: Pillar percentages must sum to 1.0 (got {total})"
                )

        logger.info(f"Platform config validation passed: {platform}")
        return True

    except ValueError as e:
        logger.error(f"Platform validation failed: {str(e)}")
        raise


def validate_all_platforms() -> bool:
    """
    Validate all platform configurations.

    Returns:
        True if all configurations are valid

    Raises:
        ValueError: If any configuration is invalid
    """
    for platform_name in PLATFORM_CONFIGS.keys():
        validate_platform_config(platform_name)

    logger.info("All platform configurations validated successfully")
    return True


# ============================================================================
# EXPORT & SERIALIZATION
# ============================================================================

def export_platform_configs() -> Dict[str, Dict[str, Any]]:
    """
    Export all platform configurations as a serializable dictionary.

    Returns:
        Dictionary of platform configurations
    """
    return {
        name: config.to_dict()
        for name, config in PLATFORM_CONFIGS.items()
    }


def get_platform_summary() -> Dict[str, Any]:
    """
    Get a summary of all platform configurations and status.

    Returns:
        Summary dictionary with active platforms, capabilities, and configurations
    """
    active = get_active_platforms()
    all_platforms = get_all_platforms()

    summary = {
        "total_platforms": len(all_platforms),
        "active_platforms": len(active),
        "active_platform_names": active,
        "platforms": export_platform_configs(),
        "brand_guidelines": BRAND_GUIDELINES,
        "character_limits": CHARACTER_LIMITS,
    }

    logger.debug("Generated platform summary")
    return summary


# ============================================================================
# INITIALIZATION
# ============================================================================

def initialize_platform_manager() -> bool:
    """
    Initialize the platform manager and validate all configurations.

    Returns:
        True if initialization successful

    Raises:
        ValueError: If any configuration is invalid
    """
    try:
        logger.info("Initializing platform manager...")

        # Validate all platform configurations
        validate_all_platforms()

        # Get summary
        summary = get_platform_summary()
        logger.info(
            f"Platform manager initialized with {summary['active_platforms']} "
            f"active platforms out of {summary['total_platforms']} total"
        )

        return True

    except Exception as e:
        logger.error(f"Platform manager initialization failed: {str(e)}")
        raise


if __name__ == "__main__":
    # Configure logging for standalone execution
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # Initialize platform manager
    try:
        initialize_platform_manager()

        # Display platform summary
        summary = get_platform_summary()
        print("\n=== Gopipways Social Hub Platform Manager ===\n")
        print(f"Active Platforms: {', '.join(summary['active_platform_names'])}")
        print(f"Total Platforms: {summary['total_platforms']}")
        print("\nPlatform Configurations:")
        print(json.dumps(summary['platforms'], indent=2, default=str))

    except Exception as e:
        logger.error(f"Initialization error: {str(e)}")
        print(f"Error: {str(e)}")
        exit(1)
