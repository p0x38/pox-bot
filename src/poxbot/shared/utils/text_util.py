def crop_word(text: str, needle_word: str, padding: int = 8, emphasis: bool = True):
    start = text.lower().find(needle_word.lower())
    if start == -1:
        return None
    
    needle_len = len(needle_word)
    
    if emphasis:
        low = max(0, start - padding)
        high = min(len(text), start + needle_len + padding)
        
        cropped = text[low:high]
        
        rel_start = start - low
        
        return (
            cropped[:rel_start]
            + "**"
            + cropped[rel_start:rel_start + needle_len]
            + "**"
            + cropped[rel_start + needle_len:]
        )
    else:
        low = max(0, start - padding)
        high = min(len(text), start + needle_len + padding)
        return text[low:high]
