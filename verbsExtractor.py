import re
import json
import argparse
import unicodedata


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
# Match precomposed Latin IAST, decomposed diacritics and homonym subscripts.
IAST_CHARS = r"A-Za-zÀ-ɏḀ-ỿ\u0300-\u036f₀-₉"
IAST_HEADWORD_RE = re.compile(rf"^[{IAST_CHARS}]+$")
# Only a leading Devanagari sequence can start a dictionary entry.
DEVANAGARI_HEAD_RE = re.compile(
    r"^(?:√\s*)?(?P<deva>[\u0900-\u097F\uA8E0-\uA8FF]+"
    r"(?:\s+[\u0900-\u097F\uA8E0-\uA8FF]+)*)(?=\s|$)"
)
# OCR substitutions in Sanskrit headwords, not arbitrary running prose.
BENGALI_HEAD_RE = re.compile(
    r"^(?P<prefix>\s*(?:√\s*)?)(?P<word>[\u0981-\u09E3]+)(?=\s|$)",
    re.MULTILINE,
)
MALFORMED_SUB_ENTRY_RE = re.compile(
    rf"^(?P<name>[{IAST_CHARS}]+)\s*\[[{IAST_CHARS}\s-]{{1,30}}\|\s*"
)
# Latin-only subentries without etymology: adverbs are often printed as
# "dhīram adv. tranquillement." rather than "dhīram [..] adv. ...".
# Do not interpret arbitrary French prose as dictionary headwords.
BARE_GRAMMATICAL_HEAD_RE = re.compile(
    rf"^(?P<name>[{IAST_CHARS}]+)\s+"
    rf"(?:adv\.|ind\.|m\.|n\.|f\.|a\.\s*m\.)\s+\S"
)
# Etymology-free Sanskrit compounds can be labelled only by a subject
# abbreviation, e.g. "nāmadhātuprakriyā gram." or "nicrdgāyatrī lit.".
# Such labels also occur in French prose, so require an IAST-looking compound,
# including a Sanskrit diacritic, rather than trusting the label alone.
BARE_SUBJECT_HEAD_RE = re.compile(
    rf"^(?P<name>[{IAST_CHARS}]+)\\s+(?:gram\\.|lit\\.)\\s+\\S"
)
SANSKRIT_HEAD_DIACRITIC_RE = re.compile(r"[āīūṛṝḷḹṃḥṅñṇṭḍśṣ]")

FOREIGN_OCR_LEADER_RE = re.compile(
    r"^[\u0A00-\u0A7F\u0980-\u09FF\uAC00-\uD7AF\u0400-\u04FF]+"
    r"\s+(?P<rest>.+)$"
)

POS_AFTER_ETYMOLOGY_RE = re.compile(
    r"^\s*(?:var\.\s*\S+\s*)?"
    r"(?:a\.|m\.|n\.|f\.|v\.|ind\.|ifc\.|adv\.|np\.|"
    r"pp\.|ppr\.|act\.|cf\.|lit\.|mod\.|soc\.|myth\.|"
    r"hist\.|véd\.|bd\.|phil\.|gram\.|num\.|iic\.)"
)
# Known IAST glyph substitutions made by OCR.
IAST_OCR_FIXES = str.maketrans({
    "ş": "ṣ", "Ş": "Ṣ", "ș": "ṣ", "Ș": "Ṣ",
    "ţ": "ṭ", "Ţ": "Ṭ", "ț": "ṭ", "Ț": "Ṭ",
})
NON_DECOMPOSABLE_LETTERS = {
    "ł": "l", "Ł": "L", "đ": "d", "Đ": "D",
    "ħ": "h", "Ħ": "H", "ø": "o", "Ø": "O",
    "ŋ": "n", "Ŋ": "N", "ð": "d", "Ð": "D",
    "ß": "ss", "æ": "ae", "Æ": "AE",
    "œ": "oe", "Œ": "OE", "ı": "i",
}


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


