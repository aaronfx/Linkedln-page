"""
Content Rewriter — Adlytics-Powered Auto-Rewrite for Failed Posts
==================================================================
Adapted from the Adlytics rewrite engine.
When a post scores below the threshold, this module rewrites it
using the scorer's feedback to target specific weaknesses.

Integration:
  from content_rewriter import rewrite_post
  result = rewrite_post(original_text, score_result, platform="linkedin")
  improved_text = result["rewritten_text"]
"""

import json
import re
import logging
from typing import Dict, Any, Optional, List

from anthropic import Anthropic
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from config import ANTHROPIC_API_KEY, CLAUDE_SETTINGS
from knowledge_base import BRAND_VOICE

logger = logging.getLogger("content_rewriter")

_client = Anthropic(api_key=ANTHROPIC_API_KEY)

# ── Rewrite modes (from Adlytics) ───────────────────────────────────────
REWRITE_MODES = {
    "engaging": "Increase emotional hooks, relatability, conversational tone",
    "hard_sell": "Direct, benefit-heavy, urgency, scarcity tactics",
    "social_proof": "Testimonials, numbers, trust signals, authority markers",
    "urgency": "Time limits, limited availability, FOMO triggers",
    "storytelling": "Narrative arc, relatable character, problem-solution journey",
    "playful": "Fun tone, humor, Gen-Z/millennial friendly, informal",
}

# Which mode to auto-select based on the weakest dimension
_AUTO_MODE_MAP = {
    "hook_strength": "engaging",
    "credibility": "social_proof",
    "emotional_pull": "storytelling",
    "cta_strength": "urgency",
    "clarity": "engaging",
    "audience_match": "engaging",
    "platform_fit": "engaging",
}


def _pick_rewrite_mode(scores: Dict[str, int]) -> str:
    """Auto-select the best rewrite mode based on the weakest scoring dimension."""
    dimension_scores = {k: v for k, v in scores.items() if k != "overall"}
    if not dimension_scores:
        return "engaging"
    weakest = min(dimension_scores, key=dimension_scores.get)
    mode = _AUTO_MODE_MAP.get(weakest, "engaging")
    logger.info(f"Auto-selected rewrite mode '{mode}' (weakest: {weakest}={dimension_scores[weakest]})")
    return mode


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=2, min=4, max=30),
    retry=retry_if_exception_type((Exception,)),
)
def _claude_call(system: str, user: str, max_tokens: int = 4000) -> str:
    """Call Claude and return raw text."""
    response = _client.messages.create(
        model=CLAUDE_SETTINGS["model"],
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return response.content[0].text.strip()


def rewrite_post(
    original_text: str,
    score_result: Dict[str, Any],
    platform: str = "linkedin",
    rewrite_mode: Optional[str] = None,
    pillar: str = "",
    brand_voice_override: str = "",
) -> Dict[str, Any]:
    """
    Rewrite a post that failed the quality gate.

    Args:
        original_text: The post that scored below threshold
        score_result: Output from content_scorer.score_post()
        platform: Target platform
        rewrite_mode: Force a mode, or None for auto-select
        pillar: Content pillar (for context)
        brand_voice_override: Custom brand voice block; defaults to knowledge_base.BRAND_VOICE

    Returns:
        {
            "rewritten_text": str,
            "mode_used": str,
            "changes_summary": [str],
            "estimated_score_lift": str,
        }
    """
    scores = score_result.get("scores", {})
    weaknesses = score_result.get("critical_weaknesses", [])
    fix_hint = score_result.get("what_to_change_right_now", "")

    mode = rewrite_mode or _pick_rewrite_mode(scores)
    mode_desc = REWRITE_MODES.get(mode, REWRITE_MODES["engaging"])
    voice = brand_voice_override or BRAND_VOICE

    weaknesses_text = "\n".join(
        f"- [{w.get('severity', '?')}] {w.get('issue', '')} → Fix: {w.get('precise_fix', '')}"
        for w in weaknesses[:5]
    ) if weaknesses else "General quality improvement needed."

    system_prompt = f"""You are an expert social media copywriter specialising in {platform.upper()} content.
You follow the brand voice EXACTLY.

{voice}

Your task: rewrite the post below to fix the identified weaknesses while keeping the core message intact."""

    user_prompt = f"""ORIGINAL POST (scored {scores.get('overall', '?')}/100 — below the 70 threshold):
━━━━━━━━━━━━━━━━━━━━━━
{original_text}
━━━━━━━━━━━━━━━━━━━━━━

DIMENSION SCORES:
{json.dumps({k: v for k, v in scores.items() if k != 'overall'}, indent=2)}

CRITICAL WEAKNESSES:
{weaknesses_text}

MOST IMPACTFUL CHANGE:
{fix_hint}

REWRITE MODE: {mode.upper()} — {mode_desc}

PILLAR: {pillar or 'General'}
PLATFORM: {platform.upper()}

REQUIREMENTS:
1. Fix EVERY weakness listed above
2. Keep the core topic, message, and any specific data/numbers
3. Must feel natural for {platform.upper()} — correct length, tone, format
4. Hook must be stronger (first 1-2 lines grab attention)
5. Include a clear CTA if the original was missing one
6. Match the brand voice above exactly
7. Do NOT add hashtags — those are handled separately
8. Output the rewritten post text ONLY — no JSON, no explanation, no preamble

Write the improved post now:"""

    logger.info(f"Rewriting post | mode={mode} | original_score={scores.get('overall')}")

    try:
        rewritten = _claude_call(system_prompt, user_prompt, max_tokens=2000)

        # Strip any accidental markdown fences
        if rewritten.startswith("```"):
            rewritten = re.sub(r"```\w*\n?", "", rewritten).strip()

        # Build changes summary
        changes = []
        if scores.get("hook_strength", 100) < 60:
            changes.append("Strengthened opening hook")
        if scores.get("credibility", 100) < 60:
            changes.append("Added proof/credibility elements")
        if scores.get("emotional_pull", 100) < 60:
            changes.append("Increased emotional resonance")
        if scores.get("cta_strength", 100) < 60:
            changes.append("Improved call-to-action")
        if scores.get("audience_match", 100) < 60:
            changes.append("Tailored language for target audience")
        if scores.get("platform_fit", 100) < 60:
            changes.append(f"Optimised format for {platform}")
        if not changes:
            changes.append(f"Applied {mode} rewrite mode for overall improvement")

        return {
            "rewritten_text": rewritten,
            "mode_used": mode,
            "changes_summary": changes,
            "estimated_score_lift": f"+{max(5, 70 - scores.get('overall', 50))} points (estimated)",
        }

    except Exception as e:
        logger.error(f"Rewrite failed: {e} — returning original")
        return {
            "rewritten_text": original_text,
            "mode_used": "none (failed)",
            "changes_summary": [f"Rewrite failed: {str(e)[:100]}"],
            "estimated_score_lift": "+0",
        }
