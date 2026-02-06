import json
import time
import uuid
import os
import requests
from pathlib import Path


class TranslationManager:
    def __init__(self, key, region, input_file='dictionary.json'):
        # Azure Translator API endpoint and required headers
        self.endpoint = "https://api.cognitive.microsofttranslator.com"
        self.path = "/translate"
        self.constructed_url = self.endpoint + self.path
        self.headers = {
            'Ocp-Apim-Subscription-Key': key,
            'Ocp-Apim-Subscription-Region': region,
            'Content-type': 'application/json',
            'X-ClientTraceId': str(uuid.uuid4())
        }
        self.input_file = Path(input_file)
        self.output_file = self.input_file.with_name('dictionary_translated.json')
        self.progress_file = self.input_file.with_name('translation_progress.json')
        self.monthly_char_limit = 2_000_000
        self.chars_translated = 0

    def load_dictionary(self):
        with open(self.input_file, 'r', encoding='utf-8') as f:
            return json.load(f)

    def save_dictionary(self, translated_batch):
        """
        Appends the newly translated batch to the output file incrementally to avoid overwriting the entire dictionary.
        """
        # Determine whether we are appending to an existing file or creating a new one
        if not self.output_file.exists():  # First batch being saved
            with open(self.output_file, 'w', encoding='utf-8') as f:
                f.write('[\n')  # Open the JSON array
                json.dump(translated_batch, f, ensure_ascii=False, indent=4)
                f.write('\n')  # Ensure proper spacing
        else:  # Append to the existing file
            with open(self.output_file, 'r+', encoding='utf-8') as f:
                f.seek(0, 2)  # Move to the end of the file
                f.seek(f.tell() - 2, 0)  # Go back 2 bytes to remove the closing bracket "]\n"
                f.write(',\n')  # Add a comma to separate the batches
                json.dump(translated_batch, f, ensure_ascii=False, indent=4)
                f.write('\n]')  # Close the JSON array

    def load_progress(self):
        if self.progress_file.exists():
            with open(self.progress_file, 'r') as f:
                progress = json.load(f)
            return progress.get('last_index', 0), progress.get('chars_translated', 0)
        return 0, 0

    def save_progress(self, index, chars):
        with open(self.progress_file, 'w') as f:
            json.dump({
                'last_index': index,
                'chars_translated': chars,
                'last_update': time.strftime('%Y-%m-%d %H:%M:%S')
            }, f)

    def translate_text(self, text):
        """Translates individual text using the Azure REST API."""
        params = {
            'api-version': '3.0',
            'from': 'fr',  # Source language
            'to': ['it']  # Target language(s)
        }
        body = [{'text': text}]

        try:
            # Make the REST API call
            response = requests.post(self.constructed_url, params=params, headers=self.headers, json=body)

            if response.status_code == 200:
                translations = response.json()
                return translations[0]['translations'][0]['text']  # Extract the translated text
            else:
                print(f"Translation error: {response.status_code} - {response.text}")
                return None
        except Exception as e:
            print(f"Error occurred during translation: {e}")
            return None

    def translate_batch(self, entries):
        """Translates a batch of dictionary entries."""
        translated_entries = []

        for entry in entries:
            new_entry = entry.copy()
            definition = entry['definition']
            chars_in_def = len(definition)

            # Check if we're approaching the monthly limit
            # if self.chars_translated + chars_in_def > self.monthly_char_limit:
            #     print(f"\nMonthly character limit ({self.monthly_char_limit:,}) approaching!")
            #     print("Please wait for next month's quota or continue with a new key.")
            #     return translated_entries, True  # True indicates limit reached

            try:
                translated_def = self.translate_text(definition)
                if translated_def:
                    new_entry['definition'] = translated_def
                    self.chars_translated += chars_in_def
                translated_entries.append(new_entry)

                print('Translated: ', translated_def)

                # Sleep to respect rate limits
                time.sleep(0.25)  # 4 requests per second

            except Exception as e:
                print(f"Error processing entry {entry['name']}: {e}")
                translated_entries.append(entry)

        return translated_entries, False

    def run(self):
        dictionary = self.load_dictionary()
        start_index, chars_translated = self.load_progress()
        self.chars_translated = chars_translated

        total_entries = len(dictionary)
        batch_size = 10

        print(f"Starting translation from index {start_index}")
        print(f"Characters translated so far: {self.chars_translated:,}")

        try:
            for i in range(start_index, total_entries, batch_size):
                batch = dictionary[i:i + batch_size]
                print(f"\nProcessing entries {i} to {i + len(batch)} of {total_entries}")

                translated_batch, limit_reached = self.translate_batch(batch)

                if translated_batch:
                    dictionary[i:i + len(translated_batch)] = translated_batch
                    self.save_dictionary(translated_batch)
                    self.save_progress(i + len(translated_batch), self.chars_translated)

                if limit_reached:
                    break

                # Progress report
                progress = (i + len(batch)) / total_entries * 100
                chars_remaining = self.monthly_char_limit - self.chars_translated
                print(f"Progress: {progress:.1f}%")
                print(f"Characters remaining in quota: {chars_remaining:,}")

        except KeyboardInterrupt:
            print("\nTranslation interrupted by user. Progress saved.")
        except Exception as e:
            print(f"\nUnexpected error: {e}")
            print("Progress saved.")
        finally:
            self.save_progress(i, self.chars_translated)


def main():
    # Get Azure credentials from environment variables
    key = os.environ.get('AZURE_TRANSLATOR_KEY', '')
    region = os.environ.get('AZURE_TRANSLATOR_REGION', 'italynorth')

    if not key or not region:
        print("Please set AZURE_TRANSLATOR_KEY and AZURE_TRANSLATOR_REGION environment variables")
        return

    translator = TranslationManager(key, region)
    translator.run()


if __name__ == "__main__":
    main()
