import json


def analyze_dictionary_size():
    with open('dictionary.json', 'r', encoding='utf-8') as f:
        dictionary = json.load(f)

    total_chars = 0
    sample_sizes = []

    # Analyze first 100 entries for average
    for entry in dictionary[:100]:
        chars = len(entry['definition'])
        sample_sizes.append(chars)

    avg_chars = sum(sample_sizes) / len(sample_sizes)
    total_entries = len(dictionary)
    estimated_total = avg_chars * total_entries

    print(f"Sample Statistics:")
    print(f"Average chars per definition: {avg_chars:.1f}")
    print(f"Total entries: {total_entries}")
    print(f"Estimated total chars: {estimated_total:,.0f}")
    print(f"Free tier limit: 500,000 chars")
    print(f"Estimated cost: ${max(0, (estimated_total - 500000) / 1000000 * 20):.2f}")


analyze_dictionary_size()