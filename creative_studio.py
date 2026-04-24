"""
Creative Design Studio Module for Gopipways Social Hub

Handles all visual content creation including image generation via DALL-E,
brand overlays using PIL, and batch processing of visual content.
"""

import logging
import os
from typing import Dict, List, Tuple, Optional, Any
from datetime import datetime

# Optional PIL import with graceful fallback
try:
    from PIL import Image, ImageDraw, ImageFont
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

# Attempt to import config and image_generator
try:
    from config import OPENAI_API_KEY, IMAGE_SETTINGS, IMAGES_DIR
except ImportError:
    # Fallback defaults if config not available
    OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
    IMAGE_SETTINGS = {}
    IMAGES_DIR = "/tmp/images"

try:
    from image_generator import _download_image
except ImportError:
    _download_image = None

# Configure logger
logger = logging.getLogger("creative_studio")

# Platform sizing presets
PLATFORM_SIZES = {
    "linkedin": {"landscape": (1200, 627), "square": (1080, 1080)},
    "whatsapp_status": {"story": (1080, 1920), "square": (1080, 1080)},
    "instagram": {"portrait": (1080, 1350), "square": (1080, 1080), "story": (1080, 1920)},
    "x": {"landscape": (1024, 512), "square": (512, 512)},
    "threads": {"square": (1080, 1080)},
    "facebook": {"landscape": (1200, 630), "square": (1080, 1080)}
}

# Brand colors
BRAND_COLORS = {
    "company_purple": "#7C3AED",
    "linkedin_blue": "#0A66C2",
    "white": "#FFFFFF",
    "black": "#000000"
}

# Pillar-specific style enhancements
PILLAR_STYLES = {
    "Personal Story": "warm golden hour photography, African professional, candid documentary style, authentic candid moment",
    "Forex Education": "person intently studying trading screens, multiple monitors visible, focused professional, analytical atmosphere",
    "AI in Trading": "modern tech workspace aesthetic, cool blue ambient lighting, cutting-edge office environment, tech innovation",
    "African Markets": "vibrant African city backdrop, young professionals with smartphones, dynamic urban setting, African energy",
    "Industry Commentary": "financial district skyline, large financial screens displaying data, serious analytical mood, professional traders",
    "EDUCATE": "classroom or learning environment, clean whiteboard, diverse African students, collaborative learning atmosphere",
    "PROVE": "results and data visualization, confident trader displaying profits, screen showing performance metrics, success visual",
    "INSPIRE": "sunrise or golden hour success imagery, African professionals celebrating achievement, motivational moment, triumph",
    "ENGAGE": "group discussion or community setting, collaborative workshop atmosphere, diverse professionals engaging, interactive moment",
    "CONVERT": "product showcase setting, smartphone displaying app interface, professional product demo, conversion-focused visual"
}


def ensure_images_dir():
    """Ensure the images directory exists."""
    try:
        os.makedirs(IMAGES_DIR, exist_ok=True)
        logger.debug(f"Images directory ensured: {IMAGES_DIR}")
    except Exception as e:
        logger.warning(f"Could not create images directory: {e}")


def _enhance_prompt(base_prompt: str, pillar: str = "", platform: str = "linkedin") -> str:
    """
    Enhance a base prompt with pillar-specific styling and technical details.

    Args:
        base_prompt: The original prompt text
        pillar: The content pillar for style enhancement
        platform: The target platform

    Returns:
        Enhanced prompt with photography style and technical details
    """
    # Get pillar style if provided
    pillar_style = PILLAR_STYLES.get(pillar, "")

    # Build enhancement
    enhancement = (
        f"{base_prompt} "
        f"{pillar_style} "
        "Photorealistic editorial photography. No text, words, logos, or watermarks. "
        "Professional 50mm lens, shallow depth of field, perfect studio lighting, "
        "rich color grading, high contrast, 8K resolution, cinematic quality."
    )

    return enhancement.strip()


