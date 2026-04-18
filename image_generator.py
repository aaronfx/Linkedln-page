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
    """Enhance the image prompt for photorealistic editorial photography."""
    style_guide = IMAGE_SETTINGS["default_theme"]

    pillar_styles = {
        "Personal Story & Behind-the-Scenes": (
            "Photorealistic. Warm, natural lighting like golden hour. "
            "Real African professional in a modern office, co-working space, or classroom. "
            "Candid, documentary-style photography. Shot on Canon EOS R5, 85mm f/1.4 lens. "
            "Shallow depth of field. Authentic and human."
        ),
        "Forex Education": (
            "Photorealistic. Close-up or medium shot of a real person studying trading screens. "
            "Multiple monitors showing candlestick charts. Focused, concentrated expression. "
            "Modern desk setup. Dramatic but natural lighting from screen glow and desk lamp. "
            "Shot on Sony A7IV, 35mm lens. Professional workspace feel."
        ),
        "AI in Trading": (
            "Photorealistic. Modern tech workspace with clean minimalist design. "
            "Laptop or dual monitors with data visualizations. African professional interacting with technology. "
            "Cool blue ambient lighting mixed with warm accents. "
            "Shot on Fuji X-T5, cinematic color grading. Tech-forward but human."
        ),
        "African Markets & Financial Literacy": (
            "Photorealistic. Vibrant African city scene — Lagos, Nairobi, or Accra skyline. "
            "Young African professionals using smartphones or laptops in modern settings. "
            "Natural daylight, bustling but professional energy. "
            "Street-level or rooftop perspective. Documentary photography style."
        ),
        "Community & Interactive": (
            "Photorealistic. Group of diverse African professionals in a collaborative setting. "
            "Workshop, seminar, or co-working space. Animated discussion, natural body language. "
            "Overhead fluorescent + window light mix. Candid group photography. "
            "Wide angle, environmental portrait style."
        ),
        "Industry Commentary": (
            "Photorealistic. Financial district or trading floor atmosphere. "
            "Large screens showing market data, professional environment. "
            "Serious, analytical mood. Cool color palette with sharp details. "
            "Shot from low angle for authority feel. News/editorial photography style."
        ),
    }

    pillar_style = pillar_styles.get(pillar, "Photorealistic editorial photography of a professional setting.")

    enhanced = (
        f"{base_prompt}. "
        f"Photography style: {pillar_style} "
        f"{style_guide} "
        f"CRITICAL: This must look like a REAL PHOTOGRAPH taken by a professional photographer. "
        f"Absolutely NO text, words, letters, numbers, logos, or watermarks anywhere in the image. "
        f"No artificial-looking elements. No clip art. No illustrations. Pure photorealism."
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
