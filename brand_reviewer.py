"""
Brand Review Engine for Gopipways Social Hub

A comprehensive content review system that validates social media content against
brand guidelines, ensuring compliance with banned words, disclaimers, tone, and voice.

Features:
- Rule-based content review against brand guidelines
- Multi-platform support (LinkedIn, WhatsApp, Instagram, Twitter/X, Threads, Facebook)
- Batch review capabilities
- AI-enhanced deep review using Claude API for nuanced brand voice analysis
- Quick validation checks
- Improvement suggestions powered by Claude

Author: Gopipways Team
"""

import logging
import re
from dataclasses import dataclass, asdict
from typing import List, Dict, Any, Optional, Tuple
from enum import Enum

try:
    import anthropic
except ImportError:
    anthropic = None

# Configure logging
logger = logging.getLogger("brand_reviewer")
logger.setLevel(logging.DEBUG)

# Create console handler if not already present
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)


# ============================================================================
# BRAND RULES - Hardcoded from brand guide
# ============================================================================

BRAND_RULES = {
    "banned_words": [
        "get rich quick",
        "guaranteed profits",
        "easy money",
        "no risk",
        "100% win rate",
        "secret formula",
        "hack the market",
        "passive income from trading",
        "financial freedom overnight",
        "millionaire trader",
    ],
    "required_disclaimers": {
        "signal_keywords": [
            "signal",
            "trade",
            "trading",
            "buy",
            "sell",
            "position",
            "entry",
            "exit",
        ],
        "disclaimer_required": (
            "Trading involves risk. Past performance doesn't guarantee future results."
        ),
    },
    "tone_attributes": {
        "linkedin": {
            "authoritative": True,
            "approachable": True,
            "data_driven": True,
            "story_led": True,
            "pan_african": True,
        },
        "whatsapp_status": {
            "educational": True,
            "product_led": True,
            "direct": True,
            "community_focused": True,
        },
        "instagram": {
            "visual": True,
            "engaging": True,
            "aspirational": True,
            "community_focused": True,
        },
        "x": {
            "concise": True,
            "witty": True,
            "timely": True,
            "conversational": True,
        },
        "threads": {
            "conversational": True,
            "thoughtful": True,
            "community_focused": True,
        },
        "facebook": {
            "accessible": True,
            "relatable": True,
            "community_focused": True,
            "inclusive": True,
        },
    },
    "words_we_use": [
        "traders",
        "edge",
        "smarter",
        "AI-powered",
        "data-driven",
        "practical",
        "real results",
        "community",
    ],
    "words_we_avoid": [
        "guru",
        "expert",
        "master class",
        "forex lifestyle",
        "lambo",
        "rich quick",
    ],
}

# Character limits per platform
CHAR_LIMITS = {
    "linkedin": 3000,
    "whatsapp_status": 700,
    "instagram": 2200,
    "x": 280,
    "threads": 500,
    "facebook": 63206,
}


# ============================================================================
# DATA CLASSES & ENUMS
# ============================================================================


class Severity(Enum):
    """Issue severity levels"""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class PlatformFit(Enum):
    """Platform suitability assessment"""

    GOOD = "good"
    NEEDS_WORK = "needs_work"
    POOR = "poor"


class Readability(Enum):
    """Readability assessment"""

    GOOD = "good"
    MODERATE = "moderate"
    COMPLEX = "complex"


@dataclass
class ReviewIssue:
    """Represents a single content issue"""

    severity: str  # "high", "medium", "low"
    type: str  # issue category (e.g., "banned_word", "missing_disclaimer")
    detail: str  # description of the issue
    suggestion: str  # how to fix it

    def to_dict(self) -> Dict[str, str]:
        """Convert to dictionary"""
        return asdict(self)


@dataclass
class ContentReview:
    """Complete content review result"""

    score: int  # 0-100 overall brand compliance score
    issues: List[Dict[str, str]]  # list of review issues
    strengths: List[str]  # positive findings
    platform_fit: str  # "good", "needs_work", "poor"
    voice_match: bool  # matches expected voice for platform
    word_count: int
    char_count: int
    within_limit: bool
    hashtag_count: int
    has_cta: bool  # has call-to-action
    readability: str  # "good", "moderate", "complex"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return asdict(self)


