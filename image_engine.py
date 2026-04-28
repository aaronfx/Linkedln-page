"""
Image Engine — Nano Banana 2 via ApiPass (Gemini Flash Image) Integration
=========================================================================
Generates on-brand social media visuals from text prompts.
Images are stored on the Railway persistent volume / local images dir
and served via the Flask app's /images/<filename> route.

ApiPass async job flow:
  1. POST /api/v1/jobs/createTask  → taskId
  2. GET  /api/v1/jobs/recordInfo?taskId=<id>  → poll until state=="success"
  3. Parse resultJson → resultUrls[0]  → download image bytes

Supports:
  - generate_image(prompt, platform)  — full AI image from concept
  - generate_image_for_queue_entry(entry) — auto-generate for a queue item
"""

import os
import json
import uuid
import time
import logging
import requests
from pathlib import Path
from datetime import datetime, timezone

logger = logging.getLogger("image_engine")

# ── ApiPass / Nano Banana 2 ──────────────────────────────────────────────
# Set NANO_BANANA_API_KEY in Railway env to the ApiPass API key.

APIPASS_CREATE_URL = "https://api.apipass.dev/api/v1/jobs/createTask"
APIPASS_POLL_URL   = "https://api.apipass.dev/api/v1/jobs/recordInfo"
APIPASS_MODEL      = "google/nano-banana-2"

NANO_BANANA_API_KEY = os.getenv("NANO_BANANA_API_KEY", "")
APP_BASE_URL = os.getenv(
    "APP_BASE_URL", "https://linkedln-page-production.up.railway.app"
).rstrip("/")

# ── Brand visual identity ──────────────────────────────────────────────
BRAND_VISUAL = {
    "name": "Gopipways",
    "tagline": "Africa's leading forex education platform",
    "colors": "deep navy blue (#1a237e), gold (#ffd700), crisp white",
    "feeling": "trustworthy, empowering, aspirational, professional",
    "style": "modern, clean, African-inspired, data-forward",
    "avoid": "cartoon style, clutter, stock-photo cliches, generic office photos",
}

# ── Platform image specs ───────────────────────────────────────────────
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
    """
    Generate an image using Nano Banana 2 via ApiPass.

    Args:
        prompt:      The image concept / DALL-E style description.
        platform:    Target platform (instagram / facebook / linkedin / threads).
        style_notes: Any extra style instructions.
        images_dir:  Where to save the image file.

    Returns:
        {
          "image_url":   "https://app.../images/ig_abc123.jpg",
          "local_path":  "/path/to/image.jpg",
          "filename":    "ig_abc123.jpg",
          "prompt_used": "...",
          "platform":    "instagram",
          "generated_at": "2026-04-25T...",
        }
    """
    if images_dir is None:
        from config import IMAGES_DIR
        images_dir = Path(IMAGES_DIR)
    images_dir.mkdir(parents=True, exist_ok=True)

    full_prompt = _build_prompt(prompt, platform, style_notes)
    logger.info(f"Generating image [{platform}] prompt: {prompt[:80]}...")

    if not NANO_BANANA_API_KEY:
        raise ValueError(
            "No image generation API key set. "
            "Set NANO_BANANA_API_KEY (ApiPass key) in Railway environment variables."
        )
    result = _call_nano_banana(full_prompt)

    # Save image to disk
    ext = result.get("ext", "jpg")
    prefix = platform[:2]  # "ig", "fb", "li", "th"
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
    """
    Auto-generate and attach an image to a queue entry that has image_prompt set.
    Modifies and returns the entry with image_url filled in.

    Raises ValueError if entry has no image_prompt.
    """
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


# ── Private helpers ────────────────────────────────────────────────────────────────

def _build_prompt(concept: str, platform: str, style_notes: str = "") -> str:
    """Build a brand-aware, platform-optimised image generation prompt."""
    brand = BRAND_VISUAL
    spec = PLATFORM_IMAGE_SPECS.get(platform, PLATFORM_IMAGE_SPECS["instagram"])

    parts = [
        f"Create a {spec['ratio']} social media image for {brand['name']} — {brand['tagline']}.",
        f"",
        f"CONCEPT: {concept}",
        f"",
        f"BRAND IDENTITY:",
        f"- Colors: {brand['colors']}",
        f"- Feeling: {brand['feeling']}",
        f"- Visual style: {brand['style']}",
        f"- Avoid: {brand['avoid']}",
        f"",
        f"PLATFORM ({platform.upper()}):",
        f"- Format: {spec['ratio']}",
        f"- Style: {spec['style']}",
        f"- Mood: {spec['mood']}",
    ]

    if style_notes:
        parts += [f"", f"ADDITIONAL DIRECTION: {style_notes}"]

    parts += [
        f"",
        f"OUTPUT: High-quality, photorealistic or stylised as appropriate. "
        f"No watermarks. Ready to post directly.",
    ]

    return "\n".join(parts)


def _call_nano_banana(prompt: str) -> dict:
    """
    Call Nano Banana 2 via ApiPass async jobs API.

    Flow:
      1. POST createTask -> taskId
      2. Poll recordInfo every 5 s until state == "success" (max 3 min)
      3. Parse resultJson -> download image from resultUrls[0]
    """
    headers = {
        "Authorization": f"Bearer {NANO_BANANA_API_KEY}",
        "Content-Type": "application/json",
    }

    # Step 1 — submit task
    payload = {
        "model": APIPASS_MODEL,
        "input": {
            "prompt": prompt,
            "aspect_ratio": "1:1",
            "resolution": "1K",
            "output_format": "jpg",
        },
    }
    resp = requests.post(APIPASS_CREATE_URL, json=payload, headers=headers, timeout=30)
    resp.raise_for_status()
    create_data = resp.json()

    if create_data.get("code") != 200:
        raise ValueError(f"ApiPass createTask failed: {create_data}")

    task_id = create_data["data"]["taskId"]
    logger.info(f"ApiPass task created: {task_id}")

    # Step 2 — poll until complete (max 180 s)
    poll_headers = {"Authorization": f"Bearer {NANO_BANANA_API_KEY}"}
    deadline = time.time() + 180
    interval = 5

    while time.time() < deadline:
        time.sleep(interval)
        poll_resp = requests.get(
            APIPASS_POLL_URL,
            params={"taskId": task_id},
            headers=poll_headers,
            timeout=30,
        )
        poll_resp.raise_for_status()
        poll_data = poll_resp.json()

        if poll_data.get("code") != 200:
            raise ValueError(f"ApiPass recordInfo error: {poll_data}")

        task = poll_data["data"]
        state = task.get("state", "")
        logger.info(f"ApiPass task {task_id} state: {state}")

        if state == "success":
            result_json = json.loads(task["resultJson"])
            image_url = result_json["resultUrls"][0]
            img_resp = requests.get(image_url, timeout=60)
            img_resp.raise_for_status()
            ext = "png" if image_url.lower().endswith(".png") else "jpg"
            return {"image_bytes": img_resp.content, "ext": ext}

        if state in ("failed", "error"):
            raise ValueError(
                f"ApiPass task {task_id} failed: "
                f"{task.get('failMsg', 'no message')} (code: {task.get('failCode', '?')})"
            )

        # Still waiting/processing — back off slightly after first few polls
        if interval < 10:
            interval = 10

    raise TimeoutError(f"ApiPass task {task_id} timed out after 180 s")
