import inspect
import itertools
import logging
import time
from base64 import b32encode
from functools import wraps
from math import floor
from typing import List, Optional

from pyjamaz.graypaper_constants import CORE_COUNT, VALIDATOR_COUNT, EPOCH_TIMESLOTS, ROTATION_PERIOD_CORE

from pyjamaz.hashing import blake2b_256_hash
from pyjamaz.settings import DEBUG


def reorder_list_outside_in(items: list) -> list:
    return [item for pair in zip(items[:len(items)//2], reversed(items[len(items)//2:])) for item in pair]


def list_has_duplicates(lst: list) -> bool:
    return any(lst.count(item) > 1 for item in lst)


def flatten_list(nested_list: list) -> list:
    return list(itertools.chain(*nested_list))


def transposition_operator(source_sequence: List[list]) -> List[list]:
    """
    GP-0.7.1-eq:H.5 | the transposition operator

    TODO
    """


def numeric_sequence_from_entropy(entropy: bytes, lemgth: int) -> List[int]:
    """
    GP-0.7.1-eq:F.2

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
    GP-0.7.1-eq:F.3

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
    GP-0.7.1-eq:F.1

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
    GP-0.7.1-eq:11.19 (function_R) | Guarantor assigment rotation function

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
    GP-0.7.1-eq:11.20 (function_P) | Guarantor assigment permute function

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
    GP-0.7.1-eq:3.2 (function_U) | Equivalent to the first argument which is not ∅, or ∅ if no such argument exists.
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


def quic_peer_id(ed25519_public_key: bytes) -> str:
    peer_id = 'e'

    alphabet = 'abcdefghijklmnopqrstuvwxyz234567'
    n = int.from_bytes(ed25519_public_key, "little")

    for i in range(51, -1 , -1):
        peer_id += alphabet[n % 32]
        n //= 32

    return peer_id


def ed25519_pubkey_from_peer_id(peer_id: str) -> bytes:
    if not peer_id.startswith('e') or len(peer_id) != 53:
        raise ValueError("Invalid peer ID format")

    alphabet = 'abcdefghijklmnopqrstuvwxyz234567'
    char_to_value = {c: i for i, c in enumerate(alphabet)}

    n = 0
    for c in reversed(peer_id[1:]):  # Skip the 'e' prefix
        if c not in char_to_value:
            raise ValueError(f"Invalid character in peer ID: {c}")
        n = n * 32 + char_to_value[c]

    return n.to_bytes(32, 'little')

def sum_dict_values(d1: dict, d2: dict) -> dict:
    return {k: d1.get(k, 0) + d2.get(k, 0) for k in set(d1) | set(d2)}


def log_execution_time(func):
    if not DEBUG:
        return func

    @wraps(func)
    def _name(*args):
        func_name = func.__name__
        if args:
            first = args[0]

            if isinstance(first, type):
                class_name = first.__name__
                return f"{class_name}.{func_name}"

            if hasattr(first, "__class__"):
                class_name = first.__class__.__name__
                return f"{class_name}.{func_name}"
        return func_name

    if inspect.iscoroutinefunction(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            start_time = time.perf_counter()
            result = await func(*args, **kwargs)
            end_time = time.perf_counter()
            execution_time = end_time - start_time
            logging.info(f"⏱️ {_name(*args)} executed in {execution_time:.6f} seconds")
            return result
        return async_wrapper
    else:
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.perf_counter()
            result = func(*args, **kwargs)
            end_time = time.perf_counter()
            execution_time = end_time - start_time
            logging.info(f"⏱️ {_name(*args)} executed in {execution_time:.6f} seconds")
            return result
        return wrapper
