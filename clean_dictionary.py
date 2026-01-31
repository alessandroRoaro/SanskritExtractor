import json
import re
from pathlib import Path


def clean_dictionary(input_file, output_file=None):
    """
    Clean HTML tags from dictionary definitions.
    
    - Removes simple tags: <i>, <b>, <u>, <math>
    - Extracts <mark> and <del> content as separate definitions
    """
    if output_file is None:
        output_file = input_file  # Overwrite in place
    
    print(f"Loading {input_file}...")
    with open(input_file, 'r', encoding='utf-8') as f:
        dictionary = json.load(f)
    
    total_entries = len(dictionary)
    extracted_count = 0
    cleaned_tags_count = 0
    
    for entry_idx, entry in enumerate(dictionary):
        if entry_idx % 1000 == 0:
            print(f"Processing entry {entry_idx}/{total_entries}...")
        
        new_definitions = []
        
        for def_obj in entry.get('definitions', []):
            definition = def_obj['definition']
            
            # Check for <mark> or <del> tags with content to extract
            # Pattern: <mark>sanskrit_text</mark> rest_of_definition
            # or: <del>sanskrit_text</del> rest_of_definition
            mark_pattern = r'<(mark|del)>\s*([^<]+)</\1>\s*(.+)$'
            
            match = re.search(mark_pattern, definition)
            
            if match:
                tag_type = match.group(1)
                sanskrit_term = match.group(2).strip()
                new_definition_text = match.group(3).strip()
                
                # Clean the original definition (remove the extracted part)
                original_clean = definition[:match.start()].strip()
                
                # Update the original definition
                def_obj['definition'] = original_clean
                
                # Create new definition for the extracted term
                new_def = {
                    'definition': new_definition_text,
                    'isVerb': False,
                    'isRootVerb': False,
                    'extracted_sanskrit': sanskrit_term  # Keep track of the Sanskrit term
                }
                new_definitions.append(new_def)
                extracted_count += 1
            
            # Remove simple HTML tags from all definitions
            original_def = def_obj['definition']
            cleaned_def = re.sub(r'</?(?:i|b|u|math)>', '', original_def)
            
            if cleaned_def != original_def:
                def_obj['definition'] = cleaned_def
                cleaned_tags_count += 1
        
        # Add any new definitions extracted from mark/del tags
        if new_definitions:
            entry['definitions'].extend(new_definitions)
            # Also clean the new definitions
            for new_def in new_definitions:
                new_def['definition'] = re.sub(r'</?(?:i|b|u|math)>', '', new_def['definition'])
    
    print(f"\nSaving to {output_file}...")
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(dictionary, f, ensure_ascii=False, indent=4)
    
    print(f"\n=== Summary ===")
    print(f"Total entries processed: {total_entries}")
    print(f"Definitions with <mark>/<del> extracted: {extracted_count}")
    print(f"Definitions with HTML tags cleaned: {cleaned_tags_count}")
    print(f"Output saved to: {output_file}")


def preview_changes(input_file, num_examples=5):
    """
    Preview what changes would be made without saving.
    """
    print(f"Loading {input_file} for preview...")
    with open(input_file, 'r', encoding='utf-8') as f:
        dictionary = json.load(f)
    
    mark_examples = []
    tag_examples = []
    
    for entry in dictionary:
        for def_obj in entry.get('definitions', []):
            definition = def_obj['definition']
            
            # Check for mark/del tags
            if '<mark>' in definition or '<del>' in definition:
                if len(mark_examples) < num_examples:
                    mark_examples.append({
                        'name': entry['name'],
                        'definition': definition
                    })
            
            # Check for other HTML tags
            elif re.search(r'</?(?:i|b|u|math)>', definition):
                if len(tag_examples) < num_examples:
                    tag_examples.append({
                        'name': entry['name'],
                        'definition': definition[:200] + '...' if len(definition) > 200 else definition
                    })
    
    print("\n=== Examples with <mark>/<del> tags (will be extracted) ===")
    for ex in mark_examples:
        print(f"\n📖 {ex['name']}:")
        print(f"   {ex['definition'][:300]}...")
    
    print("\n=== Examples with <i>/<b>/<u> tags (will be removed) ===")
    for ex in tag_examples:
        print(f"\n📖 {ex['name']}:")
        print(f"   {ex['definition']}")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python clean_dictionary.py preview <file.json>   - Preview changes")
        print("  python clean_dictionary.py clean <file.json>     - Clean and save")
        print("  python clean_dictionary.py clean_all             - Clean all dictionary_*.json files")
        sys.exit(1)
    
    command = sys.argv[1]
    
    if command == "preview" and len(sys.argv) >= 3:
        preview_changes(sys.argv[2])
    
    elif command == "clean" and len(sys.argv) >= 3:
        clean_dictionary(sys.argv[2])
    
    elif command == "clean_all":
        files = list(Path('.').glob('dictionary_??.json'))  # dictionary_it.json, dictionary_en.json, etc.
        print(f"Found {len(files)} dictionary files to clean: {[f.name for f in files]}")
        
        for f in files:
            print(f"\n{'='*50}")
            clean_dictionary(str(f))
    
    else:
        print("Invalid command. Use: preview, clean, or clean_all")
