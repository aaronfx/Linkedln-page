"""
Image Generator — Powered by OpenAI DALL-E
============================================
Generates professional LinkedIn post images using DALL-E 3.
"""

import logging
import requests
from datetime import datetime
from pathlib import Path
from openai import OpenAI
from config import OPENAI_API_KEY, IMAGE_SETTINGS, IMAGES_DIR, PROFILE

logger = logging.getLogger("image_generator")


def _get_openai_client():
    """Create OpenAI client on demand (not at import time) so env vars are fresh."""
    from config import OPENAI_API_KEY as key
    return OpenAI(api_key=key)


def generate_post_image(
    image_prompt: str,
    pillar: str = "",
    filename: str = None
) -> str:
    """
    Generate a LinkedIn post image using DALL-E 3.

    Args:
        image_prompt: Description of the image to generate
        pillar: Content pillar (for filename organization)
        filename: Optional custom filename

    Returns:
        Path to the saved image file
    """
    # Enhance the prompt with LinkedIn-specific styling
    enhanced_prompt = _enhance_prompt(image_prompt, pillar)

    logger.info(f"Generating image with prompt: {enhanced_prompt[:100]}...")

    try:
        response = _get_openai_client().images.generate(
            model=IMAGE_SETTINGS["model"],
            prompt=enhanced_prompt,
            size=IMAGE_SETTINGS["size"],
            quality=IMAGE_SETTINGS["quality"],
            style=IMAGE_SETTINGS["style"],
            n=1,
        )

        image_url = response.data[0].url
        revised_prompt = response.data[0].revised_prompt

        # Download and save the image
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            safe_pillar = pillar.replace(" ", "_").replace("&", "and")[:30]
            filename = f"post_{safe_pillar}_{timestamp}.png"

        image_path = IMAGES_DIR / filename
        _download_image(image_url, image_path)

        logger.info(f"Image saved to: {image_path}")
        logger.info(f"DALL-E revised prompt: {revised_prompt[:100]}...")

        return str(image_path)

    except Exception as e:
        logger.error(f"Image generation failed: {e}")
        # Return a fallback — generate a simple branded placeholder
        return _generate_fallback_image(pillar, filename)


def generate_batch_images(posts: list) -> list:
    """
    Generate images for a batch of posts.

    Args:
        posts: List of post dicts (each must have 'image_prompt' and 'pillar')

    Returns:
        List of image file paths
    """
    image_paths = []
    for i, post in enumerate(posts):
        prompt = post.get("image_prompt", f"Professional image about {post.get('pillar', 'forex trading')}")
        pillar = post.get("pillar", "general")
        path = generate_post_image(prompt, pillar)
        image_paths.append(path)
        logger.info(f"Generated image {i+1}/{len(posts)}: {path}")

    return image_paths


def _enhance_prompt(base_prompt: str, pillar: str) -> str:
    """Enhance the image prompt with consistent branding and LinkedIn optimization."""
    style_guide = IMAGE_SETTINGS["default_theme"]

    pillar_styles = {
        "Personal Story & Behind-the-Scenes": (
            "Warm, personal atmosphere. African professional in a modern office or "
            "training environment. Inspirational and authentic feel."
        ),
        "Forex Education": (
            "Clean trading charts, candlestick patterns, or financial data visualization. "
            "Educational and informative mood. Modern, sleek design."
        ),
        "AI in Trading": (
            "Futuristic technology meets finance. AI neural networks, data streams, "
            "or human-AI collaboration imagery. Blue and gold tones."
        ),
        "African Markets & Financial Literacy": (
            "African cityscape, mobile phones showing trading apps, or diverse African "
            "professionals. Empowerment and opportunity themes."
        ),
        "Community & Interactive": (
            "People connecting, collaboration, group discussion. Diverse faces, "
            "community feel. Vibrant and engaging."
        ),
        "Industry Commentary": (
            "Global financial markets, world map with trading connections, "
            "or market analysis scenes. Authoritative and insightful."
        ),
    }

    pillar_style = pillar_styles.get(pillar, "Professional financial theme.")

    enhanced = (
        f"{base_prompt}. "
        f"Style: {style_guide} "
        f"Mood: {pillar_style} "
        f"IMPORTANT: No text, words, letters, numbers, or watermarks in the image. "
        f"Clean, high-resolution, suitable for a professional LinkedIn post. "
        f"16:9 aspect ratio composition preferred."
    )

    return enhanced


def _download_image(url: str, save_path: Path):
    """Download an image from URL and save locally."""
    response = requests.get(url, timeout=60)
    response.raise_for_status()
    with open(save_path, "wb") as f:
        f.write(response.content)


def _generate_fallback_image(pillar: str, filename: str = None) -> str:
    """Generate a simple fallback if DALL-E fails."""
    logger.warning("Using fallback image generation")
    # In production, you could use a pre-made template system here
    # For now, return empty string to indicate no image available
    return ""
