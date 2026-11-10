import re
import json

from iast_to_flat_converter import convert_iast_to_flat
from sanskrit_char_extractor import is_sanskrit_char

# TODO some verbs are missing from before

# Root verb symbol used to split multiple definitions
ROOT_SYMBOL = '√'

# Subscript digits pattern to detect numbered definitions
SUBSCRIPT_DIGITS = '₀₁₂₃₄₅₆₇₈₉'
SUBSCRIPT_PATTERN = re.compile(f'[{SUBSCRIPT_DIGITS}]+$')

# Pattern to detect sub-entries: IAST word followed by [...] or |...|
# IAST word: Latin letters with diacritics and Vedic accents
# For [...]: matches "word [...]" 
# For |...|: matches "word |short-etymology|" (content must be short, typically 1-2 words)
IAST_CHARS = r'a-zA-ZāīūṛṝḷḹēōṃḥñṅṇṭḍśṣĀĪŪṚṜḶḸĒŌṂḤÑṄṆṬḌŚṢáíúéóÁÍÚÉÓàìùèòÀÌÙÈÒ₀₁₂₃₄₅₆₇₈₉'

# Pattern for square brackets: word [...]
SUB_ENTRY_SQUARE_BRACKET = re.compile(
    rf'^([{IAST_CHARS}]+)\s*\['
)

# Pattern for pipe brackets: word |short-word| 
# Content between pipes must be short (max ~20 chars) to be etymology, not definition separator
SUB_ENTRY_PIPE_BRACKET = re.compile(
    rf'^([{IAST_CHARS}]+)\s*\|[^|]{{1,20}}\|'
)


def has_subscript(word):
    """Check if a word ends with subscript digits."""
    return bool(SUBSCRIPT_PATTERN.search(word))


def strip_subscript(word):
    """Remove subscript digits from the end of a word."""
    return SUBSCRIPT_PATTERN.sub('', word)


def is_sub_entry_line(line):
    """Check if a line starts a sub-entry (IAST word followed by brackets)."""
    line = line.strip()
    return SUB_ENTRY_SQUARE_BRACKET.match(line) or SUB_ENTRY_PIPE_BRACKET.match(line)


def get_sub_entry_name(line):
    """Extract the name from a sub-entry line."""
    line = line.strip()
    match = SUB_ENTRY_SQUARE_BRACKET.match(line)
    if match:
        return match.group(1)
    match = SUB_ENTRY_PIPE_BRACKET.match(line)
    if match:
        return match.group(1)
    return None


def strip_html(text):
    """Remove HTML tags such as <i>...</i>."""
    return re.sub(r'<[^>]+>', '', text)


def clean_slash_artifacts(text):
    """Remove backslash delimiters left in the source, such as '\\ dhyā \\' or '\\,'."""
    text = text.replace('\x08', '')
    text = text.replace('\\,', ' ')
    # Keep letter commands (\theta); drop delimiter backslashes.
    text = re.sub(r'\\(?![A-Za-z])', '', text)
    text = re.sub(r' +', ' ', text)
    return text.strip()


IAST_TOKEN = re.compile(rf'^[{IAST_CHARS}]+$')


def bare_root_name(line):
    """IAST name of a root line that has no Devanagari, e.g. '√ dhyā' or '√ pac v. [1]'."""
    line = line.strip()
    if not line.startswith(ROOT_SYMBOL):
        return None
    tokens = line[len(ROOT_SYMBOL):].split()
    if not tokens or not IAST_TOKEN.match(tokens[0]):
        return None
    if all(IAST_TOKEN.match(token) for token in tokens):
        return ''.join(tokens)
    return tokens[0]


def clean_definition_text(text):
    """Clean up HTML, slash artifacts, and whitespace in definition text."""
    text = strip_html(text)
    text = clean_slash_artifacts(text)
    # Replace multiple spaces with single space
    text = re.sub(r' +', ' ', text)
    # Remove leading/trailing whitespace
    text = text.strip()
    return text


def clean_name(name):
    """Clean up a name: lowercase, strip HTML tags, remove control chars."""
    name = strip_html(name)
    # Remove control characters
    name = re.sub(r'[\x00-\x1f\x7f]', '', name)
    # Strip subscripts and lowercase
    name = strip_subscript(name).lower()
    # Remove any remaining leading/trailing whitespace
    name = name.strip()
    return name


def is_hyphen_annotation(headword):
    """Suffix and grammar notes such as -a, -as, -ni are not dictionary terms."""
    return bool(headword) and headword.startswith('-')


def line_headword(line, sanskrit_end):
    """First IAST token of a line, after a leading Devanagari headword when present."""
    if sanskrit_end:
        rest = line[sanskrit_end:].strip()
        if rest:
            return rest.split()[0]
    tokens = line.split()
    if not tokens:
        return None
    if tokens[0] == ROOT_SYMBOL:
        return tokens[1] if len(tokens) > 1 else None
    return tokens[0]