def generate_image(
    prompt: str,
    platform: str = "linkedin",
    aspect: str = "landscape",
    pillar: str = ""
) -> Dict[str, Any]:
    """
    Generate an image using DALL-E 3 API.

    Args:
        prompt: The image generation prompt
        platform: Target platform (determines sizing)
        aspect: Aspect ratio type (landscape, square, portrait, story)
        pillar: Content pillar for style enhancement

    Returns:
        Dictionary with keys: path, prompt_used, platform, size
        Returns empty dict on failure
    """
    if not OPENAI_API_KEY:
        logger.error("OPENAI_API_KEY not configured")
        return {}

    try:
        ensure_images_dir()

        # Get target size
        sizes = PLATFORM_SIZES.get(platform, {})
        size = sizes.get(aspect, (1080, 1080))

        # Enhance prompt with pillar styling
        enhanced_prompt = _enhance_prompt(prompt, pillar, platform)
        logger.info(f"Generating image for {platform} ({aspect}): {enhanced_prompt[:100]}...")

        # Import OpenAI here to avoid hard dependency
        try:
            from openai import OpenAI
        except ImportError:
            logger.error("OpenAI library not installed. Install with: pip install openai")
            return {}

        client = OpenAI(api_key=OPENAI_API_KEY)

        # Generate image with DALL-E 3
        response = client.images.generate(
            model="dall-e-3",
            prompt=enhanced_prompt,
            size=f"{size[0]}x{size[1]}",
            quality="hd",
            n=1
        )

        image_url = response.data[0].url

        # Download and save image
        if _download_image:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{platform}_{aspect}_{timestamp}.png"
            filepath = os.path.join(IMAGES_DIR, filename)

            image_data = _download_image(image_url)
            with open(filepath, "wb") as f:
                f.write(image_data)

            logger.info(f"Image saved to {filepath}")

            return {
                "path": filepath,
                "prompt_used": enhanced_prompt,
                "platform": platform,
                "size": size
            }
        else:
            logger.warning("image_generator._download_image not available, cannot save image")
            return {}

    except Exception as e:
        logger.error(f"Error generating image: {e}", exc_info=True)
        return {}


def add_brand_overlay(
    image_path: str,
    text: str = "",
    logo_path: Optional[str] = None,
    position: str = "bottom",
    platform: str = "linkedin"
) -> str:
    """
    Add brand overlay with text and optional logo to an image using PIL.

    Args:
        image_path: Path to the base image
        text: Text to overlay
        logo_path: Optional path to logo image
        position: Position for overlay (top, bottom, center)
        platform: Target platform

    Returns:
        Path to the new image with overlay
        Returns empty string on failure or if PIL unavailable
    """
    if not HAS_PIL:
        logger.warning("PIL/Pillow not available, skipping brand overlay")
        return ""

    try:
        if not os.path.exists(image_path):
            logger.error(f"Image not found: {image_path}")
            return ""

        # Open image
        img = Image.open(image_path)
        width, height = img.size

        # Create overlay layer
        overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)

        # Determine color based on platform
        color = BRAND_COLORS["company_purple"]
        if "linkedin" in platform.lower():
            color = BRAND_COLORS["linkedin_blue"]

        # Convert hex to RGB with alpha
        rgb = tuple(int(color.lstrip("#")[i:i+2], 16) for i in (0, 2, 4))
        overlay_color = (*rgb, 180)  # Semi-transparent

        # Add gradient overlay at specified position
        overlay_height = int(height * 0.25)  # 25% of image height

        if position == "bottom":
            y_start = height - overlay_height
        elif position == "top":
            y_start = 0
        else:  # center
            y_start = (height - overlay_height) // 2

        # Draw semi-transparent rectangle
        for i in range(overlay_height):
            alpha = int(180 * (i / overlay_height))  # Gradient effect
            current_color = (*rgb, alpha)
            draw.rectangle(
                [(0, y_start + i), (width, y_start + i + 1)],
                fill=current_color
            )

        # Add text if provided
        if text:
            try:
                # Try to use a default font, fall back to default if not available
                font_size = int(height * 0.05)
                font = ImageFont.load_default()
            except Exception as e:
                logger.warning(f"Could not load font: {e}, using default")
                font = ImageFont.load_default()

            text_color = BRAND_COLORS["white"]
            text_rgb = tuple(int(text_color.lstrip("#")[i:i+2], 16) for i in (0, 2, 4))
            text_rgba = (*text_rgb, 255)

            # Calculate text position
            text_x = int(width * 0.05)
            text_y = y_start + int(overlay_height * 0.3)

            draw.text((text_x, text_y), text, fill=text_rgba, font=font)

        # Composite overlay onto original image
        img = img.convert("RGBA")
        img = Image.alpha_composite(img, overlay)
        img = img.convert("RGB")

        # Save result
        ensure_images_dir()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_filename = f"{platform}_overlay_{timestamp}.png"
        output_path = os.path.join(IMAGES_DIR, output_filename)

        img.save(output_path, "PNG", quality=95)
        logger.info(f"Brand overlay saved to {output_path}")

        return output_path

    except Exception as e:
        logger.error(f"Error adding brand overlay: {e}", exc_info=True)
        return ""


