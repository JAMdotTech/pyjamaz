import logging
import typing
from enum import Enum
from typing import Optional, Dict, List, Tuple

from pyjamaz.merkle import PatriciaMerkleTrie
from pyjamaz.models.block import AncestorReference, Header
from pyjamaz.settings import DEBUG
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
        # GP-0.7.2-eq:5.3 (A)
        self.ancestors: Dict[bytes, Header | AncestorReference] = {}

    def add_ancestor(self, header: Header | AncestorReference):
        self.ancestors[header.hash] = header
        self.parents[header.hash] = header.parent

    def get_parent(self, header: Header) -> Header | AncestorReference | None:
        """
        GP-0.7.2-eq:5.2 (P)

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
        DEBUG and logging.debug(f"Setting finalized block hash {format_hash(block_hash)}")
        block_hash = bytes(block_hash)
        self.finalized_block_hash = block_hash


    def set_block_hash(self, block_hash: bytes, parent_hash: bytes):
        if parent_hash not in self.parents:
            # Check for exceptions (0x00..00 is genesis)
            if parent_hash not in (self.finalized_block_hash, bytes(32)):
                raise ValueError(f"Invalid parent hash {format_hash(parent_hash)}")

        if len(self.transaction) > 0:
            raise ValueError(f"Pending transaction; commit or rollback first")

        DEBUG and logging.debug(f"StateStorage: State set to block hash={format_hash(block_hash)} parent={format_hash(parent_hash)}")
        self.block_hash = block_hash
        self.parents[block_hash] = parent_hash

        self.change_sets[block_hash] = {}

    def set_temporary_block_hash(self, parent_hash: bytes):
        self.set_block_hash(bytes(32), parent_hash)

    def select_block_hash(self, block_hash: bytes):
        """Select an existing retained posterior state without rewriting it."""
        block_hash = bytes(block_hash)
        if len(self.transaction) > 0:
            raise ValueError("Pending transaction; commit or rollback first")
        if (
            block_hash != self.finalized_block_hash
            and block_hash not in self.change_sets
        ):
            raise KeyError("state for block hash is unavailable")
        self.block_hash = block_hash

    def has_state_at(self, block_hash: bytes) -> bool:
        """Return whether the posterior state can be selected immediately.

        Block bodies and headers are persisted independently from unfinalized
        state overlays.  After restart those bodies remain useful for replay,
        but they must not be mistaken for an executable parent state.
        """
        block_hash = bytes(block_hash)
        return (
            block_hash == self.finalized_block_hash
            or block_hash in self.change_sets
        )

    def update_temporary_block_hash(self, block_hash: bytes):
        self.parents[block_hash] = self.parents.pop(bytes(32))
        self.change_sets[block_hash] = self.change_sets.pop(bytes(32))
        self.block_hash = block_hash

    def clear_block_hash(self):
        DEBUG and logging.debug(f"StateStorage: Clearing block hash; set to finalized state")
        self.block_hash = None

    def get(self, key: bytes, changeset_only=False) -> Optional[bytes]:

        if self.block_hash:

            if key in self.transaction:
                value = self.transaction[key]
                if value is ItemStatus.deleted:
                    return None
                return value

            lookup_block_hash = self.block_hash
            visited: set[bytes] = set()
            while lookup_block_hash is not None:
                if lookup_block_hash in visited:
                    raise ValueError("Cycle detected in retained state ancestry")
                visited.add(lookup_block_hash)
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
        DEBUG and logging.debug(f"StateStorage: Calculated state root {format_hash(state_root)}")

        return state_root

    def as_dict(self) -> Dict[bytes, bytes]:
        if len(self.transaction) > 0:
            raise ValueError(f"Pending transaction; commit or rollback first")

        items = self.storage_engine.as_dict()

        if self.block_hash is not None:
            lookup_block_hash = self.block_hash
            visited: set[bytes] = set()

            # Process changeset modifications of current ancestors
            processed = []

            while lookup_block_hash is not None:
                if lookup_block_hash in visited:
                    raise ValueError("Cycle detected in retained state ancestry")
                visited.add(lookup_block_hash)
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

    def as_dict_at(self, block_hash: bytes) -> Dict[bytes, bytes]:
        """Return an immutable posterior-state view for a retained block."""
        block_hash = bytes(block_hash)
        if len(block_hash) != 32 or block_hash == bytes(32):
            raise KeyError("state block hash is invalid")
        items = self.storage_engine.as_dict()
        if block_hash == self.finalized_block_hash:
            return items
        if block_hash not in self.change_sets:
            raise KeyError("state for block hash is unavailable")

        processed: set[bytes] = set()
        visited: set[bytes] = set()
        lookup_block_hash: bytes | None = block_hash
        while lookup_block_hash != self.finalized_block_hash:
            if lookup_block_hash in visited:
                raise KeyError("state ancestry for block hash contains a cycle")
            visited.add(lookup_block_hash)
            changes = self.change_sets.get(lookup_block_hash)
            if changes is None:
                raise KeyError("state ancestry for block hash is unavailable")
            for key, value in changes.items():
                if key in processed:
                    continue
                processed.add(key)
                if value is ItemStatus.deleted:
                    items.pop(key, None)
                else:
                    items[key] = value
            if lookup_block_hash not in self.parents:
                raise KeyError("state ancestry for block hash is unavailable")
            lookup_block_hash = self.parents[lookup_block_hash]
        return items

    def as_list_at(self, block_hash: bytes) -> List[Tuple[bytes, bytes]]:
        return sorted(self.as_dict_at(block_hash).items(), key=lambda item: item[0])

    def state_root_at(self, block_hash: bytes) -> bytes:
        return PatriciaMerkleTrie(self.as_list_at(block_hash)).root()


    def finalize(self, block_hash: bytes):
        if len(self.transaction) > 0:
            raise ValueError(f"Pending transaction; commit or rollback first")

        block_hash = bytes(block_hash)
        if block_hash == self.finalized_block_hash:
            return

        previous_finalized = self.finalized_block_hash
        path: list[bytes] = []
        cursor: bytes | None = block_hash
        visited: set[bytes] = set()
        while cursor != previous_finalized:
            if cursor is None or cursor in visited or cursor not in self.change_sets:
                raise ValueError("Cannot finalize a block outside the retained finalized branch")
            visited.add(cursor)
            path.append(cursor)
            cursor = self.parents.get(cursor)

        # Commit in chronological order. This makes deletion and later writes
        # behave exactly like applying each selected block transition to base.
        with self.storage_engine.transaction() as tx:
            for selected_hash in reversed(path):
                for key, value in self.change_sets[selected_hash].items():
                    if value is ItemStatus.deleted:
                        tx.delete(key)
                    else:
                        tx.put(key, value)

        original_parents = dict(self.parents)

        def descends_from_target(candidate: bytes) -> bool:
            seen: set[bytes] = set()
            cursor = candidate
            while cursor not in seen:
                if cursor == block_hash:
                    return True
                seen.add(cursor)
                parent = original_parents.get(cursor)
                if parent is None:
                    return False
                cursor = parent
            return False

        retained = {
            candidate for candidate in self.change_sets
            if candidate not in path and descends_from_target(candidate)
        }
        self.change_sets = {
            candidate: changes
            for candidate, changes in self.change_sets.items()
            if candidate in retained
        }
        retained_with_finalized = retained | {block_hash}
        self.parents = {
            candidate: parent
            for candidate, parent in original_parents.items()
            if candidate in retained_with_finalized
        }
        self.parents[block_hash] = None
        self.ancestors = {
            candidate: header
            for candidate, header in self.ancestors.items()
            if candidate in retained_with_finalized
        }

        self.finalized_block_hash = block_hash
        if self.block_hash not in retained_with_finalized:
            self.block_hash = block_hash
        DEBUG and logging.debug(f"Finalized block hash={format_hash(block_hash)}")

    def clear(self):
        self.change_sets = {}
        self.ancestors = {}
        self.parents = {}
        self.block_hash = None
        self.finalized_block_hash = None
        self.transaction = {}

    def start_tx(self):
        self.transaction = {}

    def commit(self):
        if self.block_hash is not None:

            if self.block_hash == bytes(32):
                raise ValueError('Cannot commit temporary block hash')

            self.change_sets[self.block_hash] = self.transaction
            DEBUG and logging.debug(f"StateStorage: Commit transaction for {format_hash(self.block_hash)}")

        # Clear transaction
        self.transaction = {}


    def rollback(self):
        if self.block_hash is not None:
            self.change_sets.pop(self.block_hash, None)
            DEBUG and logging.debug(f"StateStorage: Rollback transaction for {format_hash(self.block_hash)}")

        # Clear transaction
        self.transaction = {}

    def discard_candidate(self, block_hash: bytes, restore_hash: bytes | None) -> None:
        """Discard one rejected overlay and reselect its retained predecessor.

        ``rollback`` historically removed writes but deliberately left head
        selection to its caller. Validator execution needs the stronger
        operation: a rejected locally produced/imported header must never
        remain the selected state hash because that header is not persisted.
        """
        block_hash = bytes(block_hash)
        restore_hash = None if restore_hash is None else bytes(restore_hash)
        if block_hash == self.finalized_block_hash:
            raise ValueError("cannot discard the finalized state overlay")
        if self.block_hash != block_hash:
            raise ValueError("candidate state overlay is not selected")
        if (
            restore_hash is not None
            and restore_hash != self.finalized_block_hash
            and restore_hash not in self.change_sets
        ):
            raise KeyError("restore state overlay is unavailable")

        self.change_sets.pop(block_hash, None)
        self.parents.pop(block_hash, None)
        self.ancestors.pop(block_hash, None)
        self.transaction = {}
        self.block_hash = restore_hash