# ============================================================================
# MAIN BRAND REVIEWER CLASS
# ============================================================================


class BrandReviewer:
    """
    Main brand review engine with rule-based and AI-enhanced review capabilities
    """

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the brand reviewer

        Args:
            api_key: Optional Anthropic API key for AI-enhanced reviews
        """
        self.api_key = api_key
        self.client = None

        if self.api_key and anthropic:
            try:
                self.client = anthropic.Anthropic(api_key=self.api_key)
                logger.info("Anthropic client initialized successfully")
            except Exception as e:
                logger.warning(f"Failed to initialize Anthropic client: {e}")

    # ========================================================================
    # QUICK CHECKS
    # ========================================================================

    def check_banned_words(self, text: str) -> List[str]:
        """
        Check for banned words in text

        Args:
            text: Content to check

        Returns:
            List of found banned words
        """
        found_words = []
        text_lower = text.lower()

        for banned_word in BRAND_RULES["banned_words"]:
            if banned_word.lower() in text_lower:
                found_words.append(banned_word)
                logger.debug(f"Found banned word: {banned_word}")

        return found_words

    def check_disclaimer_needed(self, text: str) -> bool:
        """
        Check if content requires trading/signal disclaimer

        Args:
            text: Content to check

        Returns:
            True if disclaimer is needed
        """
        text_lower = text.lower()
        keywords = BRAND_RULES["required_disclaimers"]["signal_keywords"]

        for keyword in keywords:
            if keyword.lower() in text_lower:
                logger.debug(f"Signal keyword found: {keyword}")
                return True

        return False

    def check_char_limit(
        self, text: str, platform: str = "linkedin"
    ) -> Tuple[bool, int, int]:
        """
        Check character limit for platform

        Args:
            text: Content to check
            platform: Target platform

        Returns:
            Tuple of (within_limit, char_count, max_chars)
        """
        max_chars = CHAR_LIMITS.get(platform, 3000)
        char_count = len(text)
        within_limit = char_count <= max_chars

        logger.debug(
            f"Char limit check for {platform}: {char_count}/{max_chars} "
            f"(within_limit={within_limit})"
        )

        return within_limit, char_count, max_chars

    # ========================================================================
    # ANALYSIS HELPERS
    # ========================================================================

    def _count_hashtags(self, text: str) -> int:
        """Count hashtags in text"""
        return len(re.findall(r"#\w+", text))

    def _has_cta(self, text: str) -> bool:
        """Check if text has a call-to-action"""
        cta_keywords = [
            "click here",
            "join",
            "sign up",
            "register",
            "learn more",
            "discover",
            "explore",
            "get started",
            "download",
            "share",
            "comment",
            "follow",
            "subscribe",
            "apply",
        ]

        text_lower = text.lower()
        return any(cta in text_lower for cta in cta_keywords)

    def _assess_readability(self, text: str) -> str:
        """
        Assess content readability using simple heuristics

        Returns: "good", "moderate", or "complex"
        """
        avg_word_length = sum(len(word) for word in text.split()) / max(
            len(text.split()), 1
        )
        avg_sentence_length = len(text.split()) / max(len(text.split("\n")), 1)

        # Heuristic scoring
        if avg_word_length > 6 and avg_sentence_length > 20:
            return Readability.COMPLEX.value
        elif avg_word_length > 5.5 or avg_sentence_length > 15:
            return Readability.MODERATE.value
        else:
            return Readability.GOOD.value

    def _check_words_we_use(self, text: str) -> List[str]:
        """Find words from our approved vocabulary"""
        found = []
        text_lower = text.lower()

        for word in BRAND_RULES["words_we_use"]:
            if word.lower() in text_lower:
                found.append(word)

        return found

    def _check_words_we_avoid(self, text: str) -> List[str]:
        """Find words we should avoid"""
        found = []
        text_lower = text.lower()

        for word in BRAND_RULES["words_we_avoid"]:
            if word.lower() in text_lower:
                found.append(word)

        return found

    def _calculate_score(
        self,
        issues: List[ReviewIssue],
        strengths: List[str],
        word_count: int,
        within_limit: bool,
    ) -> int:
        """
        Calculate overall brand compliance score (0-100)

        Score calculation:
        - Start at 100
        - Deduct points for issues (high: -20, medium: -10, low: -5)
        - Add points for strengths (up to +10)
        - Deduct points if over limit (-15)
        - Adjust for word count (min 20 words recommended for social)
        """
        score = 100

        # Deduct for issues
        for issue in issues:
            if issue.severity == Severity.HIGH.value:
                score -= 20
            elif issue.severity == Severity.MEDIUM.value:
                score -= 10
            elif issue.severity == Severity.LOW.value:
                score -= 5

        # Add for strengths (capped at +10)
        strength_bonus = min(len(strengths) * 2, 10)
        score += strength_bonus

        # Deduct for being over limit
        if not within_limit:
            score -= 15

        # Deduct if too short
        if word_count < 10:
            score -= 10

        # Clamp score between 0 and 100
        return max(0, min(100, score))

    # ========================================================================
    # MAIN REVIEW FUNCTION
    # ========================================================================

    def review_content(self, text: str, platform: str = "linkedin") -> ContentReview:
        """
        Review content against brand guidelines

        Args:
            text: Content to review
            platform: Target platform (linkedin, whatsapp_status, instagram, x, threads, facebook)

        Returns:
            ContentReview object with detailed analysis
        """
        logger.info(f"Starting review for platform: {platform}")

        # Initialize results storage
        issues = []
        strengths = []

        # Basic metrics
        word_count = len(text.split())
        char_count = len(text)
        within_limit, actual_chars, max_chars = self.check_char_limit(text, platform)
        hashtag_count = self._count_hashtags(text)
        has_cta = self._has_cta(text)
        readability = self._assess_readability(text)

        # Check 1: Banned words
        banned_words = self.check_banned_words(text)
        for word in banned_words:
            issues.append(
                ReviewIssue(
                    severity=Severity.HIGH.value,
                    type="banned_word",
                    detail=f"Contains '{word}'",
                    suggestion=f"Replace with brand-approved alternative",
                )
            )

        # Check 2: Words we avoid
        avoided_words = self._check_words_we_avoid(text)
        for word in avoided_words:
            issues.append(
                ReviewIssue(
                    severity=Severity.MEDIUM.value,
                    type="voice_mismatch",
                    detail=f"Uses avoided word: '{word}'",
                    suggestion=f"Replace with word from our approved vocabulary",
                )
            )

        # Check 3: Required disclaimers
        if self.check_disclaimer_needed(text):
            if BRAND_RULES["required_disclaimers"]["disclaimer_required"] not in text:
                issues.append(
                    ReviewIssue(
                        severity=Severity.HIGH.value,
                        type="missing_disclaimer",
                        detail="Signal/trade content requires risk disclaimer",
                        suggestion=(
                            "Add: 'Trading involves risk. Past performance doesn't "
                            "guarantee future results.'"
                        ),
                    )
                )

        # Check 4: Character limit
        if not within_limit:
            issues.append(
                ReviewIssue(
                    severity=Severity.HIGH.value,
                    type="char_limit_exceeded",
                    detail=f"Content exceeds {platform} limit: {actual_chars}/{max_chars}",
                    suggestion=f"Reduce content by {actual_chars - max_chars} characters",
                )
            )

        # Check 5: Platform-specific tone attributes
        # For LinkedIn, check for data-driven language and professional tone
        if platform == "linkedin":
            if word_count < 50:
                issues.append(
                    ReviewIssue(
                        severity=Severity.LOW.value,
                        type="length_concern",
                        detail="Very brief for LinkedIn (recommended 50+ words)",
                        suggestion="Expand with more context, data, or insights",
                    )
                )

        # Check 6: Minimum content length
        if word_count < 10:
            issues.append(
                ReviewIssue(
                    severity=Severity.HIGH.value,
                    type="too_short",
                    detail="Content too brief for meaningful engagement",
                    suggestion="Expand content with more substance",
                )
            )

        # Strengths assessment
        words_we_use = self._check_words_we_use(text)
        if words_we_use:
            strengths.append(f"Uses brand vocabulary: {', '.join(words_we_use[:3])}")

        if has_cta:
            strengths.append("Has clear call-to-action")

        if readability == Readability.GOOD.value:
            strengths.append("Excellent readability")

        if platform == "linkedin" and word_count >= 100:
            strengths.append("Substantial content length for LinkedIn")

        if hashtag_count > 0 and hashtag_count <= 5:
            strengths.append(f"Appropriate hashtag count ({hashtag_count})")

        # Calculate compliance score
        score = self._calculate_score(issues, strengths, word_count, within_limit)

        # Determine platform fit
        if score >= 80:
            platform_fit = PlatformFit.GOOD.value
        elif score >= 60:
            platform_fit = PlatformFit.NEEDS_WORK.value
        else:
            platform_fit = PlatformFit.POOR.value

        # Voice match: check if using our vocabulary
        voice_match = len(words_we_use) > 0 and len(avoided_words) == 0

        logger.info(f"Review complete. Score: {score}, Issues: {len(issues)}")

        return ContentReview(
            score=score,
            issues=[issue.to_dict() for issue in issues],
            strengths=strengths,
            platform_fit=platform_fit,
            voice_match=voice_match,
            word_count=word_count,
            char_count=char_count,
            within_limit=within_limit,
            hashtag_count=hashtag_count,
            has_cta=has_cta,
            readability=readability,
        )

    # ========================================================================
    # BATCH REVIEW
    # ========================================================================

    def review_batch(
        self, posts: List[Dict[str, str]]
    ) -> List[Dict[str, Any]]:
        """
        Review multiple posts in batch

        Args:
            posts: List of dicts with 'text' and optional 'platform' keys

        Returns:
            List of ContentReview dicts
        """
        logger.info(f"Starting batch review of {len(posts)} posts")
        results = []

        for idx, post in enumerate(posts):
            text = post.get("text", "")
            platform = post.get("platform", "linkedin")

            review = self.review_content(text, platform)
            results.append(review.to_dict())

            logger.debug(f"Batch review {idx + 1}/{len(posts)} complete")

        logger.info(f"Batch review complete. Processed {len(results)} posts")
        return results

    # ========================================================================
    # AI-ENHANCED DEEP REVIEW
    # ========================================================================

    def deep_review(self, text: str, platform: str = "linkedin") -> ContentReview:
        """
        AI-enhanced brand review using Claude API

        Performs rule-based review plus leverages Claude for nuanced brand voice
        analysis, semantic understanding of tone, and AI-generated suggestions.

        Args:
            text: Content to review
            platform: Target platform

        Returns:
            ContentReview object with AI-enhanced analysis
        """
        if not self.client:
            logger.warning(
                "Anthropic client not available. Falling back to rule-based review."
            )
            return self.review_content(text, platform)

        logger.info(f"Starting deep review (AI-enhanced) for {platform}")

        # Get baseline rule-based review
        base_review = self.review_content(text, platform)

        # Prepare AI analysis prompt
        tone_attrs = BRAND_RULES["tone_attributes"].get(
            platform, BRAND_RULES["tone_attributes"]["linkedin"]
        )
        tone_str = ", ".join(
            [k for k, v in tone_attrs.items() if v is True]
        )

        prompt = f"""You are a brand voice expert for Gopipways Social Hub, a fintech/trading education platform.

