import logging
from copy import deepcopy
from dataclasses import dataclass, field
from math import ceil
from typing import List, Optional, Dict, Tuple, Union, Set

from jamcodec.base import JamBytes

from pyjamaz.exceptions import StateKeyNoResult, BlockValidationError
from pyjamaz.hashing import keccak_256_hash, blake2b_256_hash

from jamcodec.mixins import Serializable
from jamcodec.types import U32, Array, H256, Vec, U8, Option, U64, Map, Bytes, Enum, Tuple as JamTuple, VarInt64
from pyjamaz.graypaper_constants import EPOCH_TIMESLOTS, VALIDATOR_COUNT, CORE_COUNT, \
    MAXIMUM_AUTHORIZATION_QUEUE_ITEMS, MINIMUM_BALANCE_SERVICE, MINIMUM_BALANCE_ITEM, \
    MINIMUM_BALANCE_OCTET, EC_SEGMENT_SIZE, MINIMUM_PUBLIC_SERVICE_ID
from pyjamaz.merkle import WellBalancedMerkleTree, MerkleMountainRange
from pyjamaz.models.common import ValidatorData, Assurance, WorkReport, TicketBody, WorkPackage, DeferredTransfer
from pyjamaz.pvm.invocation import InvocationContext
from pyjamaz.settings import DEBUG

from pyjamaz.state.base import StorageMap, state_key_constructor_service_account, state_key_constructor_preimage, \
    state_key_constructor_storage_item, state_key_constructor_preimage_availability
from pyjamaz.state.storage import StateStorage
from pyjamaz.storage import StorageEngine

from pyjamaz.models.block import Assurance as ExtrinsicAssurance, Preimage


class State(Serializable):

    def __setattr__(self, key, value):
        super().__setattr__(key, value)


@dataclass
class TimeslotState(State, Serializable):
    """
    GP-0.7.1-eq:6.1 (τ) | The most recent block's slot index, combined with helper functions.

    Attributes
    ----------
    number: U32
        GP-0.7.1-eq:6.1 (τ) | The most recent block's slot index.
    """
    # Todo: consider renaming number to timeslot
    number: int = field(metadata={'codec': U32})

    def epoch_number(self) -> int:
        """
        GP-0.7.1-eq:6.2 (e) | Function that returns the epoch index.

        Returns
        -------
        number: int
            Epoch index of the timeslot.

        """
        return self.number // EPOCH_TIMESLOTS

    def slot_phase_index(self) -> int:
        """
        GP-0.7.1-eq:6.2 (m) | Function that returns the phase index into the epoch of the timeslot.

        Returns
        -------
        number: int
            Phase index into the epoch of the timeslot.

        """
        return self.number % EPOCH_TIMESLOTS


@dataclass
class EntropyState(State, Serializable):
    """
    GP-0.7.1-eq:6.21 (η) | Entropy partition of the overall state.

    Attributes
    ----------
    entropy: Array(H256,4)
        GP-0.7.1-eq:6.21 (η) | η[0] serves as an entropy accumulator during the current epoch. η[1], η[2], η[3] retain
        three historical values of the accumulator at the point of each of the three most recently ended epochs
        respectively.
    """
    entropy: List[bytes] = field(metadata={'codec': Array(H256, 4)})


@dataclass
class SlotSealerSeries(Serializable):
    tickets: Optional[List[TicketBody]] = field(
        default=None,
        metadata={'codec': Option(Array(TicketBody.to_codec_def(), EPOCH_TIMESLOTS))}
    )
    keys: Optional[List[bytes]] = field(default=None, metadata={'codec': Option(Array(H256, EPOCH_TIMESLOTS))})

    _codec_type_def = Enum(
        tickets=Array(TicketBody.to_codec_def(), EPOCH_TIMESLOTS),
        keys=Array(H256, EPOCH_TIMESLOTS)
    )

    def __post_init__(self):
        if self.tickets is None and self.keys is None:
            raise BlockValidationError("Either tickets or keys must be set")


@dataclass
class SafroleState(State, Serializable):
    """
    GP-0.7.1-eq:6.3 (γ) | Safrole partition of the overall state.

    Attributes
    ----------
    validators: Array(ValidatorData,constant_V)
        GP-0.7.1-eq:6.7 (γ_P) | A fixed size set of keys and metadata for validators of the next epoch.
    ring_commitment: Array(U8,144)
        GP-0.7.1-eq:6.4 (γ_Z) | Bandersnatch ring commitment.
    slot_sealer_series: SlotSealerSeries
        GP-0.7.1-eq:6.5 (γ_S) | Sealing-key series of the current epoch.
    ticket_accumulator: TicketBody
        GP-0.7.1-eq:6.5 (γ_A) | Sealing-key contest ticket accumulator.
    """
    validators: List[ValidatorData] = field(metadata={'codec': Array(ValidatorData.to_codec_def(), VALIDATOR_COUNT)})
    ring_commitment: bytes = field(metadata={'codec': Array(U8, 144)})
    slot_sealer_series: SlotSealerSeries = field(metadata={'codec': SlotSealerSeries.to_codec_def()})
    ticket_accumulator: List[TicketBody] = field(metadata={'codec': Vec(TicketBody.to_codec_def())})


@dataclass
class ValidatorQueueState(State, Serializable):
    """
    GP-0.7.1-eq:6.7 (ι) | Validator keys and metadata to be drawn from next by the Safrole protocol.

    Attributes
    ----------
    validators: Array(ValidatorData,constant_V)
        GP-0.7.1-eq:6.7 (ι) | A fixed size set of validator keys and metadata to be drawn from next by the Safrole
        protocol.
    """
    # Todo: review and annotate: ValidatorData
    validators: List[ValidatorData] = field(metadata={'codec': Array(ValidatorData.to_codec_def(), VALIDATOR_COUNT)})


@dataclass
class ValidatorPoolState(State, Serializable):
    """
    GP-0.7.1-eq:6.7 (κ) | Keys and metadata for validators of the current epoch.

    Attributes
    ----------
    validators: Array(ValidatorData,constant_V)
        GP-0.7.1-eq:6.7 (κ) | A fixed size set of keys and metadata for validators of the current epoch.
    """
    # Todo: review and annotate: ValidatorData
    validators: List[ValidatorData] = field(metadata={'codec': Array(ValidatorData.to_codec_def(), VALIDATOR_COUNT)})


@dataclass
class ValidatorArchiveState(State, Serializable):
    """
    GP-0.7.1-eq:6.7 (λ) | Keys and metadata for validators of the previous epoch.

    Attributes
    ----------
    validators: Array(ValidatorData,constant_V)
        GP-0.7.1-eq:6.7 (λ) | A fixed size set of keys and metadata for validators of the previous epoch.
    """
    # Todo: review and annotate: ValidatorData
    validators: List[ValidatorData] = field(metadata={'codec': Array(ValidatorData.to_codec_def(), VALIDATOR_COUNT)})


@dataclass
class AuthorizerPoolsState(State, Serializable):
    """
    GP-0.7.1-eq:8.1 (α) | A collections of pools of authorizations for all cores.

    Attributes
    ----------
    authorizer_pools: Array(Vec(H256),constant_C)
        GP-0.7.1-eq:8.1 (α) | A collections of pools of authorizations for all cores.
    """
    authorizer_pools: List[List[bytes]] = field(metadata={'codec': Array(Vec(H256), CORE_COUNT)})

    def __post_init__(self):
        # Todo: 'vec' within array attribute is allowed to have up to constant_O (MAXIMUM_AUTHORIZATION_POOL_ITEMS=8)
        # items.
        pass

    def is_authorized(self, work_package: WorkPackage, core_index: int) -> bool:
        if core_index > len(self.authorizer_pools):
            return False
        return work_package.authorizer_hash() in self.authorizer_pools[core_index]


@dataclass
class Mmr(Serializable):
    """
    GP-0.7.1-eq:E.8,E.9 (bold_b) | A Merkle Mountain Range.

    Attributes
    ----------

    peaks: Vec(Option(H256))
        GP-0.7.1-eq:7.3 (β_B) | A collection of optional peaks in a Merkle Mountain Range
    """
    # TODO: double check β_B
    peaks: List[Optional[bytes]] = field(metadata={'codec': Vec(Option(H256))})

    def super_peak(self) -> bytes:
        mmr = MerkleMountainRange(self.peaks)
        return mmr.super_peak()



