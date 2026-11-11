"""Integration checks against the repository's actual OCR extraction input."""

import unittest
from pathlib import Path

from verbsExtractor import (
    extract_verbs_and_terms_from_text_file,
    merge_entries_with_same_name,
)

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_ENTRIES = 736
EXPECTED_DEFINITIONS = 756
COUNT_TOLERANCE = 5


class FullDictionaryIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = ROOT / "extracted_dictionary_micro1.txt"
        cls.entries = merge_entries_with_same_name(
            extract_verbs_and_terms_from_text_file(path)
        )
        cls.names = {entry["name"] for entry in cls.entries}

    def test_known_missed_headwords_are_recovered(self):
        # All present in the current, shortened OCR source.
        for name in (
            "dhīraśānta", "dhṛṣ", "dhṛṣu", "dhṛṣṭa",
            "niḥśaṅka", "niḥśabda", "niḥśeṣa", "niḥśvasya",
            "niḥsaṃjña",
        ):
            with self.subTest(name=name):
                self.assertIn(name, self.names)

    def test_known_spurious_ocr_headwords_are_absent(self):
        for name in ("a", "n", "p", "sideral", "gisme", "métaphorique"):
            with self.subTest(name=name):
                self.assertNotIn(name, self.names)

    def test_counts_match_current_ocr_baseline(self):
        """Detect unexpected count changes, not disagreement with old micro1."""
        entries = len(self.entries)
        definitions = sum(len(e["definitions"]) for e in self.entries)
        print(f"\nOCR benchmark: {entries} entries; {definitions} definitions")
        self.assertLessEqual(
            abs(entries - EXPECTED_ENTRIES),
            COUNT_TOLERANCE,
            f"Entry count {entries} differs from baseline {EXPECTED_ENTRIES} "
            f"by more than ±{COUNT_TOLERANCE}",
        )
        self.assertLessEqual(
            abs(definitions - EXPECTED_DEFINITIONS),
            COUNT_TOLERANCE,
            f"Definition count {definitions} differs from baseline "
            f"{EXPECTED_DEFINITIONS} by more than ±{COUNT_TOLERANCE}",
        )

    def test_flat_search_keys_and_definition_schema(self):
        for entry in self.entries:
            with self.subTest(name=entry["name"]):
                self.assertRegex(entry["flat"], r"^[a-z]+$")
                self.assertIsInstance(entry["sanskrit"], str)
                self.assertTrue(entry["definitions"])
                for definition in entry["definitions"]:
                    self.assertIsInstance(definition["definition"], str)
                    self.assertIsInstance(definition["isVerb"], bool)
                    self.assertIsInstance(definition["isRootVerb"], bool)


if __name__ == "__main__":
    unittest.main()
