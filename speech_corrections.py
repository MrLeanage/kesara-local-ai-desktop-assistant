"""User-controlled correction dictionary for imperfect offline speech recognition.

Entries are exact phrases, applied case-insensitively with word boundaries.
No fuzzy guessing: the user explicitly decides the replacement.
"""
import re

MAX_CORRECTIONS = 40
MAX_PHRASE_LENGTH = 90

def parse_corrections(text):
    """Parse 'recognized => intended' lines, silently ignore invalid entries."""
    pairs = []
    for line in text.splitlines():
        if '=>' not in line:
            continue
        wrong, right = [item.strip() for item in line.split('=>', 1)]
        if (not wrong or not right or len(wrong) > MAX_PHRASE_LENGTH
                or len(right) > MAX_PHRASE_LENGTH or wrong.casefold() == right.casefold()):
            continue
        if not any(old.casefold() == wrong.casefold() for old, _ in pairs):
            pairs.append((wrong, right))
        if len(pairs) >= MAX_CORRECTIONS:
            break
    return pairs

def format_corrections(pairs):
    return '\n'.join(f'{wrong} => {right}' for wrong, right in pairs)

def apply_corrections(text, pairs):
    """Apply longest exact recognized phrases first; preserve unrelated text."""
    if not text or not pairs:
        return text
    result = text
    for wrong, right in sorted(pairs, key=lambda item: len(item[0]), reverse=True):
        # Avoid matching a phrase in the middle of another word.
        result = re.sub(r'(?<!\w)' + re.escape(wrong) + r'(?!\w)',
                        lambda match: right, result, flags=re.IGNORECASE)
    return result