@dataclass
class ReportedWorkPackage(Serializable):
    """
    GP-0.7.1-eq:7.2 (bold_p) | A collection of hashes for each work-report made into the MMR, limited to the number
    of cores (constant_c=341)

    Attributes
    ----------
    hash: H256
        GP-0.7.1-eq:7.2 (blackboard_H in dictionary) | The segment_tree_lookup_item key.
    exports_root: H256
        GP-0.7.1-eq:7.2 (blackboard_H in dictionary) | The segment_tree_lookup_item key.
    """
    hash: bytes = field(metadata={'codec': H256})
    exports_root: bytes = field(metadata={'codec': H256})


@dataclass
class RecentBlock(Serializable):
    """
    GP-0.7.1-eq:7.2 (β_H) | A single item in the RecentHistory partition of the overall state.

    Attributes
    ----------

    header_hash: H256
        GP-0.7.1-eq:7.2 (h, blackboard_H) | Header hash of the recent block.
    beefy_root: H256
        GP-0.7.1-eq:7.2 (b) | Beefy root of the recent block.
    state_root: H256
        GP-0.7.1-eq:7.2 (s, blackboard_H) | State root of the recent block.
    reported: Vec(ReportedWorkPackage)
        GP-0.7.1-eq:7.2 (bold_p) | A collection of ReportedWorkPackage for each work-report made into the MMR, limited
        to the number of cores (constant_c=341)
    """
    header_hash: bytes = field(metadata={'codec': H256})
    beefy_root: bytes = field(metadata={'codec': H256})
    state_root: bytes = field(metadata={'codec': H256})
    # TODO: GP-0.5.0-eq:7.1 states bold_p needs to be a dictionary, GP-0.5.0-eq:D.2 states bold_p needs to have a
    # length prefix encoding.
    reported: List[ReportedWorkPackage] = field(metadata={'codec': Vec(ReportedWorkPackage.to_codec_def())})

    def __post_init__(self):
        # Todo: 'reported' attribute is allowed to have up to constant_C (CORES=341) items.
        pass


@dataclass
class RecentHistoryState(State, Serializable):
    """
    GP-0.7.1-eq:7.1 (β) | RecentHistory partition of the overall state

    Attributes
    ----------
    recent_blocks: Vec(RecentBlock)
        GP-0.7.1-eq:7.1 (β_H) | A collection of items in the RecentHistory partition of the overall state of
        up to constant_H (8) items.
    accumulation_output_log: Vec(Option(H256))
        GP-0.7.1-eq:7.1 (β_B) | A collection of optional peaks in a Merkle Mountain Range.
    """
    recent_blocks: List[RecentBlock] = field(metadata={'codec': Vec(RecentBlock.to_codec_def())})
    accumulation_output_log: List[Optional[bytes]] = field(metadata={'codec': Vec(Option(H256))})


    def __post_init__(self):
        # Todo: RecentHistory is allowed to have up to constant_H (HISTORY) items
        # Todo: Arjan this is a Vec (variable size) since it contains less than 8 items for the first 8
        #  blocks after genesis, so for the first 8 blocks it should have TAU entries and from block 9 and onwards it
        #  should have exactly constant_H (8) entries.
        #  GP-0.5.0-eq:D.2-C(3) states encoding is a Vec (i.e. has length definition)
        pass

    def get_recent_block(self, block_hash) -> Optional[RecentBlock]:
        for block in self.recent_blocks:
            if block.header_hash == block_hash:
                return block
        return None

class StorageItemMap(StorageMap):
    def __init__(self, service_account_id: int , storage_engine: StorageEngine):

        super().__init__(
            storage_engine=storage_engine,
            storage_key_func=lambda key: state_key_constructor_storage_item(service_account_id, key),
            storage_value_func=lambda data, key: data
        )

class PreimageMap(StorageMap):
    def __init__(self, service_account_id: int , storage_engine: StorageEngine):

        super().__init__(
            storage_engine=storage_engine,
            storage_key_func=lambda key: state_key_constructor_preimage(service_account_id, key),
            storage_value_func=lambda data, key: data
        )

class PreimageAvailabilityMap(StorageMap):
    def __init__(self, service_account_id: int , storage_engine: StorageEngine):

        def storage_value_func(data: bytes, key: int) -> List[int]:
            obj = Vec(U32).new()
            obj.decode(JamBytes(data))
            return obj.value

        super().__init__(
            storage_engine=storage_engine,
            storage_key_func=lambda key: state_key_constructor_preimage_availability(
                service_account_id=service_account_id, preimage_hash=key[0], preimage_length=key[1]
            ),
            storage_value_func=storage_value_func
        )

