"""Integration checks against the repository's actual OCR extraction input."""

import unittest
from pathlib import Path

from verbsExtractor import (
    extract_verbs_and_terms_from_text_file,
    merge_entries_with_same_name,
)

ROOT = Path(__file__).resolve().parents[1]


class FullDictionaryIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = ROOT / "extracted_dictionary_micro1.txt"
        cls.entries = merge_entries_with_same_name(
            extract_verbs_and_terms_from_text_file(path)
        )
        cls.names = {entry["name"] for entry in cls.entries}

    def test_known_missed_headwords_are_recovered(self):
        # All present in the OCR source but previously lost in JSON.
        for name in (
            "dhīraśānta", "dhṛṣ", "dhṛṣu", "dhṛṣṭa",
            "niḥśaṅka", "niḥśabda", "niḥśeṣa", "niḥśvasya",
            "niḥsaṃjña", "nirduḥkha", "nirvyūḍha",
        ):
            with self.subTest(name=name):
                self.assertIn(name, self.names)

    def test_known_spurious_ocr_headwords_are_absent(self):
        for name in ("a", "n", "p", "sideral", "gisme", "métaphorique"):
            with self.subTest(name=name):
                self.assertNotIn(name, self.names)

    def test_no_regression_in_overall_coverage(self):
        entries = len(self.entries)
        definitions = sum(len(e["definitions"]) for e in self.entries)
        print(f"\nOCR benchmark: {entries} entries; {definitions} definitions")
        # The supplied pre-fix output had 2,148 / 2,186. Some false
        # positives are intentionally removed; recovered names must
        # compensate for them rather than reducing total coverage.
        self.assertGreaterEqual(entries, 2148)
        self.assertGreaterEqual(definitions, 2186)

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