def is_valid_name(name):
    """Check if a name is valid (not empty, not just numbers, no malformed chars)."""
    if not name:
        return False
    # Reject names that are just numbers
    if re.match(r'^[0-9]+$', name):
        return False
    # Reject names with ~ (malformed from PDF extraction)
    if '~' in name:
        return False
    # Reject names that are too long (likely malformed)
    if len(name) > 50:
        return False
    return True


def should_group_with_current_entry(current_entry, sanskrit_word, name):
    """
    Check if a new definition should be grouped with the current entry.
    Only group when:
    - Same Sanskrit word
    - Name has a subscript AND base name matches current entry's name
    """
    if current_entry is None:
        return False
    
    if current_entry['sanskrit'] != sanskrit_word:
        return False
    
    if not has_subscript(name):
        return False
    
    # Check if base names match (without subscripts)
    clean_name = strip_subscript(name)
    return clean_name == current_entry['name']


def create_definition_object(definition_text):
    """Create a definition object with isVerb and isRootVerb flags."""
    definition_text = clean_definition_text(definition_text)
    is_verb = bool(re.search(r'\Wv\.\W', definition_text)) or bool(re.search(r'^v\.', definition_text))
    is_root_verb = definition_text.startswith(ROOT_SYMBOL)
    
    return {
        "definition": definition_text,
        "isVerb": is_verb,
        "isRootVerb": is_root_verb,
    }


