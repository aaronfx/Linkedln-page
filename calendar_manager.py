"""
Calendar Manager - Content Calendar Management Module
======================================================
Manages monthly content calendars for the Gopipways Social Hub.
Calendars are stored as JSON files and generated using Claude AI.

FEATURES:
- Monthly calendar creation with Claude-powered content planning
- Content distribution across platforms and pillars
- Cross-platform coordination
- Calendar persistence and versioning
- Thread-safe file operations with FileLock
"""

import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Any
from filelock import FileLock
from anthropic import Anthropic

from config import (
    DATA_DIR,
    ANTHROPIC_API_KEY,
    CLAUDE_SETTINGS,
    CONTENT_PILLARS,
    POSTING_SCHEDULE,
    PROFILE,
)

logger = logging.getLogger("calendar_manager")

# Lazy-load Anthropic client to avoid initialization issues
_client = None


def _get_client():
    """Get or create Anthropic client (lazy initialization)."""
    global _client
    if _client is None:
        _client = Anthropic(api_key=ANTHROPIC_API_KEY)
    return _client

# Calendar entry schema
CALENDAR_ENTRY_SCHEMA = {
    "id": "post_001",
    "week": 1,
    "day": "Monday",
    "platform": "linkedin",
    "pillar": "Forex Education",
    "format": "text",
    "objective": "engagement",
    "topic": "3 trading mistakes beginners make with AI tools",
    "angle": "Hook: most traders use AI wrong",
    "visual_direction": "Person studying trading screens, multiple monitors",
    "cross_platform": [],
    "status": "planned",
    "content": "",
    "notes": "",
}


def _get_calendar_path(month: int, year: int) -> Path:
    """Get the file path for a calendar file."""
    filename = f"calendar_{month:02d}_{year}.json"
    return DATA_DIR / filename


def _get_lock_path(month: int, year: int) -> Path:
    """Get the lock file path for thread-safe operations."""
    lock_filename = f"calendar_{month:02d}_{year}.lock"
    return DATA_DIR / lock_filename


def _get_pillar_names(platform: str) -> List[str]:
    """Get pillar names based on platform."""
    if platform == "linkedin":
        return [p["name"] for p in CONTENT_PILLARS]
    elif platform == "whatsapp_status":
        # WhatsApp uses different pillar framework
        return ["Educate", "Prove", "Inspire", "Engage", "Convert"]
    else:
        return [p["name"] for p in CONTENT_PILLARS]