def sub_entry_match(line, next_line=""):
    """Recognize standalone Latin-only headwords with etymology and POS.

    The POS requirement avoids promoting French prose with [...] to entries.
    A candidate with a damaged annotation remains part of the preceding
    definition, rather than silently inventing a term.
    """
    line = line.strip()
    # A foreign-script OCR glyph in the Devanagari column is not part
    # of the Latin headword. Recover the boundary but not its spelling.
    foreign = FOREIGN_OCR_LEADER_RE.match(line)
    if foreign:
        candidate_line = foreign.group("rest")
        if (SUB_ENTRY_SQUARE_BRACKET.match(candidate_line)
                or BARE_GRAMMATICAL_HEAD_RE.match(candidate_line)):
            line = candidate_line

    bare = BARE_GRAMMATICAL_HEAD_RE.match(line)
    if bare:
        name = bare.group("name")
        normalized = clean_name(name)
        if (is_valid_name(normalized) and len(normalized) >= 4
                and not re.search(r"[éèêëàâîïôöùûüç]", name, re.I)
                and normalized not in {
                    "dans", "pour", "avec", "sans", "plus", "tout",
                    "tous", "mais", "dont", "leur", "elle", "elles",
                    "nous", "vous", "ainsi", "alors", "comme",
                    "fait", "être", "vers", "entre", "cela",
                }):
            return name

    subject = BARE_SUBJECT_HEAD_RE.match(line)
    if subject:
        name = subject.group("name")
        normalized = clean_name(name)
        # Do not promote "histoire lit." / French continuations.
        if (len(normalized) >= 8 and is_valid_name(normalized)
                and SANSKRIT_HEAD_DIACRITIC_RE.search(normalized)
                and not re.search(r"[éèêëàâîïôöùûüç]", name, re.I)):
            return name

    damaged = MALFORMED_SUB_ENTRY_RE.match(line)
    if damaged and POS_AFTER_ETYMOLOGY_RE.match(line[damaged.end():]):
        candidate = damaged.group("name")
        if is_valid_name(clean_name(candidate)):
            return candidate
    for pattern in (SUB_ENTRY_SQUARE_BRACKET, SUB_ENTRY_PIPE_BRACKET):
        match = pattern.match(line)
        if not match:
            continue
        name = match.group(1)
        if not is_valid_name(clean_name(name)):
            return None
        if pattern is SUB_ENTRY_SQUARE_BRACKET:
            end = line.find("]", match.end())
        else:
            end = line.find("|", match.end() - 1)
        if end < 0 or end - match.end() > 60:
            return None
        tail = line[end + 1:]
        if POS_AFTER_ETYMOLOGY_RE.match(tail):
            return name
        # OCR may wrap the grammatical marker to the next line.
        if not tail.strip() and POS_AFTER_ETYMOLOGY_RE.match(next_line):
            return name
        # Some glossed expressions use a quoted translation instead of POS.
        if (pattern is SUB_ENTRY_SQUARE_BRACKET
                and line[match.end():].lstrip().startswith(('"', '“', '«'))
                and len(name) >= 5
                and not re.search(r"[éèêëàâîïôöùûüç]", name, re.I)):
            return name
    return None


def is_sub_entry_line(line, next_line=""):
    return sub_entry_match(line, next_line) is not None


def get_sub_entry_name(line, next_line=""):
    return sub_entry_match(line, next_line)


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


def append_continuation(parts, line):
    """Join words hyphenated across OCR lines; retain internal hyphens."""
    if not parts:
        return
    previous = parts[-1]
    if re.search(r"[^\W\d_]-$", previous) and line and line[0].islower():
        parts[-1] = previous[:-1] + line
    else:
        parts[-1] = previous + " " + line


def clean_definition_text(text):
    """Clean up HTML, slash artifacts, and whitespace in definition text."""
    text = strip_html(text)
    text = clean_slash_artifacts(text)
    # Replace multiple spaces with single space
    text = re.sub(r' +', ' ', text)
    # Remove leading/trailing whitespace
    text = text.strip()
    return text


def normalize_ocr(text):
    """NFC normalization and known IAST OCR substitutions."""
    return unicodedata.normalize("NFC", text).translate(IAST_OCR_FIXES)


def normalize_bengali_head_line(line):
    """Recognize Bengali OCR headwords, without trusting their spelling.

    A Bengali-to-Devanagari codepoint offset recovers the headword boundary,
    but does not prove the spelling itself was correctly recognized by OCR.
    Such entries retain an empty 'sanskrit' field.
    """
    match = BENGALI_HEAD_RE.match(line)
    if not match or "ৎ" in match.group("word"):
        return line, False
    converted = "".join(chr(ord(ch) - 0x80) for ch in match.group("word"))
    return line[:match.start("word")] + converted + line[match.end("word"):], True


