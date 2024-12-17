from typing import List

from pyjamaz.hashing import blake2b_256_hash


def reorder_list_outside_in(items: list) -> list:
    return [item for pair in zip(items[:len(items)//2], reversed(items[len(items)//2:])) for item in pair]


def list_has_duplicates(lst: list) -> bool:
    return any(lst.count(item) > 1 for item in lst)


def numeric_sequence_from_entropy(entropy: bytes, lemgth: int) -> List[int]:
    """
    GP-0.5.2-eq:F.2

    Parameters
    ----------
    entropy
    lemgth

    Returns
    -------
    List[int]
    """
    result = []

    for i in range(lemgth):
        preimage = entropy + int.to_bytes(i // 8, 4, byteorder='little')
        offset = 4 * i % 32
        result.append(int.from_bytes(blake2b_256_hash(preimage)[offset:offset + 4], byteorder='little'))

    return result

def entropy_shuffle(data: List[int], entropy: bytes) -> List[int]:
    """
    GP-0.5.2-eq:F.3

    Parameters
    ----------
    data
    entropy

    Returns
    -------
    List[int]
    """
    sequence = numeric_sequence_from_entropy(entropy, len(data))

    return fisher_yates_shuffle(data, sequence)

def fisher_yates_shuffle(data: List[int], sequence: List[int]) -> List[int]:
    """
    GP-0.5.2-eq:F.1

    Parameters
    ----------
    data
    sequence

    Returns
    -------

    """
    if len(data) == 0:
        return []

    length = len(data)
    index = sequence[0] % length
    head = data[index]

    data_post = data.copy()
    data_post[index] = data[length-1]

    return [head] + fisher_yates_shuffle(data_post[:-1], sequence[1:])