@dataclass
class ServiceAccount(Serializable):
    """
    GP-0.7.1-eq:9.3 (blackboard_A) | A service account.

    Attributes
    ----------
    code_hash: H256
        GP-0.7.1-eq:9.3 (c) | Hash of the service account's code
    balance: U64
        GP-0.7.1-eq:9.3 (b) | Balance of a service account
    gas_limit_accumulate: U64
        GP-0.7.1-eq:9.3 (g) | Minimum gas required to execute the Accumulate entry-point of the service account's code.
    gas_limit_on_transfer: U64
        GP-0.7.1-eq:9.3 (m) | Minimum gas required to execute the On-Transfer entry-point of the service account's code.
    footprint_storage_bytes: U64
        GP-0.7.1-eq:9.8 (o) | Storage footprint of the service account. The total number of bytes used in storage.
    footprint_storage_items: U32
        GP-0.7.1-eq:9.8 (i) | Storage footprint of the service account. The number of items in storage.
    threshold_balance: U64
        GP-0.7.1-eq:9.8 (t) | Minimum or threshold balance needed for the ServiceAccount in terms of its storage
        footprint.
    deposit_offset: U32
        GP-0.7.1-eq:9.3 (f) | Gratis deposit offset.
    creation_slot: U32
        GP-0.7.1-eq:9.3 (r) | Timeslot when created
    last_accumulation_slot: U64
        GP-0.7.1-eq:9.3 (a) | Timeslot when last accumulated
    parent_service: U64
        GP-0.7.1-eq:9.3 (p) | Parent service.
    storage_items: Dict(H256,Bytes)
        GP-0.7.1-eq:9.3 (bold_s) | Storage items dict. Provides storage item data for storage item hash.
    preimages: Dict(H256,Bytes)
        GP-0.7.1-eq:9.3 (bold_p) | Preimages dict. Provides preimage data for preimage hash (including: code_hash)
    preimage_availability: Dict(Tuple(H256,U32), Vec<U32>)
        GP-0.7.1-eq:9.3 (bold_l) | Preimages availability dict. Provides historical status of preimage availability.
    """
    # Remark: Only the following field need to be serialized/deserialized
    code_hash: bytes = field(metadata={'codec': H256})
    balance: int = field(metadata={'codec': U64})
    gas_limit_accumulate: int = field(metadata={'codec': U64})
    # TODO remove
    gas_limit_on_transfer: int = field(metadata={'codec': U64})
    footprint_storage_bytes: int = field(metadata={'codec': U64})
    deposit_offset: int = field(metadata={'codec': U64})
    footprint_storage_items: int = field(metadata={'codec': U32})
    storage_items: Union[Dict[bytes, Optional[bytes]], StorageItemMap] = field(metadata={'codec': Map(H256, Bytes)})
    preimages: Union[Dict[bytes, bytes], PreimageMap] = field(metadata={'codec': Map(H256, Bytes)})
    preimage_availability: Union[Dict[Tuple[bytes, int], List[int]], PreimageAvailabilityMap] = field(metadata={
        'codec': Map(JamTuple(H256, U32), Vec(U32))}
    )
    creation_slot: int = field(metadata={'codec': U32})
    last_accumulation_slot: int = field(metadata={'codec': U32})
    parent_service: int = field(metadata={'codec': U32})

    @property
    def threshold_balance(self):
        # GP-0.7.1-eq:9.8 (a_t)
        return max(0,
            MINIMUM_BALANCE_SERVICE + MINIMUM_BALANCE_ITEM * self.footprint_storage_items +
            MINIMUM_BALANCE_OCTET * self.footprint_storage_bytes - self.deposit_offset
        )

    @classmethod
    def from_serialized_bytes(cls, serialized_bytes: bytes) -> 'ServiceAccount':
        """
        GP-0.7.1-eq:D.2 deserializes bytes into a ServiceAccount

        Parameters
        ----------
        serialized_bytes: bytes

        Returns
        -------
        ServiceAccount
        """
        version = serialized_bytes[0]

        if version > 0:
            raise ValueError(f'Unsupported service account version "{version}"')

        return ServiceAccount(
            code_hash=serialized_bytes[1:33],
            balance=U64.decode(JamBytes(serialized_bytes[33:41])),
            gas_limit_accumulate=U64.decode(JamBytes(serialized_bytes[41:49])),
            gas_limit_on_transfer=U64.decode(JamBytes(serialized_bytes[49:57])),
            footprint_storage_bytes=U64.decode(JamBytes(serialized_bytes[57:65])),
            deposit_offset=U64.decode(JamBytes(serialized_bytes[65:73])),
            footprint_storage_items=U32.decode(JamBytes(serialized_bytes[73:77])),
            creation_slot=U32.decode(JamBytes(serialized_bytes[77:81])),
            last_accumulation_slot=U32.decode(JamBytes(serialized_bytes[81:85])),
            parent_service=U32.decode(JamBytes(serialized_bytes[85:89])),
            storage_items={},
            preimages={},
            preimage_availability={},
        )

    def to_serialized_bytes(self) -> bytes:
        """
        GP-0.7.1-eq:D.2 Serialize a ServiceAccount to bytes.

        Returns
        -------
        bytes
        """
        serialized_bytes = b'\x00'  # Version
        serialized_bytes += self.code_hash
        serialized_bytes += U64.encode(self.balance).to_bytes()
        serialized_bytes += U64.encode(self.gas_limit_accumulate).to_bytes()
        serialized_bytes += U64.encode(self.gas_limit_on_transfer).to_bytes()
        serialized_bytes += U64.encode(self.footprint_storage_bytes).to_bytes()
        serialized_bytes += U64.encode(self.deposit_offset).to_bytes()
        serialized_bytes += U32.encode(self.footprint_storage_items).to_bytes()
        serialized_bytes += U32.encode(self.creation_slot).to_bytes()
        serialized_bytes += U32.encode(self.last_accumulation_slot).to_bytes()
        serialized_bytes += U32.encode(self.parent_service).to_bytes()

        return serialized_bytes

    def update_from(self, service_account: "ServiceAccount"):
        self.footprint_storage_bytes = service_account.footprint_storage_bytes
        self.footprint_storage_items = service_account.footprint_storage_items
        self.balance = service_account.balance
        self.code_hash = service_account.code_hash
        self.gas_limit_accumulate = service_account.gas_limit_accumulate
        self.gas_limit_on_transfer = service_account.gas_limit_on_transfer
        self.deposit_offset = service_account.deposit_offset
        self.creation_slot = service_account.creation_slot
        self.last_accumulation_slot = service_account.last_accumulation_slot
        self.parent_service = service_account.parent_service

    def update_footprint_add_storage_item(self, key_len: int, value_len: int) -> None:
        """
        GP-0.7.1-eq:9.8
        """
        self.footprint_storage_items += 1
        self.footprint_storage_bytes += 34 + key_len + value_len

    def update_footprint_remove_storage_item(self, key_len: int, value_len: int) -> None:
        """
        GP-0.7.1-eq:9.8
        """
        self.footprint_storage_items -= 1
        self.footprint_storage_bytes -= 34 + key_len + value_len

    def update_footprint_update_storage_item(self, old_value_len: int, new_value_len: int) -> None:
        """
        GP-0.7.1-eq:9.8
        """
        self.footprint_storage_bytes += new_value_len - old_value_len

    def update_footprint_add_preimage(self, size: int) -> None:
        """
        GP-0.7.1-eq:9.8
        """
        self.footprint_storage_items += 2
        self.footprint_storage_bytes += 81 + size

    def update_footprint_remove_preimage(self, size: int) -> None:
        """
        GP-0.7.1-eq:9.8
        """
        self.footprint_storage_items -= 2
        self.footprint_storage_bytes -= 81 + size


class ServiceAccountMap(StorageMap):
    def __init__(self, storage_engine: StorageEngine):

        def storage_value_func(data: bytes, key: int) -> ServiceAccount:
            service_account = ServiceAccount.from_serialized_bytes(data)
            service_account.storage_items = StorageItemMap(storage_engine=storage_engine, service_account_id=key)
            service_account.preimages = PreimageMap(storage_engine=storage_engine, service_account_id=key)
            service_account.preimage_availability = PreimageAvailabilityMap(
                storage_engine=storage_engine, service_account_id=key
            )
            return service_account

        super().__init__(
            storage_engine=storage_engine,
            storage_key_func=state_key_constructor_service_account,
            storage_value_func=storage_value_func
        )


@dataclass
class PendingChanges:
    service_accounts: Dict[int, Optional[ServiceAccount]] = field(default_factory=dict)
    storage_items: Dict[Tuple[int, bytes], Optional[bytes]] = field(default_factory=dict)
    preimages: Dict[Tuple[int, bytes], Optional[bytes]] = field(default_factory=dict)
    preimages_availability: Dict[Tuple[int, bytes, int], Optional[List[int]]]= field(default_factory=dict)


