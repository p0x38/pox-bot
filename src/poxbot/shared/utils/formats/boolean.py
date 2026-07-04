def format_boolean(
    i: bool | None,
    true_text: str = 'Yes',
    false_text: str = 'No',
    missing_text: str = 'None',
):
    if not i:
        return missing_text
    return true_text if i else false_text
