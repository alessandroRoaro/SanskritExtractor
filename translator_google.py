import json
import time
import os
import html
from pathlib import Path
from google.cloud import translate_v2 as translate


class GoogleTranslationManager:
    def __init__(self, input_file='dictionary.json', source_lang='fr', target_lang='en', credentials_path=None):
        """
        Initialize the Google Cloud Translation Manager.
        
        Args:
            input_file: Path to the input dictionary JSON file
            source_lang: Source language code (default: 'fr' for French)
            target_lang: Target language code (default: 'en' for English)
            credentials_path: Optional path to Google Cloud service account JSON key file
                              If not provided, uses Application Default Credentials
        """
        # Set up Google Cloud credentials if provided
        if credentials_path:
            os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = credentials_path
        
        # Uses v2 API (simple, reliable)
        self.client = translate.Client()
        self.source_lang = source_lang
        self.target_lang = target_lang
        
        self.input_file = Path(input_file)
        self.output_file = self.input_file.with_name(f'dictionary_{target_lang}.json')
        self.progress_file = self.input_file.with_name(f'translation_progress_{target_lang}.json')
        
        self.chars_translated = 0
    
    def estimate_cost(self):
        """
        Estimate the cost of translating the entire dictionary.
        Returns total characters and estimated cost in USD.
        """
        dictionary = self.load_dictionary()
        start_index, _ = self.load_progress()
        
        # Only count entries that haven't been translated yet
        remaining_entries = dictionary[start_index:]
        
        total_chars = 0
        for entry in remaining_entries:
            for def_obj in entry.get('definitions', []):
                total_chars += len(def_obj['definition'])
        
        # Google Cloud Translation API pricing: $20 per 1 million characters
        cost_per_million = 20.0
        estimated_cost = (total_chars / 1_000_000) * cost_per_million
        
        return {
            'total_entries': len(dictionary),
            'remaining_entries': len(remaining_entries),
            'already_translated': start_index,
            'total_characters': total_chars,
            'estimated_cost_usd': estimated_cost,
            'estimated_cost_eur': estimated_cost * 0.92  # Approximate EUR conversion
        }

    def load_dictionary(self):
        """Load the dictionary from the input JSON file."""
        with open(self.input_file, 'r', encoding='utf-8') as f:
            return json.load(f)

    def save_dictionary(self, translated_batch):
        """
        Appends the newly translated batch to the output file incrementally.
        """
        if not self.output_file.exists():
            with open(self.output_file, 'w', encoding='utf-8') as f:
                f.write('[\n')
                for i, entry in enumerate(translated_batch):
                    json.dump(entry, f, ensure_ascii=False, indent=4)
                    if i < len(translated_batch) - 1:
                        f.write(',\n')
                f.write('\n]')
        else:
            with open(self.output_file, 'r+', encoding='utf-8') as f:
                f.seek(0, 2)  # Go to end
                pos = f.tell() - 1
                # Find the last ]
                while pos > 0:
                    f.seek(pos)
                    char = f.read(1)
                    if char == ']':
                        break
                    pos -= 1
                f.seek(pos)
                f.write(',\n')
                for i, entry in enumerate(translated_batch):
                    json.dump(entry, f, ensure_ascii=False, indent=4)
                    if i < len(translated_batch) - 1:
                        f.write(',\n')
                f.write('\n]')

    def load_progress(self):
        """Load translation progress from file."""
        if self.progress_file.exists():
            with open(self.progress_file, 'r') as f:
                progress = json.load(f)
            return progress.get('last_index', 0), progress.get('chars_translated', 0)
        return 0, 0

    def save_progress(self, index, chars):
        """Save translation progress to file."""
        with open(self.progress_file, 'w') as f:
            json.dump({
                'last_index': index,
                'chars_translated': chars,
                'last_update': time.strftime('%Y-%m-%d %H:%M:%S')
            }, f)

    def translate_text(self, text):
        """
        Translates individual text using the Google Cloud Translation API.
        
        Args:
            text: The text to translate
            
        Returns:
            Translated text or None if error occurred
        """
        try:
            result = self.client.translate(
                text,
                source_language=self.source_lang,
                target_language=self.target_lang
            )
            # Decode HTML entities (Google API returns &#39; for ', &quot; for ", etc.)
            return html.unescape(result['translatedText'])
        except Exception as e:
            print(f"Error occurred during translation: {e}")
            return None

    def translate_batch_api(self, texts):
        """
        Translates multiple texts in a single API call (more efficient).
        
        Args:
            texts: List of texts to translate
            
        Returns:
            List of translated texts
        """
        try:
            results = self.client.translate(
                texts,
                source_language=self.source_lang,
                target_language=self.target_lang
            )
            # Decode HTML entities for all results
            return [html.unescape(r['translatedText']) for r in results]
        except Exception as e:
            print(f"Error occurred during batch translation: {e}")
            return None

    def translate_batch(self, entries, use_batch_api=True):
        """
        Translates a batch of dictionary entries.
        
        Each entry has a 'definitions' array with objects containing 'definition', 'isVerb', 'isRootVerb'.
        
        Args:
            entries: List of dictionary entries
            use_batch_api: If True, uses batch API call (more efficient)
            
        Returns:
            Tuple of (translated_entries, limit_reached)
        """
        translated_entries = []
        
        if use_batch_api:
            # Collect all definitions from all entries for batch translation
            all_definitions = []
            definition_map = []  # Track which entry and definition index each text belongs to
            
            for entry_idx, entry in enumerate(entries):
                for def_idx, def_obj in enumerate(entry.get('definitions', [])):
                    all_definitions.append(def_obj['definition'])
                    definition_map.append((entry_idx, def_idx))
            
            total_chars = sum(len(d) for d in all_definitions)
            
            try:
                translated_defs = self.translate_batch_api(all_definitions)
                
                if translated_defs:
                    # Create deep copies of entries
                    translated_entries = [self._deep_copy_entry(entry) for entry in entries]
                    
                    # Map translations back to entries
                    for (entry_idx, def_idx), translated_text in zip(definition_map, translated_defs):
                        translated_entries[entry_idx]['definitions'][def_idx]['definition'] = translated_text
                    
                    self.chars_translated += total_chars
                    
                    # Print summary
                    print(f'  Translated {len(all_definitions)} definitions ({total_chars:,} chars)')
                else:
                    # If batch fails, fall back to individual translations
                    return self._translate_individually(entries)
                    
            except Exception as e:
                print(f"Batch translation error: {e}")
                return self._translate_individually(entries)
        else:
            return self._translate_individually(entries)
        
        return translated_entries, False

    def _deep_copy_entry(self, entry):
        """Create a deep copy of an entry including nested definitions."""
        new_entry = {
            'sanskrit': entry.get('sanskrit', ''),
            'name': entry.get('name', ''),
            'flat': entry.get('flat', ''),
            'definitions': [
                {
                    'definition': def_obj['definition'],
                    'isVerb': def_obj.get('isVerb', False),
                    'isRootVerb': def_obj.get('isRootVerb', False)
                }
                for def_obj in entry.get('definitions', [])
            ]
        }
        return new_entry

    def _translate_individually(self, entries):
        """Fallback method to translate entries one by one."""
        translated_entries = []
        
        for entry in entries:
            new_entry = self._deep_copy_entry(entry)
            
            for def_idx, def_obj in enumerate(new_entry['definitions']):
                definition = def_obj['definition']
                chars_in_def = len(definition)

                try:
                    translated_def = self.translate_text(definition)
                    if translated_def:
                        new_entry['definitions'][def_idx]['definition'] = translated_def
                        self.chars_translated += chars_in_def

                    preview = translated_def[:60] + '...' if translated_def and len(translated_def) > 60 else translated_def
                    print(f'  [{entry["name"]}] {preview}')

                    # Sleep to respect rate limits
                    time.sleep(0.1)

                except Exception as e:
                    print(f"Error processing definition in {entry['name']}: {e}")

            translated_entries.append(new_entry)

        return translated_entries, False

    def run(self):
        """Main method to run the translation process."""
        dictionary = self.load_dictionary()
        start_index, chars_translated = self.load_progress()
        self.chars_translated = chars_translated

        total_entries = len(dictionary)
        batch_size = 50  # Google API can handle larger batches

        print(f"Starting Google Cloud translation from index {start_index}")
        print(f"Total entries: {total_entries:,}")
        print(f"Characters translated so far: {self.chars_translated:,}")
        print(f"Translating from '{self.source_lang}' to '{self.target_lang}'")
        print("-" * 50)

        i = start_index  # Initialize i outside the loop for the finally block
        
        try:
            for i in range(start_index, total_entries, batch_size):
                batch = dictionary[i:i + batch_size]
                print(f"\nProcessing entries {i} to {i + len(batch) - 1} of {total_entries}")

                translated_batch, _ = self.translate_batch(batch)

                if translated_batch:
                    self.save_dictionary(translated_batch)
                    self.save_progress(i + len(translated_batch), self.chars_translated)

                # Progress report
                progress = (i + len(batch)) / total_entries * 100
                print(f"Progress: {progress:.1f}% | Total chars: {self.chars_translated:,}")

                # Small delay between batches
                time.sleep(0.5)

        except KeyboardInterrupt:
            print("\nTranslation interrupted by user. Progress saved.")
        except Exception as e:
            print(f"\nUnexpected error: {e}")
            print("Progress saved.")
        finally:
            self.save_progress(i, self.chars_translated)
            print(f"\nFinal stats: {self.chars_translated:,} characters translated")


