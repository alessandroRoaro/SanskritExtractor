"""Regression tests for the OCR dictionary parser.

Run from the repository root:
    python -m unittest discover -s tests
"""

import tempfile
import unittest
from pathlib import Path

import verbsExtractor as extractor


class DictionaryParserTests(unittest.TestCase):
    def parse(self, text):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "input.txt"
            path.write_text(text, encoding="utf-8")
            entries = extractor.extract_verbs_and_terms_from_text_file(path)
            return extractor.merge_entries_with_same_name(entries)

    def test_latin_subentries_are_separate_and_have_no_inherited_sanskrit(self):
        entries = self.parse(
            "धिक dhik ind. malheur\n"
            "dhikkāra [kāra] m. reproche\n"
            "dhikpralāpa |pralāpa| m. paroles.\n"
        )
        self.assertEqual([entry["name"] for entry in entries],
                         ["dhik", "dhikkāra", "dhikpralāpa"])
        self.assertEqual([entry["sanskrit"] for entry in entries],
                         ["धिक", "", ""])

    def test_numbered_roots_group_into_definitions(self):
        entries = self.parse(
            "√ धाव् dhāv₁ v. [1] courir\n"
            "√ धाव् dhāv₂ v. [1] laver\n"
        )
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["name"], "dhāv")
        self.assertEqual(len(entries[0]["definitions"]), 2)
        self.assertTrue(all(definition["isRootVerb"]
                            for definition in entries[0]["definitions"]))

    def test_iast_and_flat_normalization(self):
        self.assertEqual(extractor.clean_name("DHIŞAṆA₂"), "dhiṣaṇa")
        self.assertEqual(extractor.flatten_name("dhṛtarāṣṭra"), "dhrtarastra")
        self.assertEqual(extractor.flatten_name("łoka"), "loka")
        self.assertEqual(extractor.flatten_name("dhāv₁"), "dhav")

    def test_prose_and_morphological_notes_do_not_become_headwords(self):
        entries = self.parse(
            "धाय dhāya a. cadeau\n"
            "-ṇa a. gram.\n"
            "pli [mots] apparaissent en français dans le texte\n"
            "नर nara m. homme\n"
        )
        self.assertEqual([entry["name"] for entry in entries], ["dhāya", "nara"])

    def test_devanagari_inside_prose_does_not_begin_an_entry(self):
        entries = self.parse(
            "धर्म dharma m. loi\n"
            "quelque chose धर्म mot\n"
        )
        self.assertEqual(len(entries), 1)

    def test_devanagari_with_iast_on_next_line(self):
        entries = self.parse("धाय\ndhāya a. qui donne\n")
        self.assertEqual([(entry["sanskrit"], entry["name"]) for entry in entries],
                         [("धाय", "dhāya")])


if __name__ == "__main__":
    unittest.main()