def _generate_calendar_with_claude(
    month: int, year: int, platforms: List[str], goal: Optional[str]
) -> List[Dict[str, Any]]:
    """
    Generate calendar entries using Claude AI.

    Args:
        month: Month number (1-12)
        year: Year
        platforms: List of platforms (e.g., ["linkedin", "whatsapp_status"])
        goal: Optional business goal for the month

    Returns:
        List of calendar entry dictionaries
    """
    logger.info(f"Generating calendar for {month}/{year} on platforms: {platforms}")

    # Prepare pillar information
    linkedin_pillars = _get_pillar_names("linkedin")
    linkedin_pillar_details = {p["name"]: p["description"] for p in CONTENT_PILLARS}

    whatsapp_pillars = _get_pillar_names("whatsapp_status")
    whatsapp_pillar_details = {
        "Educate": "Educational content teaching trading/financial concepts",
        "Prove": "Data-driven posts demonstrating trading principles with stats",
        "Inspire": "Motivational and success story content",
        "Engage": "Interactive polls, questions, and community engagement",
        "Convert": "Calls-to-action, course promotions, Gopipways mentions",
    }

    # Build platform specifications
    platform_specs = []
    if "linkedin" in platforms:
        platform_specs.append({
            "platform": "linkedin",
            "frequency": "6 times per week (Monday-Saturday)",
            "pillars": linkedin_pillars,
            "pillar_details": linkedin_pillar_details,
            "formats": ["text", "image", "carousel", "reel", "thread", "poll"],
            "objectives": ["awareness", "engagement", "enquiries", "authority"],
            "notes": "Personal brand content. Use first-person perspective.",
        })

    if "whatsapp_status" in platforms:
        platform_specs.append({
            "platform": "whatsapp_status",
            "frequency": "5 times per week",
            "pillars": whatsapp_pillars,
            "pillar_details": whatsapp_pillar_details,
            "formats": ["text", "image", "carousel"],
            "objectives": ["awareness", "engagement", "enquiries"],
            "notes": "Short, snappy content. 15-30 seconds when read. Use emojis.",
        })

    prompt = f"""Generate a complete monthly content calendar for {month}/{year}.

PROFILE:
- Name: {PROFILE['name']}
- Title: {PROFILE['title']}
- Company: {PROFILE['company']}
- Niche: {PROFILE['niche']}
- Audience: {PROFILE['audience']}
- Tone: {PROFILE['tone']}

PLATFORMS & SPECIFICATIONS:
{json.dumps(platform_specs, indent=2)}

REQUIREMENTS:
1. Create exactly 4 weeks of content (Week 1-4)
2. Distribute across all platforms specified
3. Spread pillars evenly - NO clustering of same pillar on consecutive days
4. For each entry, assign a specific day (Monday-Saturday for LinkedIn, 5 days/week for WhatsApp)
5. LinkedIn: 6 posts/week, WhatsApp: 5 posts/week
6. Cross-platform coordination: When the same topic appears on multiple platforms, use different angles
7. Each entry must include:
   - Unique ID (post_001, post_002, etc.)
   - Week (1-4)
   - Day (Monday, Tuesday, etc.)
   - Platform (linkedin or whatsapp_status)
   - Pillar (from the specified list)
   - Format (text, image, carousel, reel, thread, poll)
   - Objective (awareness, engagement, enquiries, authority)
   - Topic (2-10 words describing the topic)
   - Angle (Hook or unique angle - 1 sentence)
   - Visual direction (Only if format is image/carousel/reel)
   - Cross-platform (Array of related post IDs on other platforms)
   - Status (always "planned" for new entries)
   - Content (empty string for new entries)
   - Notes (Optional planning notes)

{f"MONTHLY GOAL: {goal}" if goal else ""}

OUTPUT:
Return ONLY a valid JSON array of calendar entries following the schema above. No markdown, no explanation, just the JSON array."""

    try:
        client = _get_client()
        response = client.messages.create(
            model=CLAUDE_SETTINGS["model"],
            max_tokens=8000,  # Needs to be large enough for full month of posts as JSON
            temperature=CLAUDE_SETTINGS.get("temperature_analysis", 0.3),
            messages=[{"role": "user", "content": prompt}],
        )

        response_text = response.content[0].text
        logger.info(f"Claude response length: {len(response_text)} chars, stop_reason: {response.stop_reason}")

        # Try to extract JSON from response
        json_match = re.search(r'\[.*\]', response_text, re.DOTALL)
        if not json_match:
            logger.error(f"Could not find JSON array in Claude response: {response_text[:500]}")
            raise ValueError("Claude response did not contain valid JSON array")

        entries = json.loads(json_match.group())

        if not isinstance(entries, list):
            raise ValueError("Parsed JSON is not an array")

        logger.info(f"Successfully generated {len(entries)} calendar entries")
        return entries

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse Claude response as JSON: {e}")
        logger.error(f"Raw response (first 500 chars): {response_text[:500]}")
        raise
    except Exception as e:
        logger.error(f"Error calling Claude API: {e}")
        raise


