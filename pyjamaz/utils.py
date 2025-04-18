import itertools
from math import floor
from typing import List, Optional

from pyjamaz.graypaper_constants import CORE_COUNT, VALIDATOR_COUNT, EPOCH_TIMESLOTS, ROTATION_PERIOD_CORE

from pyjamaz.hashing import blake2b_256_hash


def reorder_list_outside_in(items: list) -> list:
    return [item for pair in zip(items[:len(items)//2], reversed(items[len(items)//2:])) for item in pair]


def list_has_duplicates(lst: list) -> bool:
    return any(lst.count(item) > 1 for item in lst)


def flatten_list(nested_list: list) -> list:
    return list(itertools.chain(*nested_list))


def transposition_operator(source_sequence: List[list]) -> List[list]:
    """
    GP-0.6.4-eq:H.5 | the transposition operator

    TODO
    """


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
    data: List[int]
    sequence: List[int]

    Returns
    -------
    List[int]
    """
    if len(data) == 0:
        return []

    data = data.copy()
    length = len(data)
    shuffled_data = []

    for item in sequence:
        if length == 0:
            break
        index = item % length
        shuffled_data.append(data[index])
        data[index] = data[length - 1]
        length -= 1

    return shuffled_data


def guarantor_rotation(core_indices: List[int], rotation_offset: int) -> List[int]:
    """
    GP-0.5.3-eq:11.19 (R) | Guarantor assigment rotation function

    Parameters
    ----------
    core_indices
    rotation_offset

    Returns
    -------
    List[int]
    """
    return [(x+rotation_offset) % CORE_COUNT for x in core_indices]

def guarantor_permute(entropy: bytes, timeslot: int) -> List[int]:
    """
    GP-0.5.3-eq:11.20 (P) | Guarantor assigment permute function

    Parameters
    ----------
    entropy
    timeslot

    Returns
    -------
    List[int]
    """
    core_indices = entropy_shuffle(
        data=[floor(CORE_COUNT * i / VALIDATOR_COUNT) for i in range (0, VALIDATOR_COUNT)],
        entropy=entropy
    )
    return guarantor_rotation(core_indices, floor(timeslot % EPOCH_TIMESLOTS / ROTATION_PERIOD_CORE))


def substitute_if_nothing(*args) -> Optional[any]:
    """
    GP-0.6.4-eq:3.2 (function_U) | Equivalent to the first argument which is not ∅, or ∅ if no such argument exists.
    """
    for arg in args:
        if arg is not None:
            return arg
    return None


def vrf_input_ticket_seal(entropy: bytes, ticket_attempt: int) -> bytes:
    return b"jam_ticket_seal" + entropy + int.to_bytes(ticket_attempt, byteorder='little', length=1)


def vrf_input_fallback_seal(entropy: bytes) -> bytes:
    return b"jam_fallback_seal" + entropy


def format_hash(hash: bytes) -> str:
    return f'0x{hash[:4].hex()}...{hash[-4:].hex()}'
