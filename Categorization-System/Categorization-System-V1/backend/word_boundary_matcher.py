import re
from functools import lru_cache


@lru_cache(maxsize=512)
def _compiled_pattern(keyword: str) -> re.Pattern:
    escaped = re.escape(keyword)
    return re.compile(rf"\b{escaped}\b", flags=re.IGNORECASE)


def matches_word_boundary(note_lower: str, keyword_lower: str) -> bool:
    """Return True when keyword is found at token boundaries in note text."""
    return _compiled_pattern(keyword_lower).search(note_lower) is not None
