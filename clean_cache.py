import json
import re
from pathlib import Path

def clean_cached_summaries():
    # Get the cache directory
    cache_dir = Path(".aider") / "caches" / "summaries"
    if not cache_dir.exists():
        print("No cache directory found!")
        return

    # Process each JSON file in the cache
    for cache_file in cache_dir.glob("*.json"):
        print(f"Processing {cache_file}")
        try:
            # Load the cached data
            with open(cache_file, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)

            # Get the summary content
            summary = cache_data.get("summary", "")
            if not summary:
                continue

            # Strip out <note> sections
            cleaned_summary = re.sub(r'<note>.*?</note>', '', summary, flags=re.DOTALL)

            if cleaned_summary != summary:
                print(f"Cleaned notes from {cache_file}")
                # Update the cache file with cleaned summary
                cache_data["summary"] = cleaned_summary
                with open(cache_file, 'w', encoding='utf-8') as f:
                    json.dump(cache_data, f, indent=2)

        except Exception as e:
            print(f"Error processing {cache_file}: {e}")

if __name__ == "__main__":
    print("Starting cache cleanup...")
    clean_cached_summaries()
    print("Cache cleanup complete!")
