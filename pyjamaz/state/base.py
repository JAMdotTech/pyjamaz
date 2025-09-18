import logging
import typing
from collections.abc import Mapping
from enum import Enum
from typing import TypeVar, Optional, Dict, Tuple, List

import pyjamaz.graypaper_constants as gp_const
from pyjamaz.constants import WELL_KNOWN_STORAGE_KEYS
from pyjamaz.exceptions import StateComponentNotFound, StateKeyNoResult
from pyjamaz.hashing import blake2b_256_hash
from pyjamaz.merkle import PatriciaMerkleTrie
from pyjamaz.models.block import Header

from pyjamaz.storage import StorageEngine
from pyjamaz.utils import format_hash, log_execution_time

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
    GP-0.6.7-eq:D.1 | State key constructor for a service account value

    Parameters
    ----------
    service_account_id
    value

    Returns
    -------

    """
    service_account_key = int(service_account_id).to_bytes(4, byteorder="little")
    state_key = bytearray(7)
    value = blake2b_256_hash(value)

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
    GP-0.6.7-eq:D.2 | State key constructor for a storage item hash

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
        value=int(2**32-1).to_bytes(4, byteorder='little') + storage_item_hash
    )

def state_key_constructor_preimage(service_account_id: int, preimage_hash: bytes) -> bytes:
    """
    GP-0.6.7-eq:D.2 | State key constructor for a preimage hash

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
        value=int(2**32-2).to_bytes(4, byteorder='little') + preimage_hash
    )

    return state_key