Review this social media content for brand alignment. The content is for {platform}.

BRAND VOICE ATTRIBUTES FOR {platform.upper()}:
{tone_str}

BRAND VOCABULARY TO USE:
{', '.join(BRAND_RULES['words_we_use'])}

WORDS/PHRASES TO AVOID:
{', '.join(BRAND_RULES['words_we_avoid'])}

CONTENT TO REVIEW:
\"{text}\"

Provide a JSON response with:
1. "tone_assessment": brief assessment of tone alignment (authoritative, approachable, etc.)
2. "voice_strengths": list of 2-3 specific strengths that match brand voice
3. "voice_improvements": list of 2-3 specific improvements for better brand alignment
4. "semantic_issues": any subtle messaging issues not caught by simple rules
5. "overall_assessment": one sentence summary

Format as valid JSON only, no markdown."""

        try:
            message = self.client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=1024,
                messages=[{"role": "user", "content": prompt}],
            )

            response_text = message.content[0].text
            logger.debug(f"Claude response: {response_text}")

            # Parse Claude's response (it should be JSON)
            import json

            try:
                ai_analysis = json.loads(response_text)
            except json.JSONDecodeError:
                logger.warning("Failed to parse Claude response as JSON")
                ai_analysis = {}

            # Enhance the base review with AI insights
            enhanced_review = base_review.to_dict()

            # Add AI-generated strengths
            if "voice_strengths" in ai_analysis:
                enhanced_review["strengths"].extend(
                    ai_analysis.get("voice_strengths", [])[:2]
                )

            # Add AI-identified issues
            if "voice_improvements" in ai_analysis:
                for improvement in ai_analysis.get("voice_improvements", [])[:2]:
                    enhanced_review["issues"].append(
                        {
                            "severity": "medium",
                            "type": "voice_improvement",
                            "detail": improvement,
                            "suggestion": "Consider this refinement for better brand alignment",
                        }
                    )

            if "semantic_issues" in ai_analysis:
                for issue in ai_analysis.get("semantic_issues", []):
                    enhanced_review["issues"].append(
                        {
                            "severity": "low",
                            "type": "semantic",
                            "detail": issue,
                            "suggestion": "Subtle adjustment may strengthen messaging",
                        }
                    )

            # Recalculate score with AI findings
            issue_count = len(enhanced_review["issues"])
            strength_count = len(enhanced_review["strengths"])

            # Re-score
            base_score = enhanced_review["score"]
            new_score = max(
                0,
                min(
                    100,
                    base_score
                    + (strength_count * 2)
                    - (issue_count * 3),
                ),
            )
            enhanced_review["score"] = new_score

            logger.info(
                f"Deep review complete. AI-enhanced score: {enhanced_review['score']}"
            )

            # Convert back to ContentReview
            return ContentReview(**enhanced_review)

        except Exception as e:
            logger.error(f"Error during deep review: {e}")
            logger.info("Returning rule-based review instead")
            return base_review

    # ========================================================================
    # IMPROVEMENT SUGGESTIONS
    # ========================================================================

    def suggest_improvements(
        self, text: str, platform: str = "linkedin"
    ) -> Dict[str, Any]:
        """
        Use Claude to suggest specific improvements for content

        Args:
            text: Content to improve
            platform: Target platform

        Returns:
            Dict with improvement suggestions
        """
        if not self.client:
            logger.warning("Anthropic client not available. Cannot generate suggestions.")
            return {
                "suggestions": [],
                "revised_snippet": None,
                "error": "API client not initialized",
            }

        logger.info(f"Generating improvement suggestions for {platform}")

        # Get current review
        review = self.review_content(text, platform)

        # Build prompt for improvements
        issues_summary = "\n".join(
            [f"- {issue['severity'].upper()}: {issue['detail']}" for issue in review.issues]
        )

        prompt = f"""You are a brand copywriter for Gopipways Social Hub.