def process_visual_flags(posts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Process posts with [VISUAL FLAG] markers and generate images for them.

    Scans through posts list, identifies flagged posts, generates images,
    and updates the posts with image paths.

    Args:
        posts: List of post dictionaries

    Returns:
        Updated posts list with image_path filled in for flagged posts
    """
    if not posts:
        logger.debug("No posts to process")
        return posts

    updated_posts = []

    for post in posts:
        if not isinstance(post, dict):
            updated_posts.append(post)
            continue

        content = post.get("content", "")

        if "[VISUAL FLAG]" in content or "[visual_flag]" in content:
            logger.info(f"Processing visual flag in post: {content[:80]}...")

            # Extract platform and pillar info
            platform = post.get("platform", "linkedin")
            pillar = post.get("pillar", "")

            # Extract aspect ratio hint from content or use default
            aspect = "landscape"
            if platform == "instagram":
                aspect = "portrait"
            elif "story" in content.lower():
                aspect = "story"

            # Create enhanced prompt from post content
            # Remove the flag marker from prompt
            prompt = content.replace("[VISUAL FLAG]", "").replace("[visual_flag]", "").strip()

            if prompt:
                result = generate_image(prompt, platform=platform, aspect=aspect, pillar=pillar)

                if result and result.get("path"):
                    post["image_path"] = result["path"]
                    post["image_prompt"] = result.get("prompt_used", "")
                    logger.info(f"Image generated and added to post")
                else:
                    logger.warning(f"Failed to generate image for post")
                    post["image_path"] = ""
            else:
                logger.warning(f"No prompt text found after removing flag marker")
                post["image_path"] = ""

        updated_posts.append(post)

    logger.info(f"Processed {len([p for p in updated_posts if p.get('image_path')])} posts with images")
    return updated_posts


def generate_batch(
    posts: List[Dict[str, Any]],
    platform: str = "linkedin"
) -> List[str]:
    """
    Generate images for multiple posts.

    Args:
        posts: List of post dictionaries containing prompts
        platform: Target platform for all images

    Returns:
        List of image file paths
    """
    logger.info(f"Generating batch of {len(posts)} images for {platform}")

    image_paths = []

    for idx, post in enumerate(posts, 1):
        if not isinstance(post, dict):
            logger.warning(f"Post {idx} is not a dictionary, skipping")
            continue

        prompt = post.get("content") or post.get("prompt") or post.get("text", "")

        if not prompt:
            logger.warning(f"Post {idx} has no content/prompt, skipping")
            continue

        pillar = post.get("pillar", "")

        # Determine aspect ratio
        aspect = post.get("aspect", "landscape")

        logger.debug(f"Generating image {idx}/{len(posts)}")

        result = generate_image(prompt, platform=platform, aspect=aspect, pillar=pillar)

        if result and result.get("path"):
            image_paths.append(result["path"])
            post["image_path"] = result["path"]
        else:
            logger.warning(f"Failed to generate image for post {idx}")

    logger.info(f"Batch generation complete: {len(image_paths)} images created")
    return image_paths


def batch_add_overlay(
    image_paths: List[str],
    texts: Optional[List[str]] = None,
    platform: str = "linkedin"
) -> List[str]:
    """
    Add brand overlays to multiple images.

    Args:
        image_paths: List of image file paths
        texts: Optional list of overlay texts (one per image)
        platform: Target platform

    Returns:
        List of paths to overlayed images
    """
    if not HAS_PIL:
        logger.warning("PIL/Pillow not available, cannot add overlays")
        return image_paths

    logger.info(f"Adding overlays to {len(image_paths)} images for {platform}")

    overlayed_paths = []

    for idx, image_path in enumerate(image_paths):
        text = ""
        if texts and idx < len(texts):
            text = texts[idx]

        result = add_brand_overlay(image_path, text=text, platform=platform)

        if result:
            overlayed_paths.append(result)
        else:
            overlayed_paths.append(image_path)

    return overlayed_paths


# Initialization
if __name__ == "__main__":
    # Configure logging for testing
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    logger.info("Creative Studio module loaded")
    logger.info(f"PIL available: {HAS_PIL}")
    logger.info(f"Images directory: {IMAGES_DIR}")

    # Test platform sizes
    logger.debug(f"Available platforms: {list(PLATFORM_SIZES.keys())}")
    logger.debug(f"Pillar styles available: {list(PILLAR_STYLES.keys())}")
