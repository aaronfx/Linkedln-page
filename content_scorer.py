"""
Content Scorer — Adlytics-Powered Quality Gate for Social Posts
================================================================
Adapted from the Adlytics AI Engine v7.0 scoring system.
Uses Anthropic Claude (same as the social engine) instead of OpenAI.

Two-pass scoring:
  1. Chain-of-thought analysis → 7 dimension scores
  2. Critic pass → challenges inflated scores

Integration:
  from content_scorer import score_post, SCORE_THRESHOLD
  result = score_post(text, platform="linkedin", audience_country="nigeria")
  if result["scores"]["overall"] >= SCORE_THRESHOLD:
      publish(post)
  else:
      rewritten = rewrite_post(text, result)  # from content_rewriter.py
"""

import json
import re
import hashlib
import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict

from anthropic import Anthropic
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from config import ANTHROPIC_API_KEY, CLAUDE_SETTINGS

logger = logging.getLogger("content_scorer")

# ── Score gate threshold (configurable) ──────────────────────────────────
SCORE_THRESHOLD = 70

# ── Scoring weights (from Adlytics v7.0) ────────────────────────────────
SCORING_WEIGHTS = {
    "hook_strength":  0.25,
    "credibility":    0.20,
    "emotional_pull": 0.20,
    "cta_strength":   0.15,
    "clarity":        0.10,
    "audience_match": 0.05,
    "platform_fit":   0.05,
}

# ── Claude client (shared with content_engine) ──────────────────────────
_client = Anthropic(api_key=ANTHROPIC_API_KEY)


# ══════════════════════════════════════════════════════════════════════════
# CONTENT FINGERPRINTING
# ══════════════════════════════════════════════════════════════════════════

@dataclass
class ContentFingerprint:
    content_hash: str
    word_count: int
    first_20_chars: str
    last_20_chars: str
    has_trauma_pattern: bool
    has_scam_pattern: bool
    emotional_keywords: List[str]
    sentence_count: int
    has_specific_numbers: bool
    has_social_proof: bool
    has_cta: bool


def fingerprint_content(content: str) -> ContentFingerprint:
    """Analyse content structure for scoring validation."""
    cl = content.lower()
    emotional_words = [
        "lost", "pain", "struggle", "truth", "honest", "transparent",
        "scam", "fear", "worry", "stress", "failed", "quit", "stop",
        "burned", "cheated", "mistake", "regret", "frustrated",
    ]
    trauma_patterns = [
        "i lost", "i failed", "i quit", "i stopped", "burned",
        "scammed", "lost ₦", "lost $", "lost £", "wasted", "threw away",
    ]
    scam_patterns = [
        "guarantee", "guaranteed", "no experience needed", "risk free",
        "risk-free", "10x your", "100% profit", "get rich", "overnight",
    ]
    number_patterns = [
        r'\d+[%xX]', r'₦\d', r'\$\d', r'£\d', r'\d+k',
        r'\d+,\d{3}', r'\d+ days', r'\d+ weeks', r'\d+ months',
    ]
    proof_patterns = [
        "testimonial", "screenshot", "verified", "track record",
        "client", "student", "member", "case study", "results", "proof",
    ]
    cta_patterns = [
        "dm", "whatsapp", "click", "call", "comment", "sign up",
        "register", "join", "get started", "book", "apply", "download",
        "tap", "follow", "share", "repost", "save this",
    ]
    return ContentFingerprint(
        content_hash=hashlib.md5(content.encode()).hexdigest()[:8],
        word_count=len(content.split()),
        first_20_chars=content[:20].strip(),
        last_20_chars=content[-20:].strip() if len(content) >= 20 else content.strip(),
        has_trauma_pattern=any(p in cl for p in trauma_patterns),
        has_scam_pattern=any(p in cl for p in scam_patterns),
        emotional_keywords=[w for w in emotional_words if w in cl],
        sentence_count=len(re.split(r'[.!?\n]+', content.strip())),
        has_specific_numbers=any(re.search(p, content) for p in number_patterns),
        has_social_proof=any(p in cl for p in proof_patterns),
        has_cta=any(p in cl for p in cta_patterns),
    )


