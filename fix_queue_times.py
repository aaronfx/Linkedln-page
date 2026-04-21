"""
Fix queue post times on the persistent volume.
Run at startup to correct scheduling times.
"""
import json
import os
from pathlib import Path
from datetime import datetime

def fix_queue_times():
    """Fix scheduled times in the content queue to match optimized schedule."""
    from config import CONTENT_QUEUE_FILE, DATA_DIR, POSTING_SCHEDULE
    
    queue_path = Path(CONTENT_QUEUE_FILE)
    print(f"[fix_times] Queue path: {queue_path}")
    print(f"[fix_times] Queue exists: {queue_path.exists()}")
    print(f"[fix_times] DATA_DIR: {DATA_DIR}")
    
    if not queue_path.exists():
        print("[fix_times] No queue file found, skipping")
        return
    
    with open(queue_path) as f:
        queue = json.load(f)
    
    print(f"[fix_times] Loaded {len(queue)} posts")
    
    # Build day->time mapping from POSTING_SCHEDULE
    day_times = {}
    for day_name, info in POSTING_SCHEDULE.items():
        day_times[day_name.lower()] = info["time"]
    
    print(f"[fix_times] Schedule: {day_times}")
    
    changes = 0
    for post in queue:
        sd = post.get("scheduled_date", "")
        if not sd:
            continue
        try:
            dt = datetime.strptime(sd, "%Y-%m-%d")
            day_name = dt.strftime("%A").lower()
            if day_name in day_times:
                new_time = day_times[day_name]
                old_time = post.get("scheduled_time", "")
                if old_time != new_time:
                    post["scheduled_time"] = new_time
                    # Rebuild display_date
                    hour = int(new_time.split(":")[0])
                    minute = int(new_time.split(":")[1])
                    ampm = "AM" if hour < 12 else "PM"
                    display_hour = hour if hour <= 12 else hour - 12
                    if display_hour == 0:
                        display_hour = 12
                    post["display_date"] = dt.strftime(f"%a, %b %d at {display_hour:02d}:{minute:02d} {ampm}")
                    # Rebuild scheduled_datetime
                    post["scheduled_datetime"] = f"{sd}T{new_time}:00"
                    changes += 1
                    print(f"[fix_times] {sd} ({day_name}): {old_time} -> {new_time}")
        except Exception as e:
            print(f"[fix_times] Error processing {sd}: {e}")
    
    if changes > 0:
        with open(queue_path, "w") as f:
            json.dump(queue, f, indent=2, default=str)
        print(f"[fix_times] Saved {changes} changes")
    else:
        print("[fix_times] No changes needed")

if __name__ == "__main__":
    fix_queue_times()
