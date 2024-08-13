def reorder_list_outside_in(items: list) -> list:
    return [item for pair in zip(items[:len(items)//2], reversed(items[len(items)//2:])) for item in pair]


def list_has_duplicates(lst: list) -> bool:
    return any(lst.count(item) > 1 for item in lst)
