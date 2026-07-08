from collections.abc import Callable, Iterable

from rapidfuzz import process


def fuzzy_search_objects[T](
    query: str,
    choices: Iterable[T],
    key_extrator: Callable[[T], list[str]],
    limit: int = 1,
    score_cutoff: float = 40.0,
) -> list[T]:
    if not query.strip() or not choices:
        return list(choices)[:limit]
    
    string_to_obj_map = {}
    search_strings = []
    
    for obj in choices:
        extracted_keys = key_extrator(obj)
        for key in extracted_keys:
            if key:
                normalized_key = key.lower()
                string_to_obj_map[normalized_key] = obj
                search_strings.append(normalized_key)
    
    results = process.extract(
        query.lower(),
        search_strings,
        limit=limit,
        score_cutoff=score_cutoff,
    )
    
    seen = set()
    matched_objects = []
    for matched_text, _score, _index in results:
        obj = string_to_obj_map[matched_text]
        if id(obj) not in seen:
            seen.add(id(obj))
            matched_objects.append(obj)
    
    return matched_objects
