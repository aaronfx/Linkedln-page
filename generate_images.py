#!/usr/bin/env python3
"""
Generate Images for Queued Posts
================================
Reads content_queue.json, generates DALL-E images for any posts
that have an image_prompt but no image_path, then saves back.

Usage:
  python generate_images.py
"""

import json
import logging
from pathlib import Path
from config import CONTENT_QUEUE_FILE, IMAGES_DIR
from image_generator import generate_post_image

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("generate_images")


def main():
    if not CONTENT_QUEUE_FILE.exists():
        print("No content queue found.")
        return

    with open(CONTENT_QUEUE_FILE) as f:
        queue = json.load(f)

    print(f"Found {len(queue)} posts in queue")

    updated = 0
    for i, post in enumerate(queue):
        prompt = post.get("image_prompt", "")
        existing_path = post.get("image_path", "")

        # Skip if already has an image
        if existing_path and Path(existing_path).exists():
            print(f"  [{i+1}/{len(queue)}] Already has image: {existing_path}")
            continue

        if not prompt:
            print(f"  [{i+1}/{len(queue)}] No image prompt — skipping")
            continue

        pillar = post.get("pillar", "general")
        print(f"  [{i+1}/{len(queue)}] Generating image for: {post.get('hook', '')[:60]}...")

        try:
            image_path = generate_post_image(
                image_prompt=prompt,
                pillar=pillar,
            )
            if image_path:
                post["image_path"] = image_path
                updated += 1
                print(f"    -> Saved: {image_path}")
            else:
                print(f"    -> No image returned (DALL-E may have failed)")
        except Exception as e:
            print(f"    -> ERROR: {e}")
            continue

    # Save updated queue
    with open(CONTENT_QUEUE_FILE, "w") as f:
        json.dump(queue, f, indent=2)

    print(f"\nDone! Generated {updated} images out of {len(queue)} posts.")


if __name__ == "__main__":
    main()
