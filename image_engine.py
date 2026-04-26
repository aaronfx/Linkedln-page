"""
Image Engine — Nano Banana (Gemini Flash Image) Integration
===========================================================
Generates on-brand social media visuals from text prompts.
Images are stored on the Railway persistent volume / local images dir
and served via the Flask app's /images/<filename> route.

Supports:
  - generate_image(prompt, platform)  — full AI image from concept
  - generate_image_for_queue_entry(entry) — auto-generate for a queue item
"""

import os
import json
import base64
import uuid
import logging
import requests
from pathlib import Path
from datetime import datetime, timezone

logger = logging.getLogger("image_engine")

NANO_BANANA_URL = "https://api.nanobananaapi.ai/v1/images/generate"
GEMINI_IMAGE_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "gemini-2.0-flash-preview-image-generation:generateContent"
)

NANO_BANANA_API_KEY = os.getenv("NANO_BANANA_API_KEY", "")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
APP_BASE_URL = os.getenv(
    "APP_BASE_URL", "https://linkedln-page-production.up.railway.app"
).rstrip("/")

BRAND_VISUAL = {
    "name": "Gopipways",
    "tagline": "Africa's leading forex education platform",
    "colors": "deep navy blue (#1a237e), gold (#ffd700), crisp white",
    "feeling": "trustworthy, empowering, aspirational, professional",
    "style": "modern, clean, African-inspired, data-forward",
    "avoid": "cartoon style, clutter, stock-photo cliches, generic office photos",
}

PLATFORM_IMAGE_SPECS = {
    "instagram": {
        "ratio": "1:1 square (1080x1080) or 4:5 portrait",
        "style": "Bold, scroll-stopping. Strong focal point. Minimal text in frame.",
        "mood": "high-energy but professional",
    },
    "facebook": {
        "ratio": "1.91:1 landscape (1200x630) or square",
        "style": "Clear, professional. Approachable. Works as a feed post.",
        "mood": "community-focused, warm",
    },
    "linkedin": {
        "ratio": "1.91:1 landscape (1200x627)",
        "style": "Corporate-clean. Data and charts welcome. Credibility signals.",
        "mood": "authoritative, analytical",
    },
    "threads": {
        "ratio": "1:1 square or portrait",
        "style": "Conversational, slightly informal. Text-friendly composition.",
        "mood": "authentic, relatable",
    },
}


def generate_image(
    prompt: str,
    platform: str = "instagram",
    style_notes: str = "",
    images_dir: Path = None,
) -> dict:
    if images_dir is None:
        from config import IMAGES_DIR
        images_dir = Path(IMAGES_DIR)
    images_dir.mkdir(parents=True, exist_ok=True)

    full_prompt = _build_prompt(prompt, platform, style_notes)
    logger.info(f"Generating image [{platform}] prompt: {prompt[:80]}...")

    if NANO_BANANA_API_KEY:
        result = _call_nano_banana(full_prompt)
    elif GOOGLE_API_KEY:
        result = _call_gemini(full_prompt)
    else:
        raise ValueError(
            "No image generation API key set. "
            "Set NANO_BANANA_API_KEY or GOOGLE_API_KEY in Railway environment variables."
        )

    ext = result.get("ext", "jpg")
    prefix = platform[:2]
    filename = f"{prefix}_{uuid.uuid4().hex[:12]}.{ext}"
    local_path = images_dir / filename

    image_bytes = result["image_bytes"]
    with open(local_path, "wb") as f:
        f.write(image_bytes)

    public_url = f"{APP_BASE_URL}/images/{filename}"
    logger.info(f"Image saved: {filename} ({len(image_bytes)} bytes) -> {public_url}")

    return {
        "image_url": public_url,
        "local_path": str(local_path),
        "filename": filename,
        "prompt_used": full_prompt,
        "platform": platform,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def generate_image_for_queue_entry(entry: dict, images_dir: Path = None) -> dict:
    image_prompt = entry.get("image_prompt", "").strip()
    if not image_prompt:
        raise ValueError(f"Queue entry has no image_prompt: {entry.get('id', '?')}")

    platform = entry.get("platform", "instagram")
    visual_direction = entry.get("visual_direction", "")

    result = generate_image(
        prompt=image_prompt,
        platform=platform,
        style_notes=visual_direction,
        images_dir=images_dir,
    )

    entry["image_url"] = result["image_url"]
    entry["image_filename"] = result["filename"]
    entry["image_generated_at"] = result["generated_at"]
    return entry


def _build_prompt(concept: str, platform: str, style_notes: str = "") -> str:
    brand = BRAND_VISUAL
    spec = PLATFORM_IMAGE_SPECS.get(platform, PLATFORM_IMAGE_SPECS["instagram"])

    parts = [
        f"Create a {spec['ratio']} social media image for {brand['name']} — {brand['tagline']}.",
        "",
        f"CONCEPT: {concept}",
        "",
        "BRAND IDENTITY:",
        f"- Colors: {brand['colors']}",
        f"- Feeling: {brand['feeling']}",
        f"- Visual style: {brand['style']}",
        f"- Avoid: {brand['avoid']}",
        "",
        f"PLATFORM ({platform.upper()}):",
        f"- Format: {spec['ratio']}",
        f"- Style: {spec['style']}",
        f"- Mood: {spec['mood']}",
    ]

    if style_notes:
        parts += ["", f"ADDITIONAL DIRECTION: {style_notes}"]

    parts += [
        "",
        "OUTPUT: High-quality, photorealistic or stylised as appropriate. "
        "No watermarks. Ready to post directly.",
    ]

    return "\n".join(parts)


def _call_nano_banana(prompt: str) -> dict:
    headers = {
        "Authorization": f"Bearer {NANO_BANANA_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {"prompt": prompt, "model": "nano-banana-2", "n": 1}
    resp = requests.post(NANO_BANANA_URL, json=payload, headers=headers, timeout=120)
    resp.raise_for_status()
    data = resp.json()

    if "url" in data:
        img_resp = requests.get(data["url"], timeout=60)
        img_resp.raise_for_status()
        return {"image_bytes": img_resp.content, "ext": "jpg"}
    elif "b64_json" in data:
        return {"image_bytes": base64.b64decode(data["b64_json"]), "ext": "jpg"}
    elif "data" in data and isinstance(data["data"], list):
        item = data["data"][0]
        if "url" in item:
            img_resp = requests.get(item["url"], timeout=60)
            img_resp.raise_for_status()
            return {"image_bytes": img_resp.content, "ext": "jpg"}
        elif "b64_json" in item:
            return {"image_bytes": base64.b64decode(item["b64_json"]), "ext": "jpg"}

    raise ValueError(f"Unexpected Nano Banana response shape: {list(data.keys())}")


def _call_gemini(prompt: str) -> dict:
    params = {"key": GOOGLE_API_KEY}
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"responseModalities": ["image", "text"]},
    }
    resp = requests.post(GEMINI_IMAGE_URL, json=payload, params=params, timeout=120)
    resp.raise_for_status()
    data = resp.json()

    for part in (
        data.get("candidates", [{}])[0]
        .get("content", {})
        .get("parts", [])
    ):
        if "inlineData" in part:
            mime = part["inlineData"].get("mimeType", "image/jpeg")
            ext = "png" if "png" in mime else "jpg"
            return {
                "image_bytes": base64.b64decode(part["inlineData"]["data"]),
                "ext": ext,
            }

    raise ValueError(
        f"No image in Gemini response. Keys: "
        f"{list(data.get('candidates', [{}])[0].get('content', {}).keys())}"
    )