@dataclass
class ServicesState(State, Serializable):
    """
    GP-0.7.1-eq:9.2 (δ) | Services partition of the overall state.

    Attributes
    ----------
    services: Dict(U32,ServiceAccount)
        GP-0.7.1-eq:9.1,9.2 (δ, blackboard_N_S, blackboard_A) | Services dict. Provides service account data for a
        service account index.
    """
    services: Union[Dict[int, ServiceAccount], ServiceAccountMap] = field(
        default_factory=dict,
        metadata={'codec': Map(U32, ServiceAccount.to_codec_def())}
    )

    def __deepcopy__(self, memo):
        # Create a new instance without calling __init__
        new_obj = self.__class__.__new__(self.__class__)
        memo[id(self)] = new_obj

        # Only copy attribute 'services'
        new_obj.services = deepcopy(self.services, memo)

        new_obj.pending_changes = deepcopy(self.pending_changes, memo)

        # Set new storage engine
        new_obj.set_state_storage(self.state_storage)

        return new_obj

    def set_state_storage(self, state: StateStorage):
        setattr(self, '_state_storage', state)

    @property
    def state_storage(self) -> Optional[StateStorage]:
        return getattr(self, '_state_storage', None)

    @property
    def pending_changes(self) -> Optional[PendingChanges]:
        return getattr(self, '_pending_changes', None)

    @pending_changes.setter
    def pending_changes(self, pending_changes: PendingChanges):
        setattr(self, '_pending_changes', pending_changes)

    def service_exists(self, service_id: int, check_pending_changes: bool = True) -> bool:
        try:
            self.retrieve_service_account(service_id, check_pending_changes=check_pending_changes)
            return True
        except StateKeyNoResult:
            return False

    def retrieve_service_account(
            self,
            service_account_id: int,
            check_pending_changes: bool = True,
    ) -> ServiceAccount:

        # Sanity checks
        if service_account_id >= 2**32:
            raise StateKeyNoResult(f'Service account not found for ID {service_account_id}')

        service_account = None

        if check_pending_changes and service_account_id in self.pending_changes.service_accounts:
            service_account = deepcopy(self.pending_changes.service_accounts[service_account_id])
        else:
            if self.state_storage is None:
                raise ValueError('state_storage must be set before retrieving preimage')

            storage_key = state_key_constructor_service_account(service_account_id)
            DEBUG and logging.debug(f'retrieve_service_account({service_account_id}): {storage_key.hex()}')

            data = self.state_storage.get(storage_key)
            if data:
                service_account = ServiceAccount.from_serialized_bytes(data)

        if service_account is None:
            raise StateKeyNoResult(f'Service account not found for ID {service_account_id}')

        return service_account

    def store_service_account(self, service_account_id: int, service_account: ServiceAccount, save_to_tx=False):
        """
        Stores a service account

        Parameters
        ----------
        service_account_id
        service_account
        save_to_tx

        Returns
        -------

        """

        # Sanity checks
        if service_account_id >= 2 ** 32:
            raise StateKeyNoResult(f'Service account not found for ID {service_account_id}')

        if service_account_id not in self.pending_changes.service_accounts or self.pending_changes.service_accounts[service_account_id] is None:
            self.pending_changes.service_accounts[service_account_id] = service_account
        else:
            self.pending_changes.service_accounts[service_account_id].update_from(service_account)

        state_key = state_key_constructor_service_account(service_account_id)

        if save_to_tx:

            if self.state_storage is None:
                raise ValueError('state_storage must be set before storing a service account')

            data = service_account.to_serialized_bytes()

            self.state_storage.put(state_key, data)

        DEBUG and logging.debug(f'store_service_account({service_account_id}): code_hash={service_account.code_hash.hex()} balance={service_account.balance} threshold_balance={service_account.threshold_balance} min_item_gas={service_account.gas_limit_accumulate} min_memo_gas={service_account.gas_limit_on_transfer} f_i={service_account.footprint_storage_items} f_b={service_account.footprint_storage_bytes} commit={save_to_tx}')


    def delete_service_account(self, service_account_id: int, save_to_tx=False):
        """
        Deletes a service account

        Parameters
        ----------
        service_account_id

        Returns
        -------

        """

        # Sanity checks
        if service_account_id >= 2 ** 32:
            raise StateKeyNoResult(f'Service account not found for ID {service_account_id}')

        state_key = state_key_constructor_service_account(service_account_id)

        if save_to_tx:

            if self.state_storage is None:
                raise ValueError('state_storage must be set before deleting service account data')

            self.state_storage.delete(state_key)
        else:
            self.pending_changes.service_accounts[service_account_id] = None


        DEBUG and logging.debug(f'delete_service_account({service_account_id}) storage_key={state_key.hex()} commit={save_to_tx}')


    def retrieve_preimage(self, service_account_id: int, preimage_hash: bytes) -> bytes:
        """
        Host-function OMEGA_L (lookup)

        Parameters
        ----------
        service_account_id
        preimage_hash
        storage_engine

        Returns
        -------
        bytes
        """

        if (service_account_id, preimage_hash) in self.pending_changes.preimages:
            preimage = self.pending_changes.preimages[(service_account_id, preimage_hash)]
        else:
            if self.state_storage is None:
                raise ValueError('state_storage must be set before retrieving preimage')

            storage_key = state_key_constructor_preimage(service_account_id, preimage_hash)
            DEBUG and logging.debug(f'retrieve_preimage({service_account_id}, {preimage_hash.hex()}): {storage_key.hex()}')

            preimage = self.state_storage.get(storage_key)

        if preimage is None:
            raise StateKeyNoResult(f'Preimage not found for hash {preimage_hash}')

        return preimage

    #GP-0.7.1-eq:9.7 (historical lookup)
    def historical_preimage_lookup(self, service_account_id: int, timeslot: int, preimage_hash: bytes) -> Optional[bytes]:
        """
        historical lookup
        GP-0.7.1-eq:9.5
        GP-0.7.1-eq:9.7


        Parameters
        ----------
        service_account
        timeslot
        preimage_hash
        storage_engine

        Returns
        -------
        bytes
        """

        try:
            preimage = self.retrieve_preimage(service_account_id, preimage_hash)
            preimage_availability = self.retrieve_preimage_availability(service_account_id, preimage_hash, len(preimage))

            # GP-0.6.4-eq:9.7
            def is_preimage_available() -> bool:
                if len(preimage_availability) == 0:
                    return False
                elif len(preimage_availability) == 1:
                    return preimage_availability[0] <= timeslot
                elif len(preimage_availability) == 2:
                    return preimage_availability[0] <= timeslot < preimage_availability[1]
                elif len(preimage_availability) == 3:
                    return preimage_availability[0] <= timeslot < preimage_availability[1] or preimage_availability[2] <= timeslot

                return False

            if is_preimage_available():
                return preimage

        except StateKeyNoResult:
            pass

        return None

    def is_preimage_needed(self, preimage: Preimage) -> bool:
        """
        GP-0.7.1-eq:12.35 | Is preimage needed

        Parameters
        ----------
        preimage: Preimage

        Returns
        -------
        bool
        """
        preimage_hash = blake2b_256_hash(preimage.blob)

        # Check if preimage isn't already available
        if self.preimage_exists(preimage.requester, preimage_hash):
            return False

        # Check if preimage is requested
        try:
            preimage_availability = self.retrieve_preimage_availability(
                preimage.requester, preimage_hash, len(preimage.blob)
            )
            return preimage_availability == []
        except StateKeyNoResult:
            return False

    def store_preimage(self, service_account_id: int, preimage_blob: bytes, save_to_tx=False):
        """
        Stores a preimage

        Parameters
        ----------
        service_account_id
        preimage_blob

        Returns
        -------
        None
        """

        preimage_hash = blake2b_256_hash(preimage_blob)

        self.pending_changes.preimages[(service_account_id, preimage_hash)] = preimage_blob

        storage_key = state_key_constructor_preimage(service_account_id, preimage_hash)

        if save_to_tx:

            if self.state_storage is None:
                raise ValueError('state_storage must be set before storing preimage data')

            self.state_storage.put(storage_key, preimage_blob)

        DEBUG and logging.debug(f'store_preimage({service_account_id}, {preimage_hash.hex()}): sk={storage_key.hex()} commit={save_to_tx}')


    def preimage_exists(self, service_account_id: int, preimage_hash: bytes) -> bool:
        try:
            self.retrieve_preimage(service_account_id, preimage_hash)
            return True
        except StateKeyNoResult:
            return False


    def retrieve_preimage_availability(
            self, service_account_id: int, preimage_hash: bytes, preimage_length: int
    ) -> List[int]:

        preimage_availability = None

        if service_account_id < 2**32 and preimage_length < 2**32:

            if (service_account_id, preimage_hash, preimage_length) in self.pending_changes.preimages_availability:
                preimage_availability = self.pending_changes.preimages_availability[(service_account_id, preimage_hash, preimage_length)]
            else:
                if self.state_storage is None:
                    raise ValueError('state_storage must be set before retrieving preimage availability')

                storage_key = state_key_constructor_preimage_availability(service_account_id, preimage_hash, preimage_length)

                data = self.state_storage.get(storage_key)
                if data:
                    availability = Vec(U32).new()
                    availability.decode(JamBytes(data))
                    preimage_availability = availability.value

        if preimage_availability is None:
            raise StateKeyNoResult(
                f'Preimage availability not found for hash {preimage_hash} and length {preimage_length}'
            )

        DEBUG and logging.debug(
            f'retrieve_preimage_availability({service_account_id}, {preimage_hash.hex()}, {preimage_length}): v={preimage_availability}'
            )

        return preimage_availability


    def store_preimage_availability(
            self, service_account_id: int, preimage_hash: bytes, preimage_length: int, value: List[int], save_to_tx=False
    ):

        storage_key = state_key_constructor_preimage_availability(service_account_id, preimage_hash, preimage_length)

        self.pending_changes.preimages_availability[(service_account_id, preimage_hash, preimage_length)] = value

        if save_to_tx:

            if self.state_storage is None:
                raise ValueError('state_storage must be set before storing preimage availability data')

            availability = Vec(U32).new()
            data = availability.encode(value)


            self.state_storage.put(storage_key, data.to_bytes())

        DEBUG and logging.debug(
            f'store_preimage_availability({service_account_id}, {preimage_hash.hex()}, {preimage_length}): v={value} {storage_key.hex()}'
        )


    def delete_preimage(self, service_account_id: int, preimage_hash: bytes, save_to_tx=False):


        storage_key = state_key_constructor_preimage(service_account_id, preimage_hash)

        if save_to_tx:

            if self.state_storage is None:
                raise ValueError('state_storage must be set before deleting preimage availability data')

            self.state_storage.delete(storage_key)
        else:
            self.pending_changes.preimages[(service_account_id, preimage_hash)] = None

        DEBUG and logging.debug(
            f'delete_preimage({service_account_id}, {preimage_hash.hex()}): {storage_key.hex()} commit={save_to_tx}'
            )


    def delete_preimage_availability(
            self, service_account_id: int, preimage_hash: bytes, preimage_length: int, save_to_tx=False
    ):

        storage_key = state_key_constructor_preimage_availability(service_account_id, preimage_hash, preimage_length)

        if save_to_tx:

            if self.state_storage is None:
                raise ValueError('state_storage must be set before deleting preimage availability data')

            self.state_storage.delete(storage_key)

        else:
            self.pending_changes.preimages_availability[(service_account_id, preimage_hash, preimage_length)] = None

        DEBUG and logging.debug(
            f'delete_preimage_availability({service_account_id}, {preimage_hash.hex()}, {preimage_length}): {storage_key.hex()}'
        )


    def retrieve_storage_item(
            self, service_account_id: int, storage_item_hash: bytes
    ) -> bytes:
        """
        Host-function: OMEGA_R (read)

        Parameters
        ----------
        service_account_id: int
        storage_item_hash: bytes

        Returns
        -------
        bytes
        """

        if (service_account_id, storage_item_hash) in self.pending_changes.storage_items:
            data = self.pending_changes.storage_items[(service_account_id,storage_item_hash)]
        else:
            if self.state_storage is None:
                raise ValueError('state_storage must be set before retrieving storage items')

            storage_key = state_key_constructor_storage_item(service_account_id, storage_item_hash)
            data = self.state_storage.get(storage_key)

        if data is None:
            raise StateKeyNoResult(
                f'Storage item not found for hash {storage_item_hash} for service account {service_account_id}'
            )

        DEBUG and logging.debug(
            f'retrieve_storage_item(s={service_account_id}, k={storage_item_hash.hex()}): v={data.hex()}'
            )

        return data

    def store_storage_item(self, service_account_id: int, storage_key: bytes, value: bytes, save_to_tx=False):
        """
        Store a storage item in the storage engine
        """

        self.pending_changes.storage_items[(service_account_id, storage_key)] = value

        state_key = state_key_constructor_storage_item(service_account_id, storage_key)

        if save_to_tx:
            if self.state_storage is None:
                raise ValueError('state_storage must be set before storing storage items')
            self.state_storage.put(state_key, value)

        DEBUG and logging.debug(f'store_storage_item(s={service_account_id}, k={storage_key.hex()}): v={value.hex()} state_key={state_key.hex()} [commit={save_to_tx}]')


    def delete_storage_item(self, service_account_id: int, storage_item_hash: bytes, save_to_tx=False):
        """
        Delete a storage item in the storage engine
        """

        storage_key = state_key_constructor_storage_item(service_account_id, storage_item_hash)

        if save_to_tx:

            if self.state_storage is None:
                raise ValueError('state_storage must be set before deleting storage items')

            self.state_storage.delete(storage_key)

        else:
            self.pending_changes.storage_items[(service_account_id, storage_item_hash)] = None

        DEBUG and logging.debug(
            f'delete_storage_item(s={service_account_id}, k={storage_item_hash.hex()}): state_key={storage_key.hex()} [commit={save_to_tx}]'
            )

    def add_pending_changes(self, pending_changes: PendingChanges = None):

        if pending_changes is None:
            pending_changes = self.pending_changes

        for id, service_account in pending_changes.service_accounts.items():
            if id in self.services:
                if service_account is None:
                    del self.services[id]
                else:
                    self.services[id].update_from(service_account)
            elif service_account is not None:
                self.services[id] = service_account

        for (service_id, storage_hash), storage_item in pending_changes.storage_items.items():
            if storage_item is not None:
                self.services[service_id].storage_items[storage_hash] = storage_item

        for (service_id, preimage_hash), preimage_blob in pending_changes.preimages.items():
            if preimage_blob is not None:
                self.services[service_id].preimages[preimage_hash] = preimage_blob

        for (service_id, preimage_hash, preimage_size), availability in pending_changes.preimages_availability.items():
            if availability is not None:
                self.services[service_id].preimage_availability[(preimage_hash, preimage_size)] = availability