def state_key_constructor_preimage_availability(
        service_account_id: int, preimage_hash: bytes, preimage_length: int
) -> bytes:
    """
    GP-0.6.7-eq:D.2 | State key constructor for a preimage availability

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
        value=int(preimage_length).to_bytes(4, byteorder="little") + preimage_hash
    )


class StateComponent:

    component_id: int

    def __init__(self, block_context: 'BlockContext', app_context: 'AppContext', **kwargs):

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
        result = self.app_context.state_storage.get(self._state_key_constructor_component())
        if result is None:
            raise StateKeyNoResult(f"No result for state component {self.component_id}")
        return result

    def store(self, data: bytes):
        self.app_context.state_storage.put(self._state_key_constructor_component(), data)

    async def store_state(self, state: 'State'):
        data = state.to_jam_bytes().to_bytes()
        self.store(data)

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


class ItemStatus(Enum):
    deleted = 1


class StateStorage:

    def __init__(self, storage_engine: StorageEngine):
        self.storage_engine = storage_engine
        self.finalized_block_hash = None
        self.block_hash: Optional[bytes] = None
        self.change_sets: Dict[bytes, Dict[bytes, typing.Union[bytes, ItemStatus]]] = {}
        self.transaction: Dict[bytes, typing.Union[bytes, ItemStatus]] = {}
        self.parents: Dict[bytes, Optional[bytes]] = {}
        self.ancestors: Dict[bytes, Header] = {}

    def set_header(self, header: Header):
        self.set_block_hash(header.hash, header.parent)
        self.ancestors[header.hash] = header

    def set_finalized_header(self, header: Header):
        self.set_finalized_block_hash(header.hash)
        self.ancestors[header.hash] = header

    def set_finalized_block_hash(self, block_hash: bytes):
        logging.debug(f"Setting finalized block hash {format_hash(block_hash)}")
        self.finalized_block_hash = block_hash

    def set_block_hash(self, block_hash: bytes, parent_hash: bytes):
        if parent_hash not in self.parents:
            # Check for exceptions (0x00..00 is genesis)
            if parent_hash not in (self.finalized_block_hash, bytes(32)):
                raise ValueError(f"Invalid parent hash {format_hash(parent_hash)}")

        if len(self.transaction) > 0:
            raise ValueError(f"Pending transaction; commit or rollback first")

        logging.debug(f"StateStorage: State set to block hash={format_hash(block_hash)} parent={format_hash(parent_hash)}")
        self.block_hash = block_hash
        self.parents[block_hash] = parent_hash

        self.change_sets[block_hash] = {}

    def set_temporary_block_hash(self, parent_hash: bytes):
        self.set_block_hash(bytes(32), parent_hash)

    def update_temporary_block_hash(self, block_hash: bytes):
        self.parents[block_hash] = self.parents.pop(bytes(32))
        self.change_sets[block_hash] = self.change_sets.pop(bytes(32))
        self.block_hash = block_hash

    def clear_block_hash(self):
        logging.debug(f"StateStorage: Clearing block hash; set to finalized state")
        self.block_hash = None

    def get(self, key: bytes, changeset_only=False) -> Optional[bytes]:

        if self.block_hash:

            if key in self.transaction:
                value = self.transaction[key]
                if value is ItemStatus.deleted:
                    return None
                return value

            lookup_block_hash = self.block_hash
            while lookup_block_hash is not None:
                if key in self.change_sets.get(lookup_block_hash, {}):
                    value = self.change_sets[lookup_block_hash][key]
                    if value is ItemStatus.deleted:
                        return None
                    return value
                lookup_block_hash = self.parents.get(lookup_block_hash)

        if not changeset_only:
            return self.storage_engine.get(key)

        return None

    def get_finalized(self, key: bytes) -> Optional[bytes]:
        return self.storage_engine.get(key)

    def put(self, key: bytes, value: Optional[bytes]):
        if self.block_hash:
            # Add to changeset
            if value is not None:
                self.transaction[key] = value
            else:
                self.transaction[key] = ItemStatus.deleted

        else:
            self.storage_engine.put(key, value)

    def delete(self, key: bytes):
        if self.block_hash:
            self.put(key, None)
        else:
            self.storage_engine.delete(key)

    @log_execution_time
    def state_root(self) -> bytes:
        if len(self.transaction) > 0:
            raise ValueError(f"Pending transaction; commit or rollback first")

        state_trie = PatriciaMerkleTrie(self.as_list())

        state_root = state_trie.root()
        logging.debug(f"StateStorage: Calculated state root {format_hash(state_root)}")

        return state_root

    def as_dict(self) -> Dict[bytes, bytes]:
        if len(self.transaction) > 0:
            raise ValueError(f"Pending transaction; commit or rollback first")

        items = self.storage_engine.as_dict()

        if self.block_hash is not None:
            lookup_block_hash = self.block_hash

            # Process changeset modifications of current ancestors
            processed = []

            while lookup_block_hash is not None:
                if lookup_block_hash in self.change_sets:
                    for key, value in self.change_sets[lookup_block_hash].items():
                        if key not in processed:
                            if value is ItemStatus.deleted:
                                items.pop(key, None)
                            else:
                                items[key] = value
                            processed.append(key)
                lookup_block_hash = self.parents.get(lookup_block_hash)

        return items

    def as_list(self) -> List[Tuple[bytes, bytes]]:
        items = self.as_dict()

        return [(k,v) for k,v in sorted(items.items(), key=lambda x: x[0])]


    def finalize(self, block_hash: bytes):
        if len(self.transaction) > 0:
            raise ValueError(f"Pending transaction; commit or rollback first")

        if block_hash == self.finalized_block_hash:
            return

        lookup_block_hash = block_hash

        # Process changeset modifications of current ancestors
        processed = []

        with self.storage_engine.transaction() as tx:

            while lookup_block_hash is not None:

                if lookup_block_hash in self.change_sets:

                    for key, value in self.change_sets[lookup_block_hash].items():
                        if key not in processed:
                            if value is ItemStatus.deleted:
                                tx.delete(key)
                            else:
                                tx.put(key, value)
                            processed.append(key)

                    # Remove processed changeset
                    del self.change_sets[lookup_block_hash]
                # Get and remove parent
                lookup_block_hash = self.parents.pop(lookup_block_hash, None)
                # Remove ancestor header
                self.ancestors.pop(lookup_block_hash, None)

        self.finalized_block_hash = block_hash
        logging.debug(f"Finalized block hash={format_hash(block_hash)}")

    def clear(self):
        self.change_sets = {}
        self.parents = {}
        self.block_hash = None
        self.transaction = {}

    def commit(self):
        if self.block_hash is not None:

            if self.block_hash == bytes(32):
                raise ValueError('Cannot commit temporary block hash')

            self.change_sets[self.block_hash] = self.transaction
            logging.debug(f"StateStorage: Commit transaction for {format_hash(self.block_hash)}")
        self.transaction = {}

    def rollback(self):
        if self.block_hash is not None:
            self.change_sets.pop(self.block_hash)
            logging.debug(f"StateStorage: Rollback transaction for {format_hash(self.block_hash)}")
        self.transaction = {}

