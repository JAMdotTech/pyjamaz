import typing
from collections.abc import Mapping
from typing import TypeVar, Optional

import pyjamaz.graypaper_constants as gp_const
from pyjamaz.constants import WELL_KNOWN_STORAGE_KEYS
from pyjamaz.exceptions import StateComponentNotFound, StateKeyNoResult
from pyjamaz.hashing import blake2b_256_hash

from pyjamaz.storage import StorageEngine, Transaction

if typing.TYPE_CHECKING:
    from pyjamaz.models.state import State
    from pyjamaz.models.context import AppContext, BlockContext

T = TypeVar('T')


def state_key_constructor_service_account(service_account_id) -> bytes:
    """
    GP-0.6.6-eq:D.1 | State key constructor for a service account

    Parameters
    ----------
    service_account_id

    Returns
    -------
    bytes
    """
    service_account_key = int(service_account_id).to_bytes(4, byteorder="little")

    state_key = bytearray(31)
    state_key[0] = 255
    state_key[1] = service_account_key[0]
    state_key[3] = service_account_key[1]
    state_key[5] = service_account_key[2]
    state_key[7] = service_account_key[3]

    return bytes(state_key)

def state_key_constructor_service_account_value(service_account_id: int, value: bytes) -> bytes:
    """
    GP-0.6.6-eq:D.1 | State key constructor for a service account value

    Parameters
    ----------
    service_account_id
    value

    Returns
    -------

    """
    service_account_key = int(service_account_id).to_bytes(4, byteorder="little")
    state_key = bytearray(7)

    state_key[0] = service_account_key[0]
    state_key[1] = value[0]
    state_key[2] = service_account_key[1]
    state_key[3] = value[1]
    state_key[4] = service_account_key[2]
    state_key[5] = value[2]
    state_key[6] = service_account_key[3]

    return bytes(state_key) + value[3:27]

def state_key_constructor_storage_item(service_account_id: int, storage_item_hash: bytes) -> bytes:
    """
    GP-0.6.6-eq:D.2 | State key constructor for a storage item hash

    Parameters
    ----------
    service_account_id: int
    storage_item_hash: bytes

    Returns
    -------
    bytes
    """
    return state_key_constructor_service_account_value(
        service_account_id=service_account_id,
        value=int(2**32-1).to_bytes(4, byteorder='little') + storage_item_hash[0:27]
    )

def state_key_constructor_preimage(service_account_id: int, preimage_hash: bytes) -> bytes:
    """
    GP-0.6.6-eq:D.2 | State key constructor for a preimage hash

    Parameters
    ----------
    service_account_id: int
    preimage_hash: bytes

    Returns
    -------
    bytes
    """
    state_key = state_key_constructor_service_account_value(
        service_account_id=service_account_id,
        value=int(2**32-2).to_bytes(4, byteorder='little') + preimage_hash[1:28]
    )

    return state_key


def state_key_constructor_preimage_availability(
        service_account_id: int, preimage_hash: bytes, preimage_length: int
) -> bytes:
    """
    GP-0.6.6-eq:D.2 | State key constructor for a preimage availability

    Parameters
    ----------
    service_account_id: int
    preimage_hash: bytes
    preimage_length: bytes
    Returns
    -------
    bytes
    """
    return state_key_constructor_service_account_value(
        service_account_id=service_account_id,
        value=int(preimage_length).to_bytes(4, byteorder="little") + blake2b_256_hash(preimage_hash)[2:29]
    )


class StateComponent:

    component_id: int

    def __init__(self, storage_engine: StorageEngine, block_context: 'BlockContext', app_context: 'AppContext', **kwargs):

        self.storage_engine = storage_engine
        self.block_context = block_context
        self.app_context = app_context

    def state_transition(self, *args):
        raise NotImplementedError

    def _state_key_constructor_component(self) -> bytes:
        """
        GP-0.3.8-eq:290,291 Only wellknown storage keys
        """
        try:
            return WELL_KNOWN_STORAGE_KEYS[self.component_id]
        except IndexError:
            raise StateComponentNotFound(f"State component ID {self.component_id} not found")

    def retrieve(self):
        result = self.storage_engine.get(self._state_key_constructor_component())
        if result is None:
            raise StateKeyNoResult(f"No result for state component {self.component_id}")
        return result

    def store(self, data: bytes, transaction: Transaction = None):
        if transaction is not None:
            transaction.put(self._state_key_constructor_component(), data)
        else:
            self.storage_engine.put(self._state_key_constructor_component(), data)

    async def store_state(self, state: 'State', transaction: Optional[Transaction] = None):
        data = state.to_jam_bytes().to_bytes()
        self.store(data, transaction)

    def retrieve_state(self):
        raise NotImplementedError

    @staticmethod
    def is_epoch_change(pre_slotnumber: int, post_slotnumber: int) -> bool:
        """
        GP-0.3.8-general: `e!=e' ? T, F` | Helper function that determines if the epoch has changed.

        Returns
        -------
        bool
            `True` when epoch has changed, `False` otherwise.
        """
        return pre_slotnumber // gp_const.EPOCH_TIMESLOTS != post_slotnumber // gp_const.EPOCH_TIMESLOTS

    @staticmethod
    def slot_phase_index(slot_number: int) -> int:
        """
        GP-0.3.8-eq:46 (m) | Function that returns the phase index into the epoch of the timeslot

        Returns
        -------
        number: int
            Phase index into the epoch of the timeslot

        """
        return slot_number % gp_const.EPOCH_TIMESLOTS

    @staticmethod
    def epoch_number(slot_number: int) -> int:
        """
        GP-0.3.8-eq:46 (e) | Function that returns the epoch index

        Returns
        -------
        number: int
            Epoch index of the timeslot

        """
        return slot_number // gp_const.EPOCH_TIMESLOTS


class StorageMap(Mapping):
    def __init__(self, storage_engine: StorageEngine, storage_key_func: callable, storage_value_func: callable, initial_data: dict = None):
        self.storage_engine = storage_engine
        if initial_data is None:
            initial_data = {}
        self.cache = initial_data
        self.storage_key_func = storage_key_func
        self.storage_value_func = storage_value_func

    def retrieve_from_storage(self, key: any) -> Optional[any]:
        storage_key = self.storage_key_func(key)

        # Perform lookup in storage_engine
        data = self.storage_engine.get(storage_key)

        if data is not None:
            return self.storage_value_func(data, key=key)

    def __getitem__(self, key):
        value = self.retrieve_from_storage(key)
        if value is not None:
            self.cache[key] = value
        return value

    def __contains__(self, key):

        value = self.retrieve_from_storage(key)
        if value is not None:
            self.cache[key] = value
            return True
        return False

    def __iter__(self):
        # Filter out None values in cache (previous attempts to retrieve which had no result)
        return (key for key, value in self.cache.items() if value is not None)

    def __len__(self):
        return len(self.cache)