The following content needs improvement:

CURRENT CONTENT:
\"{text}\"

TARGET PLATFORM: {platform}

IDENTIFIED ISSUES:
{issues_summary if issues_summary else "No major issues identified."}

BRAND GUIDELINES:
- Use vocabulary like: {', '.join(BRAND_RULES['words_we_use'][:5])}
- Avoid: {', '.join(BRAND_RULES['words_we_avoid'])}
- For {platform}: {', '.join(k for k in BRAND_RULES['tone_attributes'].get(platform, {}).keys() if BRAND_RULES['tone_attributes'].get(platform, {}).get(k))}

Provide a JSON response with:
1. "improvements": list of specific, actionable improvements
2. "revised_sample": a 1-2 sentence revision showing the improved style
3. "priority": which issues to fix first (list them in order)
4. "estimated_impact": how much this could improve the content

Format as valid JSON only."""

        try:
            message = self.client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=1024,
                messages=[{"role": "user", "content": prompt}],
            )

            response_text = message.content[0].text
            logger.debug(f"Suggestions response: {response_text}")

            import json

            try:
                suggestions = json.loads(response_text)
                logger.info("Improvement suggestions generated successfully")
                return suggestions
            except json.JSONDecodeError:
                logger.warning("Failed to parse suggestions as JSON")
                return {
                    "suggestions": [response_text],
                    "revised_sample": None,
                    "error": "Response parsing error",
                }

        except Exception as e:
            logger.error(f"Error generating suggestions: {e}")
            return {
                "suggestions": [],
                "revised_sample": None,
                "error": str(e),
            }


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================


def review_content(text: str, platform: str = "linkedin", api_key: Optional[str] = None) -> ContentReview:
    """
    Convenience function to review content

    Args:
        text: Content to review
        platform: Target platform
        api_key: Optional API key for AI features

    Returns:
        ContentReview object
    """
    reviewer = BrandReviewer(api_key=api_key)
    return reviewer.review_content(text, platform)


def review_batch(posts: List[Dict[str, str]], api_key: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Convenience function to review multiple posts

    Args:
        posts: List of post dicts with 'text' and optional 'platform'
        api_key: Optional API key for AI features

    Returns:
        List of ContentReview dicts
    """
    reviewer = BrandReviewer(api_key=api_key)
    return reviewer.review_batch(posts)


