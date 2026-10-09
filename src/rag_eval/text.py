from __future__ import annotations

import re


def normalize_whitespace(text: str) -> str:
    """Collapses all contiguous whitespace sequences (spaces, tabs, newlines) into a single space."""
    return " ".join(text.split())


def find_normalized_span(text: str, query: str) -> tuple[int, int] | None:
    """Finds exact character span (start, end) of query within text, normalizing whitespace.

    Matches query words in sequence allowing any whitespace sequence (\\s+, including newlines)
    between them. Returns 0-indexed [start, end) character offsets in original text,
    or None if no match is found.
    """
    clean_query = query.strip()
    if not clean_query or not text:
        return None

    tokens = [re.escape(w) for w in clean_query.split() if w]
    if not tokens:
        return None

    pattern = r"\s+".join(tokens)
    match = re.search(pattern, text)
    if match:
        return match.start(), match.end()
    return None