def validate_scores(scores: Dict[str, int], fp: ContentFingerprint) -> tuple:
    """Check score plausibility against fingerprint facts."""
    vals = [v for k, v in scores.items() if k != "overall"]
    if not vals:
        return False, "No scores returned"
    if len(set(vals)) <= 2:
        return False, "Scores too uniform — generic response"
    if max(vals) - min(vals) < 15:
        return False, f"Score spread too narrow ({max(vals) - min(vals)}pts)"
    if fp.has_trauma_pattern and scores.get("emotional_pull", 0) < 60:
        return False, "Trauma content must score emotional_pull ≥ 60"
    if fp.has_scam_pattern and scores.get("credibility", 0) > 40:
        return False, "Scam content must score credibility ≤ 40"
    return True, "OK"


# ══════════════════════════════════════════════════════════════════════════
# AUDIENCE PSYCHOLOGY PROFILES
# ══════════════════════════════════════════════════════════════════════════

AUDIENCE_PROFILES = {
    "nigeria": {
        "skepticism": "Very high — scam fatigue from endless 'make money' ads. Needs specific proof.",
        "trust_cues": "Track record screenshots, C of O documents, specific naira amounts, known landmarks.",
        "cta_style": "WhatsApp DM or 'Comment INFO' — not 'click here'. Low-friction next step.",
        "taboos": "Guaranteed returns, unrealistic income claims, foreign currency emphasis.",
        "currency": "₦",
    },
    "ghana": {
        "skepticism": "High — similar to Nigeria but more receptive to fintech/crypto messaging.",
        "trust_cues": "GH₵ amounts, local bank names, Accra/Kumasi references.",
        "cta_style": "WhatsApp or direct call. Mobile-first audience.",
        "taboos": "Dollar-dominated copy, unrealistic promises.",
        "currency": "GH₵",
    },
    "uk": {
        "skepticism": "Moderate — FCA-trained audience expects regulatory disclosure.",
        "trust_cues": "FCA registration numbers, FSCS protection mention, named reviews.",
        "cta_style": "Website link with clear privacy policy. Email capture.",
        "taboos": "Guarantees, non-FCA claims, pressure tactics.",
        "currency": "£",
    },
    "us": {
        "skepticism": "Moderate — SEC-aware for finance. Reviews and social proof convert well.",
        "trust_cues": "BBB rating, verified reviews, SEC/FINRA mentions for finance.",
        "cta_style": "Clear CTA button, free trial or lead magnet.",
        "taboos": "Unsubstantiated income claims (FTC), testimonials without disclaimer.",
        "currency": "$",
    },
    "south_africa": {
        "skepticism": "High — cautious about online finance. Values local credibility.",
        "trust_cues": "FSCA references, ZAR amounts, Johannesburg/Cape Town mentions.",
        "cta_style": "WhatsApp or website. Mobile-heavy audience.",
        "taboos": "Get-rich-quick, foreign currency dominance, ignoring load shedding reality.",
        "currency": "R",
    },
    "kenya": {
        "skepticism": "Moderate-high — M-Pesa generation is tech-savvy but cautious.",
        "trust_cues": "KES amounts, M-Pesa integration mentions, Nairobi references.",
        "cta_style": "M-Pesa or WhatsApp. Mobile-first.",
        "taboos": "Ignoring mobile-money culture, dollar-only pricing.",
        "currency": "KSh",
    },
}

OCCUPATION_PSYCHOLOGY = {
    "entrepreneur": "Busy, result-oriented. Responds to ROI and time-saving.",
    "professional": "Risk-averse, credentials matter. Needs social proof from peers.",
    "student": "Budget-conscious, aspirational. Responds to 'start small' messaging.",
    "trader": "Highly skeptical of claims. Wants specific data, not stories.",
    "blue_collar": "Values simplicity, directness. Responds to family/security framing.",
    "creative": "Trend-aware, aesthetic-sensitive. Needs to see the 'cool factor'.",
}

