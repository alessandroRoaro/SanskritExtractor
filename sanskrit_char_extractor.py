def is_sanskrit_char(character):
    # Devanagari script Unicode range: U+0900 to U+097F
    # Additional Devanagari Extended: U+A8E0 to U+A8FF
    devanagari_range = (0x0900, 0x097F)
    devanagari_extended_range = (0xA8E0, 0xA8FF)

    char_code = ord(character)
    return devanagari_range[0] <= char_code <= devanagari_range[1] or \
        devanagari_extended_range[0] <= char_code <= devanagari_extended_range[1]

test = "अल्लीबता"
print(is_sanskrit_char(test[1]))