def clean_name(name):
    """Normalize IAST while retaining Sanskrit-specific diacritics."""
    name = normalize_ocr(strip_html(name))
    decomposed = unicodedata.normalize("NFD", name)
    result = []
    last_base = ""
    for character in decomposed:
        if unicodedata.combining(character):
            # Vedic accents do not distinguish our normalized headword names.
            if character in "\u0300\u0301" and last_base.lower() in "aeiou":
                continue
        else:
            last_base = character
        result.append(character)
    name = unicodedata.normalize("NFC", "".join(result))
    name = re.sub(r"[0-9₀-₉\x00-\x1f\x7f]", "", name)
    return name.strip().lower()


def flatten_name(name):
    """Lowercase ASCII search form, not a unique dictionary identifier."""
    text = "".join(NON_DECOMPOSABLE_LETTERS.get(c, c) for c in name)
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = text.encode("ascii", "ignore").decode("ascii").lower()
    return re.sub(r"[^a-z]", "", text)


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
    # Reject punctuation/noise and accidental fragments of French prose.
    return len(name) <= 50 and bool(IAST_HEADWORD_RE.fullmatch(name)) and any(
        character.isalpha() for character in name
    )


def has_numbered_headword(definition_text):
    """Only a numbered headword at the start counts, not subscripts in glosses."""
    return bool(re.match(
        rf"^\s*{re.escape(ROOT_SYMBOL)}?\s*"
        rf"[{IAST_CHARS}]*[{SUBSCRIPT_DIGITS}]+(?=\s|$)",
        definition_text,
    ))


def headword_subscript_number(text):
    """Read a numeric subscript from the *leading headword*, not a gloss."""
    match = re.match(
        rf"^\s*{re.escape(ROOT_SYMBOL)}?\s*"
        rf"[{IAST_CHARS}]+?([{SUBSCRIPT_DIGITS}]+)(?=\s|$)",
        text,
    )
    if not match:
        return None
    digits = match.group(1).translate(str.maketrans(SUBSCRIPT_DIGITS, "0123456789"))
    return int(digits)


def has_consecutive_headword_numbers(first, second):
    first_number = headword_subscript_number(first)
    second_number = headword_subscript_number(second)
    return (first_number is not None and second_number is not None
            and second_number == first_number + 1)


def is_latin_subentry_same_lemma(entry, name, definition_text):
    """Allow the next numbered sense, including after a damaged-script header."""
    if entry is None or clean_name(name) != entry["name"]:
        return False
    return any(
        has_consecutive_headword_numbers(d["definition"], definition_text)
        for d in entry["definitions"]
    )


def prefer_ocr_name(entry, incoming_name):
    """When the same Devanagari has variant OCR IAST, favor more diacritics.

    Only adjust the name when its ASCII search form is identical; never
    arbitrarily choose between unrelated romanizations.
    """
    candidate = clean_name(incoming_name)
    existing = entry["name"]
    if (candidate != existing
            and flatten_name(candidate) == flatten_name(existing)
            and sum(ord(c) > 127 for c in candidate)
            > sum(ord(c) > 127 for c in existing)):
        entry["name"] = candidate
        entry["flat"] = flatten_name(candidate)


