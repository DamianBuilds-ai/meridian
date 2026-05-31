"""
Fuzzy matching utility.

Resolves natural language entity names to actual records.
Combines word overlap scoring with Levenshtein distance fallback.
"""

from Levenshtein import distance as levenshtein_distance


def fuzzy_match(query: str, companies: list[dict], threshold: float = 0.3) -> dict | None:
    """
    Find the best matching company for a query string.

    Scoring:
    1. Word overlap: count matching words between query and company name
    2. Levenshtein fallback: if no word overlap, check edit distance <= 2

    Returns the best match or None if below threshold.
    """
    query_lower = query.lower().strip()
    query_words = set(query_lower.split())

    best_match = None
    best_score = 0.0

    for company in companies:
        name = company.get("name", "")
        name_lower = name.lower()
        name_words = set(name_lower.split())

        # Word overlap score
        if name_words and query_words:
            overlap = len(query_words & name_words)
            score = overlap / max(len(query_words), len(name_words))
        else:
            score = 0.0

        # Exact substring bonus
        if query_lower in name_lower or name_lower in query_lower:
            score = max(score, 0.8)

        # Levenshtein fallback for short names
        if score < threshold and len(query_lower) > 2:
            dist = levenshtein_distance(query_lower, name_lower)
            if dist <= 2:
                score = max(score, 1.0 - (dist / max(len(query_lower), len(name_lower))))

        if score > best_score:
            best_score = score
            best_match = company

    if best_score >= threshold:
        return best_match
    return None


def clean_gym_name(query: str) -> str:
    """Strip common prefixes/suffixes from a gym lookup query."""
    remove_words = {
        "info", "details", "show", "tell", "me", "about", "get",
        "find", "look", "up", "lookup", "search", "gym", "for",
    }
    words = query.strip().split()
    cleaned = [w for w in words if w.lower() not in remove_words]
    return " ".join(cleaned) if cleaned else query
