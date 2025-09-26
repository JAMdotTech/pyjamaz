import logging
import typing
from enum import Enum
from typing import Optional, Dict, List, Tuple

from pyjamaz.merkle import PatriciaMerkleTrie
from pyjamaz.models.block import Header
from pyjamaz.storage import StorageEngine
from pyjamaz.utils import format_hash, log_execution_time


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
        # GP-0.7.0-eq:5.3 (A)
        self.ancestors: Dict[bytes, Header] = {}

    def add_ancestor(self, header: Header):
        self.ancestors[header.hash] = header
        self.parents[header.hash] = header.parent

    def get_parent(self, header: Header) -> Optional[Header]:
        """
        GP-0.7.0-eq:5.2 (P)

        Parameters
        ----------
        header

        Returns
        -------
        Optional[Header]
        """

        if header.parent == bytes(32):
            # H_0
            return Header.default()

        return self.ancestors.get(header.parent, None)

    def set_header(self, header: Header):
        self.set_block_hash(header.hash, header.parent)
        self.ancestors[header.hash] = header

    def set_finalized_header(self, header: Header):
        self.set_finalized_block_hash(header.hash)
        self.add_ancestor(header)

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
        self.ancestors = {}
        self.parents = {}
        self.block_hash = None
        self.finalized_block_hash = None
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
