def is_value_in_range(
    value: float,
    range_from: float | None,
    range_to: float | None,
) -> bool:
    if range_from is not None and value < range_from:
        return False
    if range_to is not None and value > range_to:
        return False
    return True
