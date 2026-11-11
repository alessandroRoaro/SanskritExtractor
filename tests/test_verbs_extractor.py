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

    def test_wrapped_pos_and_quoted_subentries(self):
        entries = self.parse(
            "धारा dhārā f. eau\n"
            "dhārāgṛha |gṛha|\n"
            "n. salle de bains\n"
            'namaste ["je te salue"] salutations\n'
        )
        self.assertEqual(
            [entry["name"] for entry in entries],
            ["dhārā", "dhārāgṛha", "namaste"],
        )

    def test_bengali_glyphs_at_start_are_mapped_to_devanagari(self):
        entries = self.parse(
            "धृतिमत dhṛtimat |mat| a. ferme\n"
            "√ ধৃষ্ dhṛṣ v. [5] oser\n"
            "ধৃষ্ট dhṛṣṭa a. hardi\n"
        )
        self.assertEqual([e["name"] for e in entries],
                         ["dhṛtimat", "dhṛṣ", "dhṛṣṭa"])
        self.assertEqual(entries[1]["sanskrit"], "")  # OCR Bengali was uncertain
        self.assertTrue(entries[1]["definitions"][0]["isRootVerb"])

    def test_ascii_visarga_in_devanagari_headword(self):
        entries = self.parse(
            "निःक्षत्र niḥkṣatra a. sans caste\n"
            "नि:शङ्क niḥśaṅka [nis-śaṅkā] a. sans peur\n"
            "नि:शब्द niḥśabda [nis-śabda] a. silencieux\n"
        )
        self.assertEqual([e["name"] for e in entries],
                         ["niḥkṣatra", "niḥśaṅka", "niḥśabda"])
        self.assertEqual(entries[1]["sanskrit"], "निःशङ्क")

    def test_broken_bracket_does_not_swallow_headword(self):
        entries = self.parse(
            "धीर dhīra a. courageux\n"
            "dhīralalita [lalita] m. héros\n"
            "dhīraśānta [śānta| m. héros paisible\n"
        )
        self.assertEqual([e["name"] for e in entries],
                         ["dhīra", "dhīralalita", "dhīraśānta"])

    def test_dehyphenates_wrapped_words_not_compounds(self):
        entries = self.parse(
            "धार् dhār v. [1] rete-\n"
            "nir, entrete-\n"
            "nir l'enfant Duryodhana-Suyodhana\n"
        )
        definition = entries[0]["definitions"][0]["definition"]
        self.assertIn("retenir", definition)
        self.assertIn("entretenir", definition)
        self.assertIn("Duryodhana-Suyodhana", definition)

    def test_glossed_french_prose_is_not_a_headword(self):
        entries = self.parse(
            "निरयन niráyana n. astr. zodiaque\n"
            'sidéral ["sans mouvement"], lié aux constellations;\n'
            "opp. sāyana.\n"
            "निरर्थ nirartha a. vain\n"
        )
        self.assertEqual([e["name"] for e in entries], ["nirayana", "nirartha"])
        self.assertIn("sidéral", entries[0]["definitions"][0]["definition"])

    def test_stray_letter_before_iast_and_spaced_damaged_devanagari(self):
        entries = self.parse(
            "निर्व्याज nirvyāja a. loyal\n"
            "निर्व्यं a nirvyūḍha [pp. nirvyūh] a. fini\n"
            "निर्द्धः ख nirduḥkha [nis-duḥkha] a. sans douleur\n"
        )
        self.assertEqual([e["name"] for e in entries],
                         ["nirvyāja", "nirvyūḍha", "nirduḥkha"])
        self.assertEqual(entries[2]["sanskrit"], "")

    def test_bare_page_letters_are_ignored(self):
        entries = self.parse(
            "न\nn\nन na part. non\n"
            "प\np\nĮ5\nЧ pa nota\n"
            "पद pada m. pied\n"
        )
        self.assertEqual([e["name"] for e in entries], ["na", "pada"])

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

    def test_nash_and_nas_group_by_devanagari_not_flat(self):
        entries = self.parse(
            "√ नश् nas₁ v. [4] pr. (nasyati) périr\n"
            "नश् naś₂ [act. naś₂] ifc. a. lié à la destruction\n"
            "नस् nas₁ pron. nous\n"
            "नस् nas₂ f. nez\n"
        )
        self.assertEqual(len(entries), 2)
        self.assertEqual(
            [(e["name"], e["sanskrit"], len(e["definitions"])) for e in entries],
            [("naś", "नश्", 2), ("nas", "नस्", 2)],
        )
        self.assertEqual([e["flat"] for e in entries], ["nas", "nas"])
        self.assertTrue(entries[0]["definitions"][0]["isRootVerb"])

    def test_same_devanagari_has_priority_over_ocr_iast_difference(self):
        entries = self.parse(
            "नद् nad₁ v. résonner\n"
            "नद् nád₂ m. son\n"
        )
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["sanskrit"], "नद्")
        self.assertEqual(len(entries[0]["definitions"]), 2)

    def test_repeated_corrupt_devanagari_does_not_merge_distinct_iast(self):
        entries = self.parse(
            "नाक nāka m. ciel\n"
            "नाक nāku n. fourmilière\n"
            "निक्त nákta n. nuit\n"
            "निक्त niktá a. purifié\n"
            "निग्रह nigrah v. [9] retenir\n"
            "निग्रह nigraha m. restriction\n"
        )
        self.assertEqual(
            [e["name"] for e in entries],
            ["nāka", "nāku", "nakta", "nikta", "nigrah", "nigraha"],
        )
        self.assertTrue(all(len(e["definitions"]) == 1 for e in entries))

    def test_no_devanagari_numbered_identical_iast_group(self):
        entries = self.parse(
            "धर्म dharma m. loi\n"
            "nāyaka₁ [nāya] m. chef\n"
            "नर nara m. homme\n"
            "nāyaka₂ [nāya] m. héros\n"
        )
        matching = [e for e in entries if e["name"] == "nāyaka"]
        self.assertEqual(len(matching), 1)
        self.assertEqual(matching[0]["sanskrit"], "")
        self.assertEqual(len(matching[0]["definitions"]), 2)

    def test_no_devanagari_without_subscripts_can_group(self):
        entries = self.parse(
            "धर्म dharma m. loi\n"
            "nāyaka [nāya] m. chef\n"
            "नर nara m. homme\n"
            "nāyaka [nāya] m. héros\n"
        )
        self.assertEqual(sum(e["name"] == "nāyaka" for e in entries), 1)

    def test_same_flat_without_devanagari_does_not_group_different_iast(self):
        entries = self.parse(
            "धर्म dharma m. loi\n"
            "nas₁ [na] m. nez\n"
            "नर nara m. homme\n"
            "naś₂ [naś] m. destruction\n"
        )
        matching = [e for e in entries if e["flat"] == "nas"]
        self.assertEqual([e["name"] for e in matching], ["nas", "naś"])

    def test_no_devanagari_unsubscripted_can_merge_with_numbered(self):
        entries = extractor.merge_entries_with_same_name([
            {"sanskrit": "", "name": "nāya", "flat": "naya",
             "definitions": [{"definition": "nāya m. guide",
                              "isVerb": False, "isRootVerb": False}]},
            {"sanskrit": "", "name": "nāya", "flat": "naya",
             "definitions": [{"definition": "nāya₂ m. conduite",
                              "isVerb": False, "isRootVerb": False}]},
        ])
        self.assertEqual(len(entries), 1)

    def test_bare_noun_and_adjective_headwords(self):
        entries = self.parse(
            "धीर dhīra a. stable\n"
            "dhrupadākyanṛtya n. la danse dhrupada\n"
            "trināciketa m. phil. rituel du feu\n"
            "nikaṣāyamāṇa a. m. n. qui définit la norme\n"
            "nayanavişayībhāva m. le fait d'être en vue\n"
            "नर nara m. homme\n"
        )
        self.assertEqual(
            [entry["name"] for entry in entries],
            ["dhīra", "dhrupadākyanṛtya", "trināciketa",
             "nikaṣāyamāṇa", "nayanaviṣayībhāva", "nara"],
        )

    def test_number_after_root_symbol_is_ocr_noise(self):
        entries = self.parse(
            "ध्वरा dhvarā f. courbure\n"
            "√2 dhvr v. [1] pr. (dhvárati) se courber\n"
            "ध्वस् dhvas v. tomber\n"
        )
        root = [entry for entry in entries if entry["name"] == "dhvr"]
        self.assertEqual(len(root), 1)
        self.assertTrue(root[0]["definitions"][0]["isRootVerb"])

    def test_romanian_ocr_diacritics_are_normalized(self):
        self.assertEqual(extractor.clean_name("nikațe"), "nikaṭe")
        self.assertEqual(extractor.clean_name("naștahavis"), "naṣtahavis")

    def test_bare_subject_labels_can_start_sanskrit_compounds(self):
        entries = self.parse(
            "नाम nāma n. nom.\n"
            "nāmadhātu [dhātu] m. gram. verbe dénominatif.\n"
            "nāmadhātuprakriyā gram. usage d'un verbe\n"
            "dénominatif.\n"
            "nāmadheya [dheya] n. appellation.\n"
            "निचृत् nicṛt₁ [ni-cṛt] v. [6] insérer.\n"
            "निचृत् nicrt₂ [act. nicrt₁] f. gram. mètre défectif.\n"
            "nicrdgāyatrī lit. adaptation de la gāyatrī ne res-\n"
            "pectant pas son mètre.\n"
        )
        names = [e["name"] for e in entries]
        self.assertEqual(names, [
            "nāma", "nāmadhātu", "nāmadhātuprakriyā", "nāmadheya",
            "nicṛt", "nicrdgāyatrī",
        ])
        self.assertEqual(len(entries[4]["definitions"]), 2)
        self.assertEqual(
            entries[-1]["definitions"][0]["definition"],
            "nicrdgāyatrī lit. adaptation de la gāyatrī ne respectant pas son mètre.",
        )
        self.assertNotIn("nāmadhātuprakriyā",
                         entries[0]["definitions"][0]["definition"])

    def test_variant_dhuta_is_not_separate_and_naksatra_prose_does_not_split(self):
        entries = self.parse(
            "धूत dhuta var. dhūta [pp. dhū₁] a. secoué.\n"
            "धूत dhūtá var. dhuta |pp. dhū₁| a. agité.\n"
            "নিধ্ব nákṣatra [instr. nakṣ] n. étoile.\n"
            "nakṣatra désigne une division de l'écliptique.\n"
            "नक्ष nakṣ v. atteindre.\n"
        )
        names = [e["name"] for e in entries]
        self.assertNotIn("dhuta", names)
        self.assertEqual(len([e for e in entries if e["name"] == "dhūta"]), 1)
        self.assertEqual(len([e for e in entries if e["name"] == "nakṣatra"]), 1)
        self.assertIn("nakṣatra désigne",
                      next(e for e in entries if e["name"] == "nakṣatra")
                      ["definitions"][0]["definition"])

    def test_subject_label_in_french_prose_is_not_a_headword(self):
        entries = self.parse(
            "निकर nikara m. abondance.\n"
            "consequent lit. un trésor dans la littérature.\n"
            "grammaticalement gram. explication de l'exemple.\n"
            "नर nara m. homme.\n"
        )
        self.assertEqual([e["name"] for e in entries], ["nikara", "nara"])

    def test_bare_adverb_is_an_independent_entry(self):
        entries = self.parse(
            "धीर dhīra₁ [dhā₁] a. m. n. f. brave\n"
            "dhīram adv. tranquillement.\n"
            "dhīratara |-tara| a. m. n. f. ferme\n"
        )
        self.assertEqual([e["name"] for e in entries],
                         ["dhīra", "dhīram", "dhīratara"])
        self.assertEqual(entries[1]["definitions"][0]["definition"],
                         "dhīram adv. tranquillement.")

    def test_damaged_foreign_script_marker_creates_second_dhu_definition(self):
        entries = self.parse(
            "√ धू dhū₁ v. [5] secouer, agiter\n"
            "몇 dhū₂ [act. dhū₁] ifc. f. fait de secouer.\n"
            "धूत dhūta a. secoué\n"
        )
        dhu = [e for e in entries if e["name"] == "dhū"]
        self.assertEqual(len(dhu), 1)
        self.assertEqual(len(dhu[0]["definitions"]), 2)
        self.assertEqual(dhu[0]["definitions"][1]["definition"],
                         "dhū₂ [act. dhū₁] ifc. f. fait de secouer.")
        self.assertTrue(dhu[0]["definitions"][0]["isRootVerb"])
        self.assertFalse(dhu[0]["definitions"][1]["isRootVerb"])

    def test_iast_only_independent_unnumbered_headwords_can_group(self):
        entries = self.parse(
            "धर्म dharma m. loi\n"
            "nāyaka [nāya] m. guide\n"
            "नर nara m. homme\n"
            "nāyaka [nāya] m. héros\n"
        )
        matching = [e for e in entries if e["name"] == "nāyaka"]
        self.assertEqual(len(matching), 1)
        self.assertEqual(len(matching[0]["definitions"]), 2)

    def test_different_devanagari_remain_separate_even_for_consecutive_iast(self):
        entries = self.parse(
            "नश् nas₁ v. périr\n"
            "नस् nas₂ m. nez\n"
        )
        self.assertEqual(len(entries), 2)

    def test_french_prose_does_not_look_like_bare_adverb(self):
        entries = self.parse(
            "निकर nikara m. abondance\n"
            "conséquent | trésor, grand ensemble\n"
            "sans cesse adv. de manière continue\n"
            "नर nara m. homme\n"
        )
        self.assertEqual([e["name"] for e in entries], ["nikara", "nara"])

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
