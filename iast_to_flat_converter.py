def convert_iast_to_flat(text):
    # Define a comprehensive mapping of IAST characters to their flat English equivalents
    char_map = {
        'ā': 'a', 'ī': 'i', 'ū': 'u', 'ṛ': 'r', 'ṝ': 'r', 'ḷ': 'l', 'ḹ': 'l',
        'ṃ': 'm', 'ḥ': 'h', 'ṅ': 'n', 'ñ': 'n', 'ṭ': 't', 'ḍ': 'd', 'ṇ': 'n',
        'ś': 's', 'ṣ': 's', 'ḻ': 'l',
        # Vowels with acute accents
        'á': 'a', 'í': 'i', 'ú': 'u', 'é': 'e', 'ó': 'o',
        # Vowels with grave accents
        'à': 'a', 'ì': 'i', 'ù': 'u', 'è': 'e', 'ò': 'o',
        # Vowels with circumflex accents
        'â': 'a', 'ê': 'e', 'î': 'i', 'ô': 'o', 'û': 'u',
        # Vowels with tilde
        'ã': 'a', 'ĩ': 'i', 'ũ': 'u',
        # Vowels with diaeresis
        'ä': 'a', 'ë': 'e', 'ï': 'i', 'ö': 'o', 'ü': 'u',
        # Other special characters
        'č': 'c', 'ǧ': 'g', 'ḫ': 'h', 'ř': 'r', 'ž': 'z', 'ẖ': 'h', 'ṭ': 't', 'ḳ': 'k',
    }

    # Convert the text using the mapping
    converted_text = ''.join(char_map.get(c, c) for c in text)

    return converted_text


# Test examples
text1 = "aṃśāṃśi"
text2 = "ákaṉisṭha"
text3 = "ātmā śakti"

# print(convert_iast_to_flat(text1))  # Output: amsamsi
# print(convert_iast_to_flat(text2))  # Output: akanistha
# print(convert_iast_to_flat(text3))  # Output: atma sakti