@dataclass
class AssurancesState(State, Serializable):
    """
    GP-0.7.1-eq:11.1 (ρ) | Assurances partition of the overall state.

    Attributes
    ----------
    assurances: Vec(Option(Assurance))
        GP-0.7.1-eq:11.1 (ρ) | A collection of optional assurances per core.
    """
    assurances: List[Optional[Assurance]] = field(
        metadata={'codec': Array(Option(Assurance.to_codec_def()), CORE_COUNT)}
    )


@dataclass
class AuthorizerQueuesState(State, Serializable):
    """
    GP-0.7.1-eq:8.1 (𝜙) | A collections of queues of authorizations for all cores.

    Attributes
    ----------
    authorizer_queues: Array(Array(H256,constant_Q),constant_C)
        GP-0.7.1-eq:8.1 (𝜙) | A collections of queues of authorizations for all cores.
    """
    authorizer_queues: List[List[bytes]] = field(
        metadata={'codec': Array(Array(H256, MAXIMUM_AUTHORIZATION_QUEUE_ITEMS), CORE_COUNT)}
    )


@dataclass
class PrivilegedServicesState(State, Serializable):
    """
    GP-0.7.1-eq:9.9 (χ) | The PrivilegedServices partition of the overall state.

    Attributes
    ----------
    manager: U32
        GP-0.7.1-eq:9.9 (χ_M) | The service index of the manager service. I.e. the service that allows state transitions
        of PrivilegedServices (χ).
    assigners: Array(U32, Constant_C)
        GP-0.7.1-eq:9.9 (χ_A) | The service index of the assign service. I.e. the service that allows state transitions
        of AuthorizerQueue (𝜙).
    delegator: U32
        GP-0.7.1-eq:9.9 (χ_V) | The service index of the designate service. I.e. the service that allows state
        transitions of ValidatorQueue (ι).
    registrar: U32
        GP-0.7.1-eq:9.9 (χ_R) | The service index of the registrar service.
    always_accumulators: Dict(U32,U64)
        GP-0.7.1-eq:9.9 (χ_Z) | Auto Accumulate Services dict. Provides gas limit data for a service account index.
    """
    manager: int = field(metadata={'codec': U32})
    assigners: List[int] = field(metadata={'codec': Array(U32, CORE_COUNT)})
    delegator: int = field(metadata={'codec': U32})
    registrar: int = field(metadata={'codec': U32})
    always_accumulators: Dict[int, int] = field(metadata={'codec': Map(U32, U64)})


@dataclass
class DisputesState(State, Serializable):
    """
    GP-0.7.1-eq:10.1 (ψ) | A collection of judgements of validators over the validity of work reports.

    Attributes
    ----------
    good_set: Vec(H256)
        GP-0.7.1-eq:10.1,10.16 (ψ_G) | A collection of work reports hashes with a good verdict.
    bad_set: Vec(H256)
        GP-0.7.1-eq:10.1,10.17 (ψ_B) | A collection of work reports hashes with a bad verdict.
    wonky_set: Vec(H256)
        GP-0.7.1-eq:10.1,10.18 (ψ_W) | A collection of work reports hashes with a wonky verdict.
    offenders: Vec(H256)
        GP-0.7.1-eq:10.1,10.19 (ψ_O) | A collection Edwards 25519 keys for validators found guilty of offending.
    """
    good_set: List[bytes] = field(metadata={'codec': Vec(H256)})
    bad_set: List[bytes] = field(metadata={'codec': Vec(H256)})
    wonky_set: List[bytes] = field(metadata={'codec': Vec(H256)})
    offenders: List[bytes] = field(metadata={'codec': Vec(H256)})


@dataclass
class ActivityRecord(Serializable):
    """
    GP-0.7.1-eq:13.2 (π_V,π_L) | A set of cumulative metrics for a single validator in a single epochs.

    Attributes
    ----------
    blocks: U32
        GP-0.7.1-eq:13.2 (b) | The number of blocks produced by the validator.
    tickets: U32
        GP-0.7.1-eq:13.2 (t) | The number of tickets introduced by the validator.
    pre_images: U32
        GP-0.7.1-eq:13.2 (p) | The number of preimages introduced by the validator.
    pre_images_size: U32
        GP-0.7.1-eq:13.2 (d) | The number of total number of bytes across all preimages introduced by the validator.
    guarantees: U32
        GP-0.7.1-eq:13.2 (g) | The number of reports guaranteed by the validator.
    assurances: U32
        GP-0.7.1-eq:13.2 (a) | The number of availability assurances made by the validator.
    """
    blocks: int = field(metadata={'codec': U32})
    tickets: int = field(metadata={'codec': U32})
    pre_images: int = field(metadata={'codec': U32})
    pre_images_size: int = field(metadata={'codec': U32})
    guarantees: int = field(metadata={'codec': U32})
    assurances: int = field(metadata={'codec': U32})