def deep_review(text: str, platform: str = "linkedin", api_key: Optional[str] = None) -> ContentReview:
    """
    Convenience function to perform AI-enhanced review

    Args:
        text: Content to review
        platform: Target platform
        api_key: Optional API key (required for AI features)

    Returns:
        ContentReview object with AI-enhanced analysis
    """
    reviewer = BrandReviewer(api_key=api_key)
    return reviewer.deep_review(text, platform)


def check_banned_words(text: str) -> List[str]:
    """Convenience function to check for banned words"""
    reviewer = BrandReviewer()
    return reviewer.check_banned_words(text)


def check_disclaimer_needed(text: str) -> bool:
    """Convenience function to check if disclaimer is needed"""
    reviewer = BrandReviewer()
    return reviewer.check_disclaimer_needed(text)


def check_char_limit(text: str, platform: str = "linkedin") -> Tuple[bool, int, int]:
    """Convenience function to check character limit"""
    reviewer = BrandReviewer()
    return reviewer.check_char_limit(text, platform)


def suggest_improvements(
    text: str, platform: str = "linkedin", api_key: Optional[str] = None
) -> Dict[str, Any]:
    """Convenience function to get improvement suggestions"""
    reviewer = BrandReviewer(api_key=api_key)
    return reviewer.suggest_improvements(text, platform)


if __name__ == "__main__":
    # Example usage
    logger.info("Brand Reviewer module loaded successfully")

    # Example post
    sample_post = """
    Excited to share our latest AI-powered trading signal analysis with the community!
    Our data-driven approach helps traders make smarter decisions. Check out the results
    from last month - real traders, real results. No guarantees, but you'll get practical
    insights you can actually use.

    #trading #AI #datadriven
    """

    # Basic review
    print("\n" + "=" * 60)
    print("BASIC REVIEW (Rule-based)")
    print("=" * 60)
    reviewer = BrandReviewer()
    review = reviewer.review_content(sample_post, "linkedin")
    print(f"Score: {review.score}")
    print(f"Platform Fit: {review.platform_fit}")
    print(f"Issues: {len(review.issues)}")
    for issue in review.issues:
        print(f"  - [{issue['severity']}] {issue['detail']}")
    print(f"Strengths: {review.strengths}")
