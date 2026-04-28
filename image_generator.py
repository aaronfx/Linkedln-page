"""
image_generator.py — delegates all image generation to image_engine.py (ApiPass / Nano Banana 2)
================================================================================================
Kept as a compatibility shim so dashboard.py imports continue working unchanged.
The real generation logic lives in image_engine.py.
"""

import logging
from pathlib import Path

logger = logging.getLogger("image_generator")


def generate_post_image(image_prompt: str, pillar: str = "", platform: str = "instagram") -> str:
    """
    Generate an image for a post and return the local file path.

    Args:
        image_prompt: Description of the image to generate.
        pillar:       Content pillar (used to pick platform if not set).
        platform:     Target social platform.

    Returns:
        str: Absolute path to the saved image file.
    """
    from image_engine import generate_image

    # Map pillar to platform if caller didn't specify
    if not platform or platform == "instagram":
        pillar_lower = (pillar or "").lower()
        if "linkedin" in pillar_lower:
            platform = "linkedin"
        elif "facebook" in pillar_lower:
            platform = "facebook"
        elif "threads" in pillar_lower:
            platform = "threads"
        else:
            platform = "instagram"

    logger.info(f"generate_post_image: platform={platform} prompt={image_prompt[:60]}...")
    result = generate_image(prompt=image_prompt, platform=platform)
    return result["local_path"]


def generate_batch_images(posts: list) -> list:
    """
    Generate images for a list of posts. Returns list of local file paths.
    Each post dict should have 'image_prompt' and optionally 'platform'.
    """
    paths = []
    for i, post in enumerate(posts):
        prompt = post.get("image_prompt", "")
        if not prompt:
            paths.append(None)
            continue
        platform = post.get("platform", "instagram")
        try:
            path = generate_post_image(prompt, platform=platform)
            paths.append(path)
            logger.info(f"Batch image {i+1}/{len(posts)} done: {path}")
        except Exception as e:
            logger.error(f"Batch image {i+1} failed: {e}")
            paths.append(None)
    return paths
