import json
import re
from pathlib import Path


def repair_dictionary(input_file, output_file=None):
    """
    Repair a malformed dictionary JSON file by extracting all valid entries.
    The issue: save_dictionary wrote batches as nested arrays [batch1, batch2, ...]
    instead of flat arrays [entry1, entry2, entry3, ...]
    """
    if output_file is None:
        output_file = input_file
    
    print(f"Reading {input_file}...")
    with open(input_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Strategy: Find all dictionary entry objects by pattern matching
    # Each entry has: sanskrit, name, flat, definitions
    
    # Use regex to find all complete entry objects
    # Pattern matches: { "sanskrit": "...", "name": "...", "flat": "...", "definitions": [...] }
    
    entries = []
    
    # Try to parse as-is first (might work if structure is just nested)
    try:
        data = json.loads(content)
        # Flatten if nested
        entries = flatten_entries(data)
        print(f"Parsed successfully, found {len(entries)} entries (after flattening)")
    except json.JSONDecodeError as e:
        print(f"JSON parse failed: {e}")
        print("Attempting manual extraction...")
        entries = extract_entries_manually(content)
    
    if not entries:
        print("ERROR: Could not extract any entries!")
        return
    
    print(f"Total entries extracted: {len(entries)}")
    
    # Validate entries
    valid_entries = []
    for entry in entries:
        if isinstance(entry, dict) and 'sanskrit' in entry and 'name' in entry and 'definitions' in entry:
            valid_entries.append(entry)
    
    print(f"Valid entries: {len(valid_entries)}")
    
    # Save repaired file
    print(f"Saving to {output_file}...")
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(valid_entries, f, ensure_ascii=False, indent=4)
    
    print("Done!")


def flatten_entries(data):
    """Recursively flatten nested arrays to extract all entry objects."""
    entries = []
    
    if isinstance(data, list):
        for item in data:
            if isinstance(item, list):
                # Nested array - recurse
                entries.extend(flatten_entries(item))
            elif isinstance(item, dict) and 'sanskrit' in item:
                # This is an entry
                entries.append(item)
    elif isinstance(data, dict) and 'sanskrit' in data:
        entries.append(data)
    
    return entries


def extract_entries_manually(content):
    """
    Extract entries using regex when JSON parsing fails.
    """
    entries = []
    
    # Pattern to match entry objects
    # This is a simplified approach - find all {...} blocks that look like entries
    pattern = r'\{\s*"sanskrit"\s*:\s*"[^"]*"\s*,\s*"name"\s*:\s*"[^"]*"\s*,\s*"flat"\s*:\s*"[^"]*"\s*,\s*"definitions"\s*:\s*\[.*?\]\s*\}'
    
    # This won't work well due to nested braces, so let's try a different approach
    # Parse character by character to find balanced braces
    
    i = 0
    while i < len(content):
        # Find start of an object that looks like an entry
        match = re.search(r'\{\s*"sanskrit"', content[i:])
        if not match:
            break
        
        start = i + match.start()
        
        # Find the matching closing brace
        brace_count = 0
        j = start
        while j < len(content):
            if content[j] == '{':
                brace_count += 1
            elif content[j] == '}':
                brace_count -= 1
                if brace_count == 0:
                    # Found complete object
                    obj_str = content[start:j+1]
                    try:
                        entry = json.loads(obj_str)
                        if 'sanskrit' in entry and 'definitions' in entry:
                            entries.append(entry)
                    except json.JSONDecodeError:
                        pass
                    break
            j += 1
        
        i = j + 1
        
        if len(entries) % 1000 == 0 and len(entries) > 0:
            print(f"  Extracted {len(entries)} entries...")
    
    return entries


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python repair_dictionary.py <file.json> [output.json]")
        print("       python repair_dictionary.py all  - Repair all dictionary_*.json files")
        sys.exit(1)
    
    if sys.argv[1] == "all":
        files = list(Path('.').glob('dictionary_??.json'))
        print(f"Found files: {[f.name for f in files]}")
        
        for f in files:
            print(f"\n{'='*50}")
            print(f"Repairing {f.name}...")
            repair_dictionary(str(f))
    else:
        input_file = sys.argv[1]
        output_file = sys.argv[2] if len(sys.argv) > 2 else None
        repair_dictionary(input_file, output_file)