INCOME_PSYCHOLOGY = {
    "low": "Price-sensitive. Must see clear ROI before any spend.",
    "middle": "Aspirational. Wants quality but watches price.",
    "high": "Quality-first. Price secondary. Exclusivity and expertise matter.",
    "affluent": "Time is priority. Concierge-level trust. Peer validation.",
}

AGE_PSYCHOLOGY = {
    "18-24": "Short attention span, trend-driven. Hook must land in 1 second.",
    "25-34": "Career-driven, comparing options. Responds to specificity.",
    "35-44": "Family-focused, stability-seeking. Trust outweighs hype.",
    "45-54": "Established, cautious. Prefers detailed information.",
    "55+": "Security-focused, brand-loyal. Needs clarity, no jargon.",
}


def build_audience_context(
    country: str = "nigeria",
    age: str = "25-34",
    income: str = "middle",
    occupation: str = "trader",
    platform: str = "linkedin",
) -> str:
    """Build rich audience psychology block for the scoring prompt."""
    country_ctx = AUDIENCE_PROFILES.get(country.lower(), AUDIENCE_PROFILES["nigeria"])
    age_ctx = AGE_PSYCHOLOGY.get(age.split(",")[0].strip(), AGE_PSYCHOLOGY["25-34"])
    income_ctx = INCOME_PSYCHOLOGY.get(income, INCOME_PSYCHOLOGY["middle"])
    occ_ctx = OCCUPATION_PSYCHOLOGY.get(occupation, "General audience.")

    platform_notes = {
        "linkedin": "Professional tone. Long-form tolerated. Value-driven, thought leadership converts. CTA = comment/follow.",
        "facebook": "Longer copy tolerated. Social proof + clear CTA. Cold audiences need trust-building.",
        "instagram": "Visual-first. Aspirational framing. Story format preferred. Short punchy captions.",
        "threads": "Conversational, Twitter-like. Thread format for depth. Authentic voice wins.",
        "tiktok": "Videos 15-60s. Hook in 0-2s. Casual, authentic tone. Text overlays essential.",
        "whatsapp": "Status format. Max 700 chars. Direct, personal tone. Mobile-first. Must feel like a message from a friend.",
    }.get(platform.lower(), "General social media post.")

    return f"""
TARGET AUDIENCE PROFILE:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Country: {country.title()} | Currency: {country_ctx['currency']}
Age: {age} → {age_ctx}
Income: {income} → {income_ctx}
Occupation: {occupation} → {occ_ctx}
Skepticism: {country_ctx['skepticism']}
Trust signals: {country_ctx['trust_cues']}
CTA style: {country_ctx['cta_style']}
Avoid: {country_ctx['taboos']}
Platform: {platform.upper()} → {platform_notes}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"""