def estimate_only(target_lang='en'):
    """
    Only estimate the cost without translating anything.
    """
    print("=" * 60)
    print("COST ESTIMATION (using Application Default Credentials)")
    print("=" * 60)
    
    translator = GoogleTranslationManager(
        input_file='dictionary.json',
        source_lang='fr',
        target_lang=target_lang
    )
    
    estimate = translator.estimate_cost()
    
    print(f"\nTarget language: {target_lang}")
    print(f"Total entries in dictionary: {estimate['total_entries']:,}")
    print(f"Already translated: {estimate['already_translated']:,}")
    print(f"Remaining to translate: {estimate['remaining_entries']:,}")
    print(f"\nTotal characters to translate: {estimate['total_characters']:,}")
    print(f"\nEstimated cost (at $20/million chars):")
    print(f"  USD: ${estimate['estimated_cost_usd']:.2f}")
    print(f"  EUR: ~{estimate['estimated_cost_eur']:.2f}")
    print("\n" + "=" * 60)
    
    return estimate


def test_translation(num_entries=2, target_lang='en'):
    """
    Test the translation on a small number of entries.
    Run this first, then check your billing to verify pricing!
    """
    print(f"=== Testing Google Cloud Translation on {num_entries} entries ===")
    print(">>> Using Application Default Credentials <<<")
    print(">>> After this test, CHECK YOUR BILLING to verify the cost! <<<\n")
    
    translator = GoogleTranslationManager(
        input_file='dictionary.json',
        source_lang='fr',
        target_lang=target_lang
    )
    
    # Load dictionary and take only first few entries
    dictionary = translator.load_dictionary()
    test_entries = dictionary[:num_entries]
    
    # Count characters
    test_chars = sum(len(d['definition']) for e in test_entries for d in e.get('definitions', []))
    print(f"Test will translate {test_chars:,} characters")
    print(f"Expected cost: ${(test_chars / 1_000_000) * 20:.4f} USD\n")
    
    for entry in test_entries:
        print(f"Entry: {entry['name']} ({entry['sanskrit']})")
        print(f"  Definitions: {len(entry['definitions'])}")
    
    print("\n" + "-" * 50)
    input("Press Enter to start test translation (or Ctrl+C to cancel)...")
    print("Starting translation...\n")
    
    translated_entries, _ = translator.translate_batch(test_entries)
    
    print("\n" + "=" * 50)
    print("RESULTS:")
    print("=" * 50)
    
    for original, translated in zip(test_entries, translated_entries):
        print(f"\n{original['name']} ({original['sanskrit']})")
        for i, (orig_def, trans_def) in enumerate(zip(original['definitions'], translated['definitions'])):
            print(f"\n  Definition {i + 1}:")
            print(f"  [FR] {orig_def['definition'][:200]}{'...' if len(orig_def['definition']) > 200 else ''}")
            print(f"  [{target_lang.upper()}] {trans_def['definition'][:200]}{'...' if len(trans_def['definition']) > 200 else ''}")
    
    print(f"\n\nTotal characters translated: {translator.chars_translated:,}")
    print("\n>>> NOW CHECK YOUR GOOGLE CLOUD BILLING to verify the cost! <<<")
    print(">>> Go to: https://console.cloud.google.com/billing <<<")