@dataclass
class CoreActivityRecord(Serializable):
    """
    GP-0.7.1-eq:13.6 (π_C) | Core activity statistics

    Attributes
    ----------
    da_load: VarInt64
        GP-0.7.1-eq:13.6 (d) | Amount of bytes which are placed into either Audits or Segments DA.
    popularity: VarInt64
        GP-0.7.1-eq:13.6 (p) | Number of validators which formed super-majority for assurance.
    imports: VarInt64
        GP-0.7.1-eq:13.6 (i) | Number of segments imported from DA made by core for reported work.
    exports: VarInt64
        GP-0.7.1-eq:13.6 (x) | Number of segments exported into DA made by core for reported work.
    extrinsic_size: VarInt64
        GP-0.7.1-eq:13.6 (z) | Total size of extrinsic data used by core for reported work.
    extrinsic_count: VarInt64
        GP-0.7.1-eq:13.6 (e) | Total number of extrinsics used by core for reported work.
    bundle_size: VarInt64
        GP-0.7.1-eq:13.6 (l) | The work-bundle size. This is the size of data being placed into Audits DA by the core.
    gas_used: VarInt64
         GP-0.7.1-eq:13.6 (u) | Total gas consumed by core for reported work. Includes all refinement and authorizations
    """
    da_load: int = field(metadata={'codec': VarInt64})
    popularity: int = field(metadata={'codec': VarInt64})
    imports: int = field(metadata={'codec': VarInt64})
    extrinsic_count: int = field(metadata={'codec': VarInt64})
    extrinsic_size: int = field(metadata={'codec': VarInt64})
    exports: int = field(metadata={'codec': VarInt64})
    bundle_size: int = field(metadata={'codec': VarInt64})
    gas_used: int = field(metadata={'codec': VarInt64})

    def update(self,
               core_index: int,
               incoming_work_reports: List[WorkReport],
               available_work_reports: List[WorkReport],
               extrinsic_assurances: List['ExtrinsicAssurance']
    ):
        """
         GP-0.7.1-eq:13.8 | Updating core stats for specified core
        """
        self.gas_used = 0
        self.imports = 0
        self.extrinsic_count = 0
        self.extrinsic_size = 0
        self.exports = 0
        self.bundle_size = 0
        self.da_load = 0
        self.popularity = 0

        if incoming_work_reports:
            self.update_from_incoming_work_reports(core_index, incoming_work_reports)

        if available_work_reports:
            self.update_from_available_work_reports(core_index, available_work_reports)

        self.popularity = sum([1 for a in extrinsic_assurances if core_index in a.cores_engaged])


    def update_from_incoming_work_reports(self, core_index: int, incoming_work_reports: List[WorkReport]):
        """
        GP-0.7.1-eq:13.9 (R) | Updating core stats using incoming work-reports (bold_I) in extrinsic data (GP-0.7.0-eq:11.28)
        """
        for w in incoming_work_reports:
            if w.core_index == core_index:
                self.bundle_size += w.package_spec.length
                for r in w.results:
                    self.imports += r.refine_load.imports
                    self.extrinsic_count += r.refine_load.extrinsic_count
                    self.extrinsic_size += r.refine_load.extrinsic_size
                    self.exports += r.refine_load.exports
                    self.gas_used += r.refine_load.gas_used

    def update_from_available_work_reports(self, core_index: int, available_work_reports: List[WorkReport]):
        """
        GP-0.7.1-eq:13.11 (D) | Updating core stats using available work-reports (bold_R) (GP-0.7.0-eq:11.16)
        """
        self.da_load = sum([
            w.package_spec.length + EC_SEGMENT_SIZE * ceil(w.package_spec.exports_count * 65/64)
            for w in available_work_reports if w.core_index == core_index
        ])

@dataclass
class ServiceActivityRecord(Serializable):
    """
    GP-0.7.1-eq:13.7 (π_S) | A collection of statistics for all validators for two epochs.

    Attributes
    ----------
    provided_count: VarInt64
        GP-0.7.1-eq:13.7 (p_0) | Number of preimages provided to this service.
    provided_size: VarInt64
        GP-0.7.1-eq:13.7 (p_1)| Total size of preimages provided to this service.
    refinement_count: VarInt64
        GP-0.7.1-eq:13.7 (r_0)| Number of work-items refined by service for reported work.
    refinement_gas_used: VarInt64
        GP-0.7.1-eq:13.7 (r_1)| Amount of gas used for refinement by service for reported work.
    imports: VarInt64
        GP-0.7.1-eq:13.7 (i) | Number of segments imported from the DL by service for reported work.
    extrinsic_count: VarInt64
        GP-0.7.1-eq:13.7 (x) | Total number of extrinsics used by service for reported work.
    extrinsic_size: VarInt64
        GP-0.7.1-eq:13.7 (z) | Total size of extrinsics used by service for reported work.
    exports: VarInt64
        GP-0.7.1-eq:13.7 (e) | Number of segments exported into the DL by service for reported work.
    accumulate_count: VarInt64
        GP-0.7.1-eq:13.7 (a_0) | Number of work-items accumulated by service.
    accumulate_gas_used: VarInt64
        GP-0.7.1-eq:13.7 (a_1) | Amount of gas used for accumulation by service.
    """
    provided_count: int = field(metadata={'codec': VarInt64}, default=0)
    provided_size: int = field(metadata={'codec': VarInt64}, default=0)
    refinement_count: int = field(metadata={'codec': VarInt64}, default=0)
    refinement_gas_used: int = field(metadata={'codec': VarInt64}, default=0)
    imports: int = field(metadata={'codec': VarInt64}, default=0)
    extrinsic_count: int = field(metadata={'codec': VarInt64}, default=0)
    extrinsic_size: int = field(metadata={'codec': VarInt64}, default=0)
    exports: int = field(metadata={'codec': VarInt64}, default=0)
    accumulate_count: int = field(metadata={'codec': VarInt64}, default=0)
    accumulate_gas_used: int = field(metadata={'codec': VarInt64}, default=0)


@dataclass
class StatisticsState(State, Serializable):
    """
    GP-0.7.1-eq:13.1 (π) | A collection of statistics for all validators for two epochs.

    Attributes
    ----------

    vals_current: Array(Statistic,constant_V)
        GP-0.7.1-eq:13.1 (π_V) | A collection of statistics for all validators for current epoch.
    vals_last: Array(Statistic,constant_V)
        GP-0.7.1-eq:13.1 (π_L) | A collection of statistics for all validators for last epoch.
    cores: Array(Statistic,constant_C)
        GP-0.7.1-eq:13.1 (π_C) | Core activity statistics for last block.
    services: Map(U32, ServiceActivityRecord)
        GP-0.7.1-eq:13.1 (π_S) | Service activity statistics for last block.
    """
    vals_current: List[ActivityRecord] = field(metadata={'codec': Array(ActivityRecord.to_codec_def(), VALIDATOR_COUNT)})
    vals_last: List[ActivityRecord] = field(metadata={'codec': Array(ActivityRecord.to_codec_def(), VALIDATOR_COUNT)})
    cores: List[CoreActivityRecord] = field(metadata={
        'codec': Array(CoreActivityRecord.to_codec_def(), CORE_COUNT)
    })
    services: Dict[int, ServiceActivityRecord] = field(metadata={
        'codec': Map(U32, ServiceActivityRecord.to_codec_def())
    })

    @classmethod
    def default(cls) -> 'StatisticsState':
        return cls(
            vals_current=[ActivityRecord(0, 0, 0, 0, 0, 0) for _ in range(VALIDATOR_COUNT)],
            vals_last=[ActivityRecord(0, 0, 0, 0, 0, 0) for _ in range(VALIDATOR_COUNT)],
            cores=[CoreActivityRecord(0, 0, 0, 0, 0, 0, 0, 0) for _ in range(CORE_COUNT)],
            services={},
        )



@dataclass
class AccumulationQueueWorkPackage(Serializable):
    """
    GP-0.7.1-eq:13.1 (ω) | A not yet accumulated work package.

    Attributes
    ----------
    report: WorkReport
        GP-0.7.1-eq:12.3 (blackboard_R) | Work Report.
    dependencies: Vec(H256)
        GP-0.7.1-eq:12.3 ({blackboard_H}) | Set of Work Package hashes.
    """
    report: WorkReport = field(metadata={'codec': WorkReport.to_codec_def()})
    dependencies: List[bytes] = field(metadata={'codec': Vec(H256)})