def create_monthly_calendar(
    month: int,
    year: int,
    platforms: Optional[List[str]] = None,
    goal: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Create a full month of content calendar entries using Claude AI.

    Args:
        month: Month number (1-12)
        year: Year
        platforms: List of platforms (default: ["linkedin", "whatsapp_status"])
        goal: Optional business goal for the month

    Returns:
        List of calendar entry dictionaries

    Raises:
        ValueError: If month/year are invalid
    """
    if not 1 <= month <= 12:
        raise ValueError(f"Invalid month: {month}")
    if year < 2024:
        raise ValueError(f"Invalid year: {year}")

    if platforms is None:
        platforms = ["linkedin", "whatsapp_status"]

    # Generate entries with Claude
    entries = _generate_calendar_with_claude(month, year, platforms, goal)

    # Validate entries
    validated_entries = []
    for entry in entries:
        validated_entry = _validate_entry(entry)
        validated_entries.append(validated_entry)

    # Save to file
    save_calendar(month, year, validated_entries)

    logger.info(f"Created monthly calendar for {month}/{year} with {len(validated_entries)} entries")
    return validated_entries


def load_calendar(month: int, year: int) -> List[Dict[str, Any]]:
    """
    Load a calendar from JSON file.

    Args:
        month: Month number (1-12)
        year: Year

    Returns:
        List of calendar entries, empty list if file doesn't exist
    """
    path = _get_calendar_path(month, year)
    lock_path = _get_lock_path(month, year)

    if not path.exists():
        logger.warning(f"Calendar file not found: {path}")
        return []

    try:
        with FileLock(str(lock_path), timeout=10):
            with open(path, "r") as f:
                entries = json.load(f)
                logger.info(f"Loaded calendar for {month}/{year} with {len(entries)} entries")
                return entries
    except Exception as e:
        logger.error(f"Error loading calendar {path}: {e}")
        raise


def save_calendar(month: int, year: int, entries: List[Dict[str, Any]]) -> None:
    """
    Save calendar entries to JSON file with thread-safe locking.

    Args:
        month: Month number (1-12)
        year: Year
        entries: List of calendar entries
    """
    path = _get_calendar_path(month, year)
    lock_path = _get_lock_path(month, year)

    try:
        with FileLock(str(lock_path), timeout=10):
            with open(path, "w") as f:
                json.dump(entries, f, indent=2)
            logger.info(f"Saved calendar for {month}/{year} with {len(entries)} entries")
    except Exception as e:
        logger.error(f"Error saving calendar {path}: {e}")
        raise


def get_calendar_summary(month: int, year: int) -> Dict[str, Any]:
    """
    Get a summary of calendar statistics.

    Args:
        month: Month number (1-12)
        year: Year

    Returns:
        Dictionary with summary statistics
    """
    entries = load_calendar(month, year)

    if not entries:
        return {
            "month": month,
            "year": year,
            "total_posts": 0,
            "by_platform": {},
            "by_pillar": {},
            "by_status": {},
            "by_week": {},
        }

    summary = {
        "month": month,
        "year": year,
        "total_posts": len(entries),
        "by_platform": {},
        "by_pillar": {},
        "by_status": {},
        "by_week": {},
        "by_format": {},
    }

    for entry in entries:
        platform = entry.get("platform", "unknown")
        summary["by_platform"][platform] = summary["by_platform"].get(platform, 0) + 1

        pillar = entry.get("pillar", "unknown")
        summary["by_pillar"][pillar] = summary["by_pillar"].get(pillar, 0) + 1

        status = entry.get("status", "unknown")
        summary["by_status"][status] = summary["by_status"].get(status, 0) + 1

        week = entry.get("week", 0)
        summary["by_week"][f"Week {week}"] = summary["by_week"].get(f"Week {week}", 0) + 1

        format_type = entry.get("format", "unknown")
        summary["by_format"][format_type] = summary["by_format"].get(format_type, 0) + 1

    return summary


def update_entry(
    month: int, year: int, entry_id: str, updates: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Update specific fields of a calendar entry.

    Args:
        month: Month number (1-12)
        year: Year
        entry_id: The entry ID to update
        updates: Dictionary of fields to update

    Returns:
        The updated entry

    Raises:
        ValueError: If entry not found
    """
    entries = load_calendar(month, year)

    entry_index = None
    for i, entry in enumerate(entries):
        if entry.get("id") == entry_id:
            entry_index = i
            break

    if entry_index is None:
        raise ValueError(f"Entry {entry_id} not found in calendar {month}/{year}")

    # Update the entry
    entries[entry_index].update(updates)

    # Save updated calendar
    save_calendar(month, year, entries)

    logger.info(f"Updated entry {entry_id} in calendar {month}/{year}")
    return entries[entry_index]


def get_entries_by_platform(
    month: int, year: int, platform: str
) -> List[Dict[str, Any]]:
    """
    Get all entries for a specific platform.

    Args:
        month: Month number (1-12)
        year: Year
        platform: Platform name (e.g., "linkedin", "whatsapp_status")

    Returns:
        List of matching entries
    """
    entries = load_calendar(month, year)
    return [e for e in entries if e.get("platform") == platform]


def get_entries_by_status(
    month: int, year: int, status: str
) -> List[Dict[str, Any]]:
    """
    Get all entries with a specific status.

    Args:
        month: Month number (1-12)
        year: Year
        status: Status value (planned, written, visual_ready, scheduled, published)

    Returns:
        List of matching entries
    """
    entries = load_calendar(month, year)
    return [e for e in entries if e.get("status") == status]


def get_entries_by_week(
    month: int, year: int, week: int
) -> List[Dict[str, Any]]:
    """
    Get all entries for a specific week.

    Args:
        month: Month number (1-12)
        year: Year
        week: Week number (1-4)

    Returns:
        List of matching entries
    """
    if not 1 <= week <= 4:
        raise ValueError(f"Invalid week: {week}")

    entries = load_calendar(month, year)
    return [e for e in entries if e.get("week") == week]


def _validate_entry(entry: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate and normalize a calendar entry.

    Args:
        entry: Raw entry dictionary from Claude

    Returns:
        Validated and normalized entry
    """
    validated = {}

    # ID validation — auto-generate if missing
    entry_id = entry.get("id", "")
    if not entry_id:
        import uuid
        entry_id = f"post_{uuid.uuid4().hex[:6]}"
    validated["id"] = entry_id

    # Week validation
    week = entry.get("week", 1)
    if not isinstance(week, int) or not 1 <= week <= 4:
        week = 1
    validated["week"] = week

    # Day validation
    valid_days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    day = entry.get("day", "Monday")
    if day not in valid_days:
        day = "Monday"
    validated["day"] = day

    # Platform validation
    valid_platforms = ["linkedin", "whatsapp_status", "twitter", "instagram", "tiktok"]
    platform = entry.get("platform", "linkedin")
    if platform not in valid_platforms:
        platform = "linkedin"
    validated["platform"] = platform

    # Pillar validation
    valid_pillars = _get_pillar_names(platform)
    pillar = entry.get("pillar", valid_pillars[0] if valid_pillars else "General")
    if pillar not in valid_pillars:
        pillar = valid_pillars[0] if valid_pillars else "General"
    validated["pillar"] = pillar

    # Format validation
    valid_formats = ["text", "image", "carousel", "reel", "thread", "poll", "video"]
    format_type = entry.get("format", "text")
    if format_type not in valid_formats:
        format_type = "text"
    validated["format"] = format_type

    # Objective validation
    valid_objectives = ["awareness", "engagement", "enquiries", "authority"]
    objective = entry.get("objective", "engagement")
    if objective not in valid_objectives:
        objective = "engagement"
    validated["objective"] = objective

    # Topic validation — use fallback if missing
    topic = entry.get("topic", "").strip()
    if not topic:
        topic = f"{validated.get('pillar', 'General')} post"
    validated["topic"] = topic

    # Angle validation
    angle = entry.get("angle", "").strip()
    validated["angle"] = angle

    # Visual direction validation
    visual_direction = entry.get("visual_direction", "").strip()
    validated["visual_direction"] = visual_direction

    # Cross-platform validation
    cross_platform = entry.get("cross_platform", [])
    if not isinstance(cross_platform, list):
        cross_platform = []
    validated["cross_platform"] = cross_platform

    # Status validation
    valid_statuses = ["planned", "written", "visual_ready", "scheduled", "published"]
    status = entry.get("status", "planned")
    if status not in valid_statuses:
        status = "planned"
    validated["status"] = status

    # Content validation
    content = entry.get("content", "").strip()
    validated["content"] = content

    # Notes validation
    notes = entry.get("notes", "").strip()
    validated["notes"] = notes

    return validated


def export_calendar_to_csv(month: int, year: int, output_path: Optional[Path] = None) -> Path:
    """
    Export calendar to CSV format for spreadsheet review.

    Args:
        month: Month number (1-12)
        year: Year
        output_path: Optional output path (default: DATA_DIR/calendar_{month}_{year}.csv)

    Returns:
        Path to exported CSV file
    """
    import csv

    entries = load_calendar(month, year)

    if output_path is None:
        output_path = DATA_DIR / f"calendar_{month:02d}_{year}.csv"

    fieldnames = [
        "id", "week", "day", "platform", "pillar", "format", "objective",
        "topic", "angle", "visual_direction", "cross_platform", "status", "notes"
    ]

    try:
        with open(output_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for entry in entries:
                row = {field: entry.get(field, "") for field in fieldnames}
                if isinstance(row["cross_platform"], list):
                    row["cross_platform"] = ", ".join(row["cross_platform"])
                writer.writerow(row)

        logger.info(f"Exported calendar to CSV: {output_path}")
        return output_path

    except Exception as e:
        logger.error(f"Error exporting calendar to CSV: {e}")
        raise


def import_calendar_from_csv(csv_path: Path, month: int, year: int) -> List[Dict[str, Any]]:
    """
    Import calendar entries from CSV file.

    Args:
        csv_path: Path to CSV file
        month: Month number (1-12)
        year: Year

    Returns:
        List of imported entries
    """
    import csv

    entries = []

    try:
        with open(csv_path, "r") as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Parse cross_platform from comma-separated string
                cross_platform = [
                    p.strip() for p in row.get("cross_platform", "").split(",")
                    if p.strip()
                ]

                entry = {
                    "id": row["id"],
                    "week": int(row.get("week", 1)),
                    "day": row["day"],
                    "platform": row["platform"],
                    "pillar": row["pillar"],
                    "format": row["format"],
                    "objective": row["objective"],
                    "topic": row["topic"],
                    "angle": row.get("angle", ""),
                    "visual_direction": row.get("visual_direction", ""),
                    "cross_platform": cross_platform,
                    "status": row.get("status", "planned"),
                    "content": row.get("content", ""),
                    "notes": row.get("notes", ""),
                }

                validated_entry = _validate_entry(entry)
                entries.append(validated_entry)

        # Save imported entries
        save_calendar(month, year, entries)
        logger.info(f"Imported {len(entries)} entries from CSV")
        return entries

    except Exception as e:
        logger.error(f"Error importing calendar from CSV: {e}")
        raise


if __name__ == "__main__":
    # Example usage for testing
    logging.basicConfig(level=logging.INFO)

    # Generate a test calendar
    print("Generating test calendar for April 2026...")
    entries = create_monthly_calendar(4, 2026, platforms=["linkedin"])

    # Get summary
    summary = get_calendar_summary(4, 2026)
    print(f"\nCalendar Summary:")
    print(json.dumps(summary, indent=2))

    # Get LinkedIn entries
    linkedin_entries = get_entries_by_platform(4, 2026, "linkedin")
    print(f"\nLinkedIn entries: {len(linkedin_entries)}")
    for entry in linkedin_entries[:3]:
        print(f"  - {entry['id']}: {entry['topic']}")