def should_group_with_current_entry(
    current_entry, sanskrit_word, name, current_raw_definitions=()
):
    """Match reliable Devanagari first, then numbered or IAST-only senses.

    Different explicit Devanagari spellings are always kept distinct.
    If OCR omitted the script for the next numbered sense, a consecutive
    subscript and matching IAST can attach it to the preceding entry.
    """
    if current_entry is None:
        return False
    existing_sanskrit = current_entry["sanskrit"]
    candidate_name = clean_name(name)
    if existing_sanskrit and sanskrit_word:
        return (
            existing_sanskrit == sanskrit_word
            and current_entry["flat"] == flatten_name(candidate_name)
        )
    if existing_sanskrit or sanskrit_word:
        return False
    # Both spellings absent: independently recognized identical normalized
    # IAST subentries belong together, whether numbered or not.
    return candidate_name == current_entry["name"]



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
        text = normalize_ocr(file.read())

        # Track matches
        extracted_entries = []
        lines = text.splitlines()
        current_entry = None
        current_raw_definitions = []  # List of raw definition strings
        pending_sanskrit = None  # Sanskrit word waiting for IAST name on next line
        pending_root_prefix = False  # Whether there was a √ before pending Sanskrit
        skipping_annotation = False  # Continuation of a hyphenated grammar note

        for line_index, line in enumerate(lines):
            if line == '':
                continue

            line = clean_slash_artifacts(line.strip())
            # Isolated page folios such as "1(" and ")2" are OCR noise,
            # not definition content. Do not discard numbered lexical forms.
            if re.fullmatch(r"(?:[0-9]{1,3}\(|\)[0-9]{1,3})", line):
                continue
            # OCR sometimes inserts a digit immediately after the root sign,
            # e.g. "√2 dhvr v." for a genuine standalone root.
            line = re.sub(r"^√\s*[0-9](?=\s+[A-Za-z])", "√", line)
            line, bengali_head = normalize_bengali_head_line(line)
            # An OCR ASCII colon between Devanagari letters represents visarga.
            line = re.sub(r"(?<=[\u0900-\u097F]):(?=[\u0900-\u097F])", "ः", line)
            if line == '':
                continue

            # Only a Devanagari headword at the *beginning* of a line
            # counts as a new entry. Devanagari inside prose is not a header.
            deva_match = DEVANAGARI_HEAD_RE.match(line)
            sanskrit_word = (
                deva_match.group("deva")
                if deva_match and not bengali_head and " " not in deva_match.group("deva")
                else "" if deva_match else None
            )
            sanskrit_word_index = deva_match.start("deva") if deva_match else None
            sanskrit_word_index_end = deva_match.end("deva") if deva_match else None

            headword = line_headword(line, sanskrit_word_index_end)
            if is_hyphen_annotation(headword):
                skipping_annotation = True
                pending_sanskrit = None
                pending_root_prefix = False
                continue

            # Case 1: We have a pending Sanskrit from previous line, this line should have the IAST name
            if pending_sanskrit is not None:
                skipping_annotation = False
                line_stripped = line.strip()
                if line_stripped:
                    words_in_line = line_stripped.split()
                    name = words_in_line[0] if words_in_line else ''
                    
                    # A bare one-letter OCR page marker has no definition.
                    if len(words_in_line) == 1 and len(clean_name(name)) <= 1:
                        pending_sanskrit = None
                        pending_root_prefix = False
                        skipping_annotation = True
                        continue
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
                        if should_group_with_current_entry(
                            current_entry, pending_sanskrit, name,
                            current_raw_definitions
                        ):
                            prefer_ocr_name(current_entry, name)
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
                                "flat": flatten_name(cleaned_name),
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

                words_after_sanskrit = line_after_sanskrit.split()
                name = words_after_sanskrit[0]
                # Ignore a stray one-letter glyph before a clear IAST headword.
                if (len(name) == 1 and len(words_after_sanskrit) >= 3
                        and len(words_after_sanskrit[1]) >= 3
                        and IAST_TOKEN.fullmatch(words_after_sanskrit[1])
                        and words_after_sanskrit[2][0] in "[|"):
                    name = words_after_sanskrit[1]
                    line_after_sanskrit = line_after_sanskrit.split(None, 1)[1]
                
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
                if should_group_with_current_entry(
                    current_entry, sanskrit_word, name, current_raw_definitions
                ):
                    prefer_ocr_name(current_entry, name)
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
                        "flat": flatten_name(cleaned_name),
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
                    "flat": flatten_name(cleaned_name),
                    "definitions": [],
                }
                current_raw_definitions = [definition_text]

            # Case 3: No Sanskrit, check if it's a sub-entry or continuation
            elif current_entry and line.strip() != '' and not re.search(r'^\d+$', line):
                line_stripped = line.strip()
                following_line = (
                    lines[line_index + 1].strip()
                    if line_index + 1 < len(lines) else ""
                )
                if skipping_annotation and not is_sub_entry_line(line_stripped, following_line):
                    continue
                skipping_annotation = False
                is_new_sub_entry = False
                
                # Strip a single corrupted script marker only when followed by
                # a recognized headword with a grammatical/etymology cue.
                foreign = FOREIGN_OCR_LEADER_RE.match(line_stripped)
                if foreign and is_sub_entry_line(foreign.group("rest"), following_line):
                    line_stripped = foreign.group("rest")

                # Check if this line starts a independently recognized Latin subentry
                if is_sub_entry_line(line_stripped, following_line):
                    sub_entry_name = get_sub_entry_name(line_stripped, following_line)
                    cleaned_name = clean_name(sub_entry_name)
                    
                    # Only create sub-entry if name is valid
                    if is_valid_name(cleaned_name):
                        is_new_sub_entry = True
                        # The numbered next sense can have no reliable script,
                        # even though the preceding sense had Devanagari.
                        next_number = headword_subscript_number(line_stripped)
                        previous_number = (
                            headword_subscript_number(current_raw_definitions[-1])
                            if current_raw_definitions else None
                        )
                        merge_next_sense = (
                            cleaned_name == current_entry["name"]
                            and next_number is not None
                            and previous_number is not None
                            and next_number == previous_number + 1
                        )
                        # IAST-only headwords can also group without numbers,
                        # but only once independently recognized by grammar.
                        merge_iast_only = (
                            not current_entry["sanskrit"]
                            and cleaned_name == current_entry["name"]
                        )
                        if merge_next_sense or merge_iast_only:
                            current_raw_definitions.append(line_stripped)
                        else:
                            if current_raw_definitions:
                                for raw_def in current_raw_definitions:
                                    current_entry['definitions'].append(
                                        create_definition_object(raw_def)
                                    )
                                extracted_entries.append(current_entry)
                            current_entry = {
                                "sanskrit": "",
                                "name": cleaned_name,
                                "flat": flatten_name(cleaned_name),
                                "definitions": [],
                            }
                            current_raw_definitions = [line_stripped]
                
                if not is_new_sub_entry:
                    # Append to the last raw definition
                    if current_raw_definitions:
                        append_continuation(current_raw_definitions, line_stripped)

        # Add any remaining entry
        if current_entry is not None and current_raw_definitions:
            for raw_def in current_raw_definitions:
                if raw_def.strip():
                    current_entry['definitions'].append(create_definition_object(raw_def))
            extracted_entries.append(current_entry)

    return extracted_entries