@dataclass
class AccumulationQueueState(State, Serializable):
    """
    GP-0.7.1-eq:12.3 (ω) | A collection of unaccumulated work packages.

    Attributes
    ----------

    accumulation_queue: Array(Vec(AccumulationQueueWorkPackage),constant_E)
        GP-0.7.1-eq:12.3 (ω) | A collection of unaccumulated work packages.
    """
    accumulation_queue: List[List[AccumulationQueueWorkPackage]] = field(
        metadata={'codec': Array(Vec(AccumulationQueueWorkPackage.to_codec_def()), EPOCH_TIMESLOTS)}
    )


@dataclass
class AccumulationHistoryState(State, Serializable):
    """
    GP-0.7.1-eq:12.1 (ξ) | A history of what has been accumulated.

    Attributes
    ----------

    accumulation_history: Array(Vec(H256),constant_E)
        GP-0.7.1-eq:12.1 (ξ) | A history of what has been accumulated.
    """
    accumulation_history: List[List[bytes]] = field(
        metadata={'codec': Array(Vec(H256), EPOCH_TIMESLOTS)}
    )


class TupleMap(Map):
    def to_serializable_obj(self, value_object: list):
        return [(key.to_serializable_obj(), value.to_serializable_obj()) for key, value in value_object]

@dataclass
class BeefyCommitmentMap(State, Serializable):
    """
    GP-0.7.1-eq:7.4 (θ) | Service-indexed commitment to the accumulation output

    Attributes
    ----------
    beefy_commitment_map: List[Tuple[int, bytes]]
        GP-0.7.1-eq:7.4 (θ) | Beefy Commitment Map dictionary. Provides accumulation
        result TreeRoot for accumulated services.
    """
    beefy_commitment_map: Set[Tuple[int, bytes]] = field(default_factory=set, metadata={'codec': TupleMap(U32, H256)})

    def add_accumulation_output(self, service_index: int, accumulation_output: bytes):
        self.beefy_commitment_map.add((service_index, accumulation_output))

    def get_accumulation_outputs(self):
        return sorted(self.beefy_commitment_map)

    def get_accumulate_root(self) -> bytes:
        """
        GP-0.7.1-eq:7.6,7.7 (r) | The accumulation-result tree root of the beefy commitment map.

        Returns
        -------
        bytes
        """
        items = self.get_accumulation_outputs()
        data = [k.to_bytes(4, byteorder='little') + v for k, v in items]
        return WellBalancedMerkleTree(data, hash_function=keccak_256_hash).root()


@dataclass
class JamState(State, Serializable):
    """
    GP-0.7.1-eq:4.4 (σ) | Logically partitioned state into several largely independent segments which can help both
    visual clutter within the protocol description and provide formality over elements of computation which may be
    simultaneously calculated (i.e. parallelized).

    Attributes
    ----------
    authorizer_pools: AuthorizerPoolsState
        GP-0.7.1-eq:4.4 (α) | AuthorizerPool partition of the overall state
    recent_history: RecentHistoryState
        GP-0.7.1-eq:4.4 (β) | RecentHistory partition of the overall state
    safrole: SafroleState
        GP-0.7.1-eq:4.4 (γ) | Safrole partition of the overall state
    services: ServicesState
        GP-0.7.1-eq:4.4 (δ) | Services partition of the overall state
    entropy: EntropyState
        GP-0.7.1-eq:4.4 (η) | Entropy partition of the overall state
    validator_queue: ValidatorQueueState
        GP-0.7.1-eq:4.4 (ι) | ValidatorQueue partition of the overall state
    validator_pool: ValidatorPoolState
        GP-0.7.1-eq:4.4 (κ) | ValidatorPool partition of the overall state
    validator_archive: ValidatorArchiveState
        GP-0.7.1-eq:4.4 (λ) | ValidatorArchive partition of the overall state
    assurances: AssurancesState
        GP-0.7.1-eq:4.4 (ρ) | Assurances partition of the overall state
    timeslot: TimeslotState
        GP-0.7.1-eq:4.4 (τ) | Timeslot partition of the overall state
    authorizer_queues: AuthorizerQueuesState
        GP-0.7.1-eq:4.4 (𝜙) | AuthorizerQueue partition of the overall state
    privileged_services: PrivilegedServicesState
        GP-0.7.1-eq:4.4 (χ) | PrivilegedServices partition of the overall state
    disputes: DisputesState
        GP-0.7.1-eq:4.4 (ψ) | Disputes partition of the overall state
    statistics: StatisticsState
        GP-0.7.1-eq:4.4 (π) | Statistics partition of the overall state
    accumulation_queue: AccumulationQueueState
        GP-0.7.1-eq:4.4 (ω) | AccumulationQueue partition of the overall state
    accumulation_history: AccumulationHistoryState
        GP-0.7.1-eq:4.4 (ξ) | AccumulationHistory partition of the overall state
    recent_accumulation_outputs: BeefyCommitmentMap
        GP-0.7.1-eq:4.4 (θ) | The most recent Accumulation outputs
    """
    authorizer_pools: AuthorizerPoolsState = field(metadata={'codec': AuthorizerPoolsState.to_codec_def()})
    recent_history: RecentHistoryState = field(metadata={'codec': RecentHistoryState.to_codec_def()})
    safrole: SafroleState = field(metadata={'codec': SafroleState.to_codec_def()})
    services: ServicesState = field(metadata={'codec': ServicesState.to_codec_def()})
    entropy: EntropyState = field(metadata={'codec': EntropyState.to_codec_def()})
    validator_queue: ValidatorQueueState = field(metadata={'codec': ValidatorQueueState.to_codec_def()})
    validator_pool: ValidatorPoolState = field(metadata={'codec': ValidatorPoolState.to_codec_def()})
    validator_archive: ValidatorArchiveState = field(metadata={'codec': ValidatorArchiveState.to_codec_def()})
    assurances: AssurancesState = field(metadata={'codec': AssurancesState.to_codec_def()})
    timeslot: TimeslotState = field(metadata={'codec': TimeslotState.to_codec_def()})
    authorizer_queues: AuthorizerQueuesState = field(metadata={'codec': AuthorizerQueuesState.to_codec_def()})
    privileged_services: PrivilegedServicesState = field(metadata={'codec': PrivilegedServicesState.to_codec_def()})
    disputes: DisputesState = field(metadata={'codec': DisputesState.to_codec_def()})
    statistics: StatisticsState = field(metadata={'codec': StatisticsState.to_codec_def()})
    accumulation_queue: AccumulationQueueState = field(metadata={'codec': AccumulationQueueState.to_codec_def()})
    accumulation_history: AccumulationHistoryState = field(metadata={'codec': AccumulationHistoryState.to_codec_def()})
    recent_accumulation_outputs: BeefyCommitmentMap = field(metadata={'codec': BeefyCommitmentMap.to_codec_def()})
    block_hash: Optional[bytes] = field(metadata={'codec': H256}, default=None)
    state_root: Optional[bytes] = field(metadata={'codec': H256}, default=None)

    @classmethod
    def create_genesis_state(cls, validators: Optional[List[ValidatorData]] = None):

        if validators is None:
            validators = [ValidatorData.from_json({
                "bandersnatch": "0x5e465beb01dbafe160ce8216047f2155dd0569f058afd52dcea601025a8d161d",
                "ed25519": "0x3b6a27bcceb6a42d62a3a8d02a6f0d73653215771de243a63ac048a18b59da29",
                "bls": "0x000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000",
                "metadata": "0x0000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000"
            })] * VALIDATOR_COUNT

        return cls(
            timeslot=TimeslotState(number=0),
            entropy=EntropyState(
                entropy=[
                    validators[0].ed25519, validators[1].ed25519,
                    validators[2].ed25519, validators[3].ed25519
                ]
            ),
            safrole=SafroleState(
                ticket_accumulator=[],
                validators=validators,
                slot_sealer_series=SlotSealerSeries(keys=[validators[0].bandersnatch for _ in range(EPOCH_TIMESLOTS)]),
                ring_commitment=bytes(144),
            ),
            validator_queue=ValidatorQueueState(
                validators=validators
            ),
            validator_pool=ValidatorPoolState(
                validators=validators
            ),
            validator_archive=ValidatorArchiveState(
                validators=validators
            ),
            authorizer_pools=AuthorizerPoolsState(
                authorizer_pools=[
                    [] for _ in range(CORE_COUNT)
                ]
            ),
            recent_history=RecentHistoryState(
                recent_blocks=[],
                accumulation_output_log=[]
            ),
            services=ServicesState(services={}),
            assurances=AssurancesState(
                assurances=[None for _ in range(CORE_COUNT)]
            ),
            authorizer_queues=AuthorizerQueuesState(
                authorizer_queues=[
                    [bytes(32) for _ in range(MAXIMUM_AUTHORIZATION_QUEUE_ITEMS)] for _ in range(CORE_COUNT)
                ]
            ),
            privileged_services=PrivilegedServicesState(
                manager=0,
                assigners=[0 for _ in range(CORE_COUNT)],
                delegator=0,
                registrar=0,
                always_accumulators={}
            ),
            disputes=DisputesState(
                good_set=[],
                bad_set=[],
                wonky_set=[],
                offenders=[],
            ),
            statistics=StatisticsState.default(),
            accumulation_queue=AccumulationQueueState(
                accumulation_queue=[
                    [] for _ in range(EPOCH_TIMESLOTS)
                ]
            ),
            accumulation_history=AccumulationHistoryState(
                accumulation_history=[[] for _ in range(EPOCH_TIMESLOTS)]
            ),
            recent_accumulation_outputs=BeefyCommitmentMap()
        )