def main(target_lang='en'):
    """
    Main entry point for full translation.
    Uses Application Default Credentials (run 'gcloud auth application-default login' first)
    """
    print("=" * 60)
    print(f"Google Cloud Translation - French to {target_lang.upper()}")
    print("Using Application Default Credentials")
    print("=" * 60)
    
    translator = GoogleTranslationManager(
        input_file='dictionary.json',
        source_lang='fr',
        target_lang=target_lang
    )
    
    # Show cost estimate first
    estimate = translator.estimate_cost()
    
    print(f"\nCost estimate:")
    print(f"  Characters to translate: {estimate['total_characters']:,}")
    print(f"  Estimated cost: ${estimate['estimated_cost_usd']:.2f} USD / ~{estimate['estimated_cost_eur']:.2f} EUR")
    print(f"  Already translated: {estimate['already_translated']:,} entries")
    print()
    
    confirm = input("Do you want to proceed? (yes/no): ")
    if confirm.lower() != 'yes':
        print("Cancelled.")
        return
    
    translator.run()


if __name__ == "__main__":
    import sys
    
    # Usage:
    #   python translator_google.py estimate [lang]  - Show cost estimate only
    #   python translator_google.py test [lang]      - Test with 2 entries
    #   python translator_google.py run [lang]       - Run full translation
    #
    # Default language is 'it' (Italian). Other options: 'en', 'es'
    
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python translator_google.py estimate [lang]  - Show cost estimate")
        print("  python translator_google.py test [lang]      - Test with 2 entries")
        print("  python translator_google.py run [lang]       - Run full translation")
        print("\nLanguages: it (Italian), en (English), es (Spanish)")
        sys.exit(1)
    
    command = sys.argv[1]
    lang = sys.argv[2] if len(sys.argv) > 2 else 'it'
    
    if command == 'estimate':
        estimate_only(lang)
    elif command == 'test':
        test_translation(num_entries=2, target_lang=lang)
    elif command == 'run':
        main(target_lang=lang)
    else:
        print(f"Unknown command: {command}")
        print("Use: estimate, test, or run")