def merge_entries_with_same_name(entries):
    """Merge independently detected headwords conservatively.

    Priority 1: same nonempty Devanagari and compatible Latin romanization.
    Priority 2: same IAST with consecutive numbered senses when script is
    missing on one side.
    Priority 3: same normalized IAST when both lack Devanagari.
    Different explicit Sanskrit spellings never merge.
    """
    merged = []
    devanagari_index = {}
    iast_without_devanagari = {}

    for entry in entries:
        sanskrit = entry["sanskrit"]
        name = clean_name(entry["name"])
        definitions = entry["definitions"]
        if sanskrit:
            index = devanagari_index.get((sanskrit, flatten_name(name)))
        else:
            index = iast_without_devanagari.get(name)
            if index is None and definitions:
                first_definition = definitions[0]["definition"]
                for j in range(len(merged) - 1, -1, -1):
                    other = merged[j]
                    if other["name"] != name or not other["definitions"]:
                        continue
                    if any(has_consecutive_headword_numbers(
                            d["definition"], first_definition)
                           for d in other["definitions"]):
                        index = j
                        break

        if index is None:
            index = len(merged)
            merged.append({
                "sanskrit": sanskrit,
                "name": name,
                "flat": flatten_name(name),
                "definitions": list(definitions),
            })
            if sanskrit:
                devanagari_index[(sanskrit, flatten_name(name))] = index
            else:
                iast_without_devanagari[name] = index
        else:
            merged[index]["definitions"].extend(definitions)
            if sanskrit:
                prefer_ocr_name(merged[index], name)
            # If a numbered Latin-only definition has an earlier Devanagari
            # sense, retain the reliable spelling from that sense.

    return merged


def main():
    parser = argparse.ArgumentParser(description="Extract Sanskrit dictionary entries from OCR text")
    parser.add_argument("input", nargs="?", default="extracted_dictionary_micro1.txt")
    parser.add_argument("output", nargs="?", default="dictionary_micro1.json")
    args = parser.parse_args()

    extracted = extract_verbs_and_terms_from_text_file(args.input)
    entries = merge_entries_with_same_name(extracted)
    with open(args.output, "w", encoding="utf-8") as json_file:
        json.dump(entries, json_file, ensure_ascii=False, indent=4)
    definitions = sum(len(entry["definitions"]) for entry in entries)
    print(f"Wrote {len(entries)} entries and {definitions} definitions to {args.output}")


if __name__ == "__main__":
    main()