@dataclass
class DeferredTransfers(Serializable):
    """
    GP-0.7.1-eq:12.23 (Vec(blackboard_X)) | A collection of deferred transfers.

    Attributes
    ----------

    deferred_transfers: Vec(DeferredTransfer)
        GP-0.7.1-eq:12.23 (Vec(blackboard_X)) | A collection of deferred transfers.
    """
    deferred_transfers: List[DeferredTransfer] = field(metadata={'codec': Vec(DeferredTransfer.to_codec_def())})


@dataclass
class AccumulationStateComponents(Serializable):
    """
    GP-0.7.1-eq:12.16 (blackboard_S) | State components which are needed and mutable by the accumulation process.

    Attributes
    ----------
    services: ServicesState
        GP-0.7.1-eq:12.16 (bold_d) | Dictionary with services state.
    validator_queue: ValidatorQueueState
        GP-0.7.1-eq:12.16 (bold_i) | Validator Queue state.
    authorizer_queues: AuthorizerQueuesState
        GP-0.7.1-eq:12.16 (bold_q) | Authorizer Queues state.
    privileged_services: PrivilegedServicesState
        GP-0.7.1-eq:9.9 (bold_x) | Privileged Services state.
    """
    # TODO: structure change in 0.7.0 split up privileged services
    services: ServicesState = field(metadata={'codec': ServicesState.to_codec_def()})
    validator_queue: ValidatorQueueState = field(metadata={'codec': ValidatorQueueState.to_codec_def()})
    authorizer_queues: AuthorizerQueuesState = field(metadata={'codec': AuthorizerQueuesState.to_codec_def()})
    # TODO: structure change in 0.7.0 split up privileged services
    privileged_services: PrivilegedServicesState = field(metadata={'codec': PrivilegedServicesState.to_codec_def()})

    def check_service_id(self, service_id: int) -> int:
        """
        GP-0.7.1-eq:B.14 | Find an unused service id
        """
        try:
            self.services.retrieve_service_account(service_id)
            return self.check_service_id(
                (service_id - MINIMUM_PUBLIC_SERVICE_ID + 1) % (2 ** 32 - 2 ** 8 - MINIMUM_PUBLIC_SERVICE_ID) + MINIMUM_PUBLIC_SERVICE_ID
            )

        except StateKeyNoResult:
            return service_id


    def to_invocation_context(self, service_account_id: int, entropy: bytes, timeslot: int) -> 'AccumulateInvocationContext':
        """
        GP-0.7.1-eq:B.10 (I)

        entropy: eta_0
        timeslot: int post_state

        """
        # Generate new unique service id
        check_payload = int.from_bytes(blake2b_256_hash(
            service_account_id.to_bytes(length=4, byteorder='little') + entropy + timeslot.to_bytes(length=4, byteorder='little')
        )[:4], byteorder='little')

        new_service_account_id = self.check_service_id(
            (check_payload % (2**32 - MINIMUM_PUBLIC_SERVICE_ID - 2**8)) + MINIMUM_PUBLIC_SERVICE_ID
        )

        return AccumulateInvocationContext(
            context=AccumulateContextItem(
                service_account_id=service_account_id,
                state_context=deepcopy(self),
                new_service_account_id=new_service_account_id,
                deferred_transfers=[],
                invocation_output=None,
                preimages=[]
            ),
            savepoint_context=AccumulateContextItem(
                service_account_id=service_account_id,
                state_context=deepcopy(self),
                new_service_account_id=new_service_account_id,
                deferred_transfers=[],
                invocation_output=None,
                preimages=[]
            ),
            timeslot=timeslot
        )


@dataclass
class AccumulateContextItem:
    """
    GP-0.7.1-eq:B.7 (blackboard_L) | Invocation Result Context

    TODO check service_account_id in state_context.services
    """
    service_account_id: int  # s
    state_context: AccumulationStateComponents  # bold_e
    new_service_account_id: int  # i
    deferred_transfers: List[DeferredTransfer]  # bold_t
    invocation_output: Optional[bytes]  # y
    preimages: List[Tuple[int, bytes]] # bold_p


@dataclass
class AccumulateInvocationContext(InvocationContext):
    """
    GP-0.7.1-eq:B.8 (blackboard_L) | Invocation Result Context
    """
    context: AccumulateContextItem           # GP-0.7.0-eq:B.11 X_x
    savepoint_context: AccumulateContextItem # GP-0.7.0-eq:B.11 X_y
    timeslot: int # TODO how to make available?


STORAGE_KEY_MAPPING = {
    # Authorizer pool
    bytes.fromhex('01000000000000000000000000000000000000000000000000000000000000'): AuthorizerPoolsState,
    # Authorizer queue
    bytes.fromhex('02000000000000000000000000000000000000000000000000000000000000'): AuthorizerQueuesState,
    # Recent blocks
    bytes.fromhex('03000000000000000000000000000000000000000000000000000000000000'): RecentHistoryState,
    # Safrole
    bytes.fromhex('04000000000000000000000000000000000000000000000000000000000000'): SafroleState,
    # Disputes
    bytes.fromhex('05000000000000000000000000000000000000000000000000000000000000'): DisputesState,
    # Entropy
    bytes.fromhex('06000000000000000000000000000000000000000000000000000000000000'): EntropyState,
    # Validator queue
    bytes.fromhex('07000000000000000000000000000000000000000000000000000000000000'): ValidatorQueueState,
    # Validator pool
    bytes.fromhex('08000000000000000000000000000000000000000000000000000000000000'): ValidatorPoolState,
    # Validator archive
    bytes.fromhex('09000000000000000000000000000000000000000000000000000000000000'): ValidatorArchiveState,
    # Assurances
    bytes.fromhex('0a000000000000000000000000000000000000000000000000000000000000'): AssurancesState,
    # Timeslot
    bytes.fromhex('0b000000000000000000000000000000000000000000000000000000000000'): TimeslotState,
    # Privileged services
    bytes.fromhex('0c000000000000000000000000000000000000000000000000000000000000'): PrivilegedServicesState,
    # Statistics
    bytes.fromhex('0d000000000000000000000000000000000000000000000000000000000000'): StatisticsState,
    # Accumulation queue
    bytes.fromhex('0e000000000000000000000000000000000000000000000000000000000000'): AccumulationQueueState,
    # Accumulation history
    bytes.fromhex('0f000000000000000000000000000000000000000000000000000000000000'): AccumulationHistoryState,
    # Recent beefy commitments
    bytes.fromhex('10000000000000000000000000000000000000000000000000000000000000'): BeefyCommitmentMap,
}


@dataclass
class ParallelAccumulationOutput:
    """
    GP-0.7.1-eq:12.19
    """
    accumulation_state: AccumulationStateComponents
    deferred_transfers: List[DeferredTransfer]
    accumulation_commitment: BeefyCommitmentMap
    accumulation_gas_utilized: Dict[int, int]


@dataclass
class FullAccumulationOutput:
    """
    GP-0.7.1-eq:12.28
    """
    # n
    nr_work_results_accumulated: int
    # e'
    post_accumulation_state: AccumulationStateComponents
    # θ
    accumulation_commitment: BeefyCommitmentMap
    # bold_u
    accumulation_gas_utilized: Dict[int, int]