# ══════════════════════════════════════════════════════════════════════════
# CLAUDE API WRAPPER
# ══════════════════════════════════════════════════════════════════════════

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=2, min=4, max=30),
    retry=retry_if_exception_type((Exception,)),
)
def _claude_json(system: str, user: str, max_tokens: int = 4000) -> Dict[str, Any]:
    """Call Claude and parse JSON response."""
    response = _client.messages.create(
        model=CLAUDE_SETTINGS["model"],
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    raw = response.content[0].text.strip()
    # Strip markdown fences if present
    raw = re.sub(r"```json|```", "", raw).strip()
    return json.loads(raw)


# ══════════════════════════════════════════════════════════════════════════
# RECALCULATE OVERALL
# ══════════════════════════════════════════════════════════════════════════

def _recalc_overall(scores: Dict[str, int]) -> int:
    total = sum(scores.get(k, 50) * w for k, w in SCORING_WEIGHTS.items())
    return min(98, max(1, round(total)))


# ══════════════════════════════════════════════════════════════════════════
# HEURISTIC FALLBACK
# ══════════════════════════════════════════════════════════════════════════

def _fallback_scores(fp: ContentFingerprint) -> Dict[str, int]:
    """Generate heuristic scores when the AI call fails entirely."""
    import random
    base = 35
    scores = {
        "hook_strength": base + (15 if fp.has_specific_numbers else 0) + random.randint(-5, 10),
        "clarity": base + 10 + random.randint(-5, 10),
        "credibility": base + (15 if fp.has_social_proof else 0) - (20 if fp.has_scam_pattern else 0) + random.randint(-5, 10),
        "emotional_pull": base + (20 if fp.has_trauma_pattern else 0) + (5 if fp.emotional_keywords else 0) + random.randint(-5, 10),
        "cta_strength": base + (10 if fp.has_cta else -10) + random.randint(-5, 10),
        "audience_match": base + random.randint(-5, 10),
        "platform_fit": base + random.randint(-5, 10),
    }
    scores = {k: max(5, min(95, v)) for k, v in scores.items()}
    scores["overall"] = _recalc_overall(scores)
    return scores


# ══════════════════════════════════════════════════════════════════════════
# SCORING PROMPTS
# ══════════════════════════════════════════════════════════════════════════

def _build_scoring_prompt(content: str, fp: ContentFingerprint, audience_block: str, platform: str) -> str:
    """Chain-of-thought scoring prompt (Stage 1)."""
    return f"""You are CONTENT SCORER v1.0 — a rigorous social media post quality evaluator.

CONTENT FINGERPRINT: {fp.content_hash}
FIRST WORDS: "{fp.first_20_chars}"
LAST WORDS: "{fp.last_20_chars}"
WORD COUNT: {fp.word_count}
HAS TRAUMA PATTERN: {fp.has_trauma_pattern}
HAS SCAM PATTERN: {fp.has_scam_pattern}
HAS SPECIFIC NUMBERS: {fp.has_specific_numbers}
HAS SOCIAL PROOF: {fp.has_social_proof}
HAS CTA: {fp.has_cta}

{audience_block}

POST CONTENT TO SCORE:
━━━━━━━━━━━━━━━━━━━━━━
{content}
━━━━━━━━━━━━━━━━━━━━━━

STEP 1 — LINE-BY-LINE REASONING (do this BEFORE scoring):
Read every sentence. For each, identify:
a) What psychological trigger it activates (or fails to)
b) Whether it would make this SPECIFIC audience stop scrolling, trust, or engage
c) Any weakness, vague claim, or missing proof element

STEP 2 — SCORE EACH DIMENSION (0–100):

hook_strength — First 1-2 sentences. 90+: Pattern interrupt with specific data. 70-89: Strong curiosity gap. 50-69: Clear but generic. <50: Weak/no hook.
credibility — Does it PROVE claims? 90+: Specific data/results. 50-69: Claims without proof. <30: Scam signals. If scam detected → cap at 35.
emotional_pull — Visceral feeling? 90+: Personal trauma with detail. 70-89: Relatable pain. 50-69: Generic emotional language.
clarity — Can this audience understand instantly? 90+: Crystal clear. 50-69: Requires effort.
cta_strength — Action request quality. 90+: Specific, low-friction, benefit-driven. 70-89: Clear but generic. No CTA → max 30.
audience_match — Speaks THIS specific audience's language? Generic = max 50. Market-specific = 75+.
platform_fit — Native to {platform.upper()}? Right length, tone, format?

overall — Weighted: hook(25%) + credibility(20%) + emotional(20%) + cta(15%) + clarity(10%) + audience(5%) + platform(5%)

SCORING RULES:
1. Scores MUST reflect the reasoning — no generic 70s across the board
2. Diversity required: scores should span at least 30 points
3. Be HARDER on weak content. Most posts score 35-65. Only exceptional posts hit 80+.
4. Generic copy → cap overall at 55
5. No proof elements → credibility max 55

OUTPUT STRICT JSON (no markdown, no preamble):
{{
    "reasoning": {{
        "line_by_line": "sentence-by-sentence analysis",
        "hook_verdict": "Why the hook earns/loses its score",
        "credibility_verdict": "Specific proof elements found or missing",
        "audience_verdict": "How well it matches the audience profile",
        "biggest_weakness": "The single change that would most improve this post"
    }},
    "scores": {{
        "overall": 0, "hook_strength": 0, "clarity": 0, "credibility": 0,
        "emotional_pull": 0, "cta_strength": 0, "audience_match": 0, "platform_fit": 0
    }},
    "critical_weaknesses": [
        {{"issue": "...", "severity": "High|Medium|Low", "precise_fix": "exact rewrite suggestion"}}
    ],
    "what_to_change_right_now": "Single most impactful change with specific rewrite."
}}"""


def _build_critic_prompt(content: str, first_pass: Dict[str, Any], fp: ContentFingerprint, audience_block: str) -> str:
    """Second-pass critic that challenges inflated scores."""
    scores = first_pass.get("scores", {})

    flags = []
    if scores.get("credibility", 0) > 65 and not fp.has_specific_numbers and not fp.has_social_proof:
        flags.append(f"credibility={scores['credibility']} but NO specific numbers or social proof")
    if scores.get("hook_strength", 0) > 75 and not fp.has_trauma_pattern and not fp.has_specific_numbers:
        flags.append(f"hook_strength={scores['hook_strength']} but no trauma or specific number")
    if scores.get("emotional_pull", 0) > 70 and not fp.has_trauma_pattern:
        flags.append(f"emotional_pull={scores['emotional_pull']} but no trauma pattern detected")
    if scores.get("audience_match", 0) > 70 and not any(
        kw in content.lower() for kw in ["nigeria", "naira", "₦", "lagos", "abuja", "ghana", "accra", "uk", "london", "£"]
    ):
        flags.append(f"audience_match={scores['audience_match']} but no market-specific language")
    if max(scores.values() or [0]) - min(scores.values() or [0]) < 20:
        flags.append(f"Score spread only {max(scores.values() or [0]) - min(scores.values() or [0])} points — suspiciously uniform")

    flags_text = "\n".join(f"  ⚠️ {f}" for f in flags) if flags else "  ✅ No obvious inflation flags"

    reasoning = first_pass.get("reasoning", {})

    return f"""You are CONTENT CRITIC — a strict second reviewer who challenges over-generous scoring.

ORIGINAL SCORES: {json.dumps(scores, indent=2)}
ORIGINAL REASONING: {json.dumps(reasoning)[:600]}

INFLATION FLAGS:
{flags_text}

POST CONTENT:
{content}

FINGERPRINT FACTS:
- Has specific numbers: {fp.has_specific_numbers}
- Has social proof: {fp.has_social_proof}
- Has CTA: {fp.has_cta}
- Has trauma pattern: {fp.has_trauma_pattern}
- Has scam pattern: {fp.has_scam_pattern}
- Word count: {fp.word_count}

{audience_block}

CRITIC RULES:
1. You may LOWER or RAISE scores — accuracy matters
2. Claim without proof → credibility max 60
3. Hook without specific number/loss/pattern interrupt → max 72
4. audience_match above 70 requires market-specific language
5. If spread < 20 points, widen it
6. If a score is correct, leave it unchanged

OUTPUT STRICT JSON:
{{
    "critic_notes": "2-3 sentences explaining changes",
    "scores": {{
        "overall": 0, "hook_strength": 0, "clarity": 0, "credibility": 0,
        "emotional_pull": 0, "cta_strength": 0, "audience_match": 0, "platform_fit": 0
    }},
    "adjustments_made": [
        {{"dimension": "...", "from": 0, "to": 0, "reason": "..."}}
    ]
}}"""


# ══════════════════════════════════════════════════════════════════════════
# PUBLIC API
# ══════════════════════════════════════════════════════════════════════════

def score_post(
    content: str,
    platform: str = "linkedin",
    audience_country: str = "nigeria",
    audience_age: str = "25-34",
    audience_income: str = "middle",
    audience_occupation: str = "trader",
) -> Dict[str, Any]:
    """
    Score a social media post using two-pass Adlytics-style analysis.

    Returns:
        {
            "scores": {"overall": int, "hook_strength": int, ...},
            "passed": bool,          # overall >= SCORE_THRESHOLD
            "critical_weaknesses": [...],
            "what_to_change_right_now": str,
            "reasoning": {...},
            "fingerprint": {...},
        }
    """
    if not content or not content.strip():
        return {
            "scores": {"overall": 0},
            "passed": False,
            "critical_weaknesses": [{"issue": "Empty content", "severity": "High", "precise_fix": "Provide content"}],
            "what_to_change_right_now": "Content is empty.",
            "reasoning": {},
            "fingerprint": {},
        }

    fp = fingerprint_content(content)
    audience_block = build_audience_context(
        country=audience_country,
        age=audience_age,
        income=audience_income,
        occupation=audience_occupation,
        platform=platform,
    )

    logger.info(f"Scoring post [{fp.content_hash}] | {fp.word_count} words | platform={platform}")

    # ── Stage 1: Chain-of-thought scoring ──
    try:
        scoring_prompt = _build_scoring_prompt(content, fp, audience_block, platform)
        first_pass = _claude_json(
            system="You are a rigorous content quality evaluator. Return only valid JSON.",
            user=scoring_prompt,
            max_tokens=4000,
        )
        first_scores = first_pass.get("scores", {})
        logger.info(f"Stage 1 scores [{fp.content_hash}]: overall={first_scores.get('overall')}")
    except Exception as e:
        logger.error(f"Stage 1 failed [{fp.content_hash}]: {e} — using fallback")
        first_scores = _fallback_scores(fp)
        first_pass = {"scores": first_scores, "reasoning": {}, "critical_weaknesses": [], "what_to_change_right_now": ""}

    # Validate & fallback if all zeros
    is_valid, msg = validate_scores(first_scores, fp)
    if not is_valid:
        logger.warning(f"Score validation: {msg}")
        if all(v == 0 for k, v in first_scores.items() if k != "overall"):
            first_scores = _fallback_scores(fp)
            first_pass["scores"] = first_scores

    # ── Stage 2: Critic pass ──
    try:
        critic_prompt = _build_critic_prompt(content, first_pass, fp, audience_block)
        critic_result = _claude_json(
            system="You are a strict scoring critic. Return only valid JSON.",
            user=critic_prompt,
            max_tokens=1500,
        )
        critic_scores = critic_result.get("scores", {})
        adjustments = critic_result.get("adjustments_made", [])

        # Merge: big diff trusts critic, small diff averages, tiny keeps original
        final_scores = {}
        for dim in first_scores:
            if dim == "overall":
                continue
            orig = first_scores.get(dim, 50)
            crit = critic_scores.get(dim, orig)
            diff = abs(crit - orig)
            if diff > 15:
                final_scores[dim] = crit
            elif diff > 5:
                final_scores[dim] = round((orig + crit) / 2)
            else:
                final_scores[dim] = orig

        if adjustments:
            logger.info(f"Critic adjusted {len(adjustments)} dimension(s)")

    except Exception as e:
        logger.warning(f"Critic pass failed [{fp.content_hash}]: {e} — using Stage 1")
        final_scores = {k: v for k, v in first_scores.items() if k != "overall"}

    # Recompute weighted overall
    final_scores["overall"] = _recalc_overall(final_scores)
    passed = final_scores["overall"] >= SCORE_THRESHOLD

    logger.info(
        f"Final score [{fp.content_hash}]: {final_scores['overall']}/100 "
        f"({'PASS' if passed else 'FAIL — will rewrite'})"
    )

    return {
        "scores": final_scores,
        "passed": passed,
        "critical_weaknesses": first_pass.get("critical_weaknesses", []),
        "what_to_change_right_now": first_pass.get("what_to_change_right_now", ""),
        "reasoning": first_pass.get("reasoning", {}),
        "fingerprint": asdict(fp),
    }