def extract_verbs_and_terms_from_text_file(file_path):
    """Extract verbs and associated text between specified markers from a text file."""
    with open(file_path, 'r', encoding='utf-8') as file:
        text = file.read()

        # Track matches
        extracted_entries = []
        lines = text.splitlines()
        current_entry = None
        current_raw_definitions = []  # List of raw definition strings
        pending_sanskrit = None  # Sanskrit word waiting for IAST name on next line
        pending_root_prefix = False  # Whether there was a √ before pending Sanskrit
        skipping_annotation = False  # Continuation of a hyphenated grammar note

        for line in lines:
            if line == '':
                continue

            line = clean_slash_artifacts(line.strip())
            if line == '':
                continue

            # Scan for Sanskrit characters in this line
            sanskrit_word = None
            sanskrit_word_index = None
            sanskrit_word_index_end = None
            
            for index, char in enumerate(line):
                if is_sanskrit_char(char):
                    sanskrit_word = (sanskrit_word or '') + char
                    if sanskrit_word_index is None:
                        sanskrit_word_index = index
                elif sanskrit_word is not None:
                    if char != ' ' and line[index - 1] != ' ':
                        sanskrit_word = None
                        sanskrit_word_index = None
                    elif char != ' ':
                        sanskrit_word_index_end = index
                        break

            headword = line_headword(line, sanskrit_word_index_end)
            if is_hyphen_annotation(headword):
                skipping_annotation = True
                pending_sanskrit = None
                pending_root_prefix = False
                continue

            # Process words to remove hyphens
            words = line.split()
            processed_words = []
            for word in words:
                processed_word = re.sub(r'(?<!\s)(\s?)-(\s?)(?!\s)', r'\1\2', word)
                processed_words.append(processed_word)
            line = ' '.join(processed_words)

            # Case 1: We have a pending Sanskrit from previous line, this line should have the IAST name
            if pending_sanskrit is not None:
                skipping_annotation = False
                line_stripped = line.strip()
                if line_stripped:
                    words_in_line = line_stripped.split()
                    name = words_in_line[0] if words_in_line else ''
                    
                    if name:
                        # Build the definition text
                        if pending_root_prefix:
                            definition_text = ROOT_SYMBOL + ' ' + line_stripped
                        else:
                            definition_text = line_stripped
                        
                        cleaned_name = clean_name(name)
                        
                        # Skip invalid names
                        if not is_valid_name(cleaned_name):
                            pending_sanskrit = None
                            pending_root_prefix = False
                            continue
                        
                        # Check if should group with current entry (same Sanskrit, same base name with subscript)
                        if should_group_with_current_entry(current_entry, pending_sanskrit, name):
                            current_raw_definitions.append(definition_text)
                        else:
                            # Save previous entry if exists
                            if current_entry:
                                for raw_def in current_raw_definitions:
                                    current_entry['definitions'].append(create_definition_object(raw_def))
                                extracted_entries.append(current_entry)
                            
                            # Start new entry
                            current_entry = {
                                "sanskrit": pending_sanskrit,
                                "name": cleaned_name,
                                "flat": convert_iast_to_flat(cleaned_name).lower(),
                                "definitions": [],
                            }
                            current_raw_definitions = [definition_text]
                
                pending_sanskrit = None
                pending_root_prefix = False
                continue

            # Case 2: Sanskrit found on this line
            if sanskrit_word is not None:
                skipping_annotation = False
                # Check if there's a √ symbol before the Sanskrit word
                prefix_before_sanskrit = line[:sanskrit_word_index].strip() if sanskrit_word_index else ''
                has_root_prefix = prefix_before_sanskrit.endswith(ROOT_SYMBOL)
                
                line_after_sanskrit = line[sanskrit_word_index_end:] if sanskrit_word_index_end else ''

                # If nothing after Sanskrit, wait for next line
                if line_after_sanskrit.strip() == '':
                    pending_sanskrit = sanskrit_word
                    pending_root_prefix = has_root_prefix
                    continue

                name = line_after_sanskrit.split()[0]
                
                # Build the full definition text
                if has_root_prefix:
                    definition_text = ROOT_SYMBOL + ' ' + line_after_sanskrit
                else:
                    definition_text = line_after_sanskrit
                
                cleaned_name = clean_name(name)
                
                # Skip invalid names
                if not is_valid_name(cleaned_name):
                    continue
                
                # Check if should group with current entry (same Sanskrit, same base name with subscript)
                if should_group_with_current_entry(current_entry, sanskrit_word, name):
                    current_raw_definitions.append(definition_text)
                else:
                    # Save previous entry if exists
                    if current_entry:
                        for raw_def in current_raw_definitions:
                            current_entry['definitions'].append(create_definition_object(raw_def))
                        extracted_entries.append(current_entry)
                    
                    # Start new entry
                    current_entry = {
                        "sanskrit": sanskrit_word,
                        "name": cleaned_name,
                        "flat": convert_iast_to_flat(cleaned_name).lower(),
                        "definitions": [],
                    }
                    current_raw_definitions = [definition_text]

            # Case 2b: Root headword with no Devanagari, e.g. "√ dhyā"
            elif (root_name := bare_root_name(line)) and is_valid_name(clean_name(root_name)):
                skipping_annotation = False
                cleaned_name = clean_name(root_name)
                tokens = line[len(ROOT_SYMBOL):].split()
                if all(IAST_TOKEN.match(token) for token in tokens):
                    definition_text = ROOT_SYMBOL + ' ' + root_name
                else:
                    definition_text = line

                if current_entry:
                    for raw_def in current_raw_definitions:
                        current_entry['definitions'].append(create_definition_object(raw_def))
                    extracted_entries.append(current_entry)

                current_entry = {
                    "sanskrit": "",
                    "name": cleaned_name,
                    "flat": convert_iast_to_flat(cleaned_name).lower(),
                    "definitions": [],
                }
                current_raw_definitions = [definition_text]

            # Case 3: No Sanskrit, check if it's a sub-entry or continuation
            elif current_entry and line.strip() != '' and not re.search(r'^\d+$', line):
                line_stripped = line.strip()
                if skipping_annotation and not is_sub_entry_line(line_stripped):
                    continue
                skipping_annotation = False
                is_new_sub_entry = False
                
                # Check if this line starts a sub-entry (IAST word + brackets)
                if is_sub_entry_line(line_stripped):
                    sub_entry_name = get_sub_entry_name(line_stripped)
                    cleaned_name = clean_name(sub_entry_name)
                    
                    # Only create sub-entry if name is valid
                    if is_valid_name(cleaned_name):
                        is_new_sub_entry = True
                        # Save current entry first
                        if current_raw_definitions:
                            for raw_def in current_raw_definitions:
                                current_entry['definitions'].append(create_definition_object(raw_def))
                            extracted_entries.append(current_entry)
                        
                        # Create new entry for sub-entry using parent's Sanskrit
                        current_entry = {
                            "sanskrit": current_entry['sanskrit'],  # Use parent's Sanskrit
                            "name": cleaned_name,
                            "flat": convert_iast_to_flat(cleaned_name).lower(),
                            "definitions": [],
                        }
                        current_raw_definitions = [line_stripped]
                
                if not is_new_sub_entry:
                    # Append to the last raw definition
                    if current_raw_definitions:
                        current_raw_definitions[-1] += ' ' + line_stripped

        # Add any remaining entry
        if current_entry is not None and current_raw_definitions:
            for raw_def in current_raw_definitions:
                if raw_def.strip():
                    current_entry['definitions'].append(create_definition_object(raw_def))
            extracted_entries.append(current_entry)

    return extracted_entries


def merge_entries_with_same_name(entries):
    """
    Post-process entries to merge those with the same Sanskrit and same base name.
    This handles cases where numbered definitions (like dhī₁, dhī₂, dhī₃) are 
    separated by sub-entries in the source text.
    """
    merged = {}
    order = []  # Keep track of first occurrence order
    
    for entry in entries:
        key = (entry['sanskrit'], entry['name'])
        
        if key in merged:
            # Merge definitions into existing entry
            merged[key]['definitions'].extend(entry['definitions'])
        else:
            # New entry
            merged[key] = {
                "sanskrit": entry['sanskrit'],
                "name": entry['name'],
                "flat": entry['flat'],
                "definitions": list(entry['definitions']),
            }
            order.append(key)
    
    # Return entries in original order
    return [merged[key] for key in order]


# Usage
file_path = 'extracted_dictionary_micro1.txt'

extracted_entries = extract_verbs_and_terms_from_text_file(file_path)
# Merge entries with same Sanskrit and name
extracted_entries = merge_entries_with_same_name(extracted_entries)

file_path = 'dictionary_micro1.json'
with open(file_path, 'w', encoding='utf-8') as json_file:
    json.dump(extracted_entries, json_file, ensure_ascii=False, indent=4)
