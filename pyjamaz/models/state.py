import logging
from copy import deepcopy
from dataclasses import dataclass, field
from math import ceil
from typing import List, Optional, Dict, Tuple, Union

from jamcodec.base import JamBytes

from pyjamaz.exceptions import StateKeyNoResult
from pyjamaz.hashing import keccak_256_hash, blake2b_256_hash

from jamcodec.mixins import Serializable
from jamcodec.types import U32, Array, H256, Vec, U8, Option, U64, Map, Bytes, Enum, Tuple as JamTuple, VarInt64
from pyjamaz.graypaper_constants import EPOCH_TIMESLOTS, VALIDATOR_COUNT, CORE_COUNT, \
    MAXIMUM_AUTHORIZATION_QUEUE_ITEMS, SIZE_TRANSFER_MEMO, MINIMUM_BALANCE_SERVICE, MINIMUM_BALANCE_ITEM, \
    MINIMUM_BALANCE_OCTET, EC_SEGMENT_SIZE
from pyjamaz.merkle import WellBalancedMerkleTree, MerkleMountainRange
from pyjamaz.models.common import ValidatorData, Assurance, WorkReport, TicketBody, WorkPackage
from pyjamaz.pvm.invocation import InvocationContext

from pyjamaz.state.base import StorageMap, state_key_constructor_service_account, state_key_constructor_preimage, \
    state_key_constructor_storage_item, state_key_constructor_preimage_availability
from pyjamaz.storage import StorageEngine, Transaction

from pyjamaz.models.block import Assurance as ExtrinsicAssurance, Preimage


class State(Serializable):

    def __setattr__(self, key, value):
        super().__setattr__(key, value)


@dataclass
class TimeslotState(State, Serializable):
    """
    GP-0.5.0-eq:6.1 (τ) | The most recent block's slot index, combined with helper functions.

    Attributes
    ----------
    number: U32
        GP-0.5.0-eq:6.1 (τ) | The most recent block's slot index.
    """
    # Todo: consider renaming number to timeslot
    number: int = field(metadata={'codec': U32})

    def epoch_number(self) -> int:
        """
        GP-0.5.0-eq:6.2 (e) | Function that returns the epoch index.

        Returns
        -------
        number: int
            Epoch index of the timeslot.

        """
        return self.number // EPOCH_TIMESLOTS

    def slot_phase_index(self) -> int:
        """
        GP-0.5.0-eq:6.2 (m) | Function that returns the phase index into the epoch of the timeslot.

        Returns
        -------
        number: int
            Phase index into the epoch of the timeslot.

        """
        return self.number % EPOCH_TIMESLOTS


@dataclass
class EntropyState(State, Serializable):
    """
    GP-0.5.0-eq:6.21 (η) | Entropy partition of the overall state.

    Attributes
    ----------
    entropy: Array(H256,4)
        GP-0.5.0-eq:6.21 (η) | η[0] serves as an entropy accumulator during the current epoch. η[1], η[2], η[3] retain
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
            raise ValueError("Either tickets or keys must be set")


@dataclass
class SafroleState(State, Serializable):
    """
    GP-0.5.0-eq:6.3 (γ) | Safrole partition of the overall state.

    Attributes
    ----------
    validators: Array(ValidatorData,constant_V)
        GP-0.5.0-eq:6.7 (γ_k) | A fixed size set of keys and metadata for validators of the next epoch.
    ring_commitment: Array(U8,144)
        GP-0.5.0-eq:6.4 (γ_z) | Bandersnatch ring commitment.
    slot_sealer_series: SlotSealerSeries
        GP-0.5.0-eq:6.5 (γ_s) | Sealing-key series of the current epoch.
    ticket_accumulator: TicketBody
        GP-0.5.0-eq:6.5 (γ_a) | Sealing-key contest ticket accumulator.
    """
    # Todo: review and annotate: ValidatorData
    validators: List[ValidatorData] = field(metadata={'codec': Array(ValidatorData.to_codec_def(), VALIDATOR_COUNT)})
    ring_commitment: bytes = field(metadata={'codec': Array(U8, 144)})
    # Todo: review and annotate: SlotSealerSeries
    slot_sealer_series: SlotSealerSeries = field(metadata={'codec': SlotSealerSeries.to_codec_def()})
    # Todo: review and annotate: TicketBody
    ticket_accumulator: List[TicketBody] = field(metadata={'codec': Vec(TicketBody.to_codec_def())})


@dataclass
class ValidatorQueueState(State, Serializable):
    """
    GP-0.5.0-eq:6.7 (ι) | Validator keys and metadata to be drawn from next by the Safrole protocol.

    Attributes
    ----------
    validators: Array(ValidatorData,constant_V)
        GP-0.5.0-eq:6.7 (ι) | A fixed size set of validator keys and metadata to be drawn from next by the Safrole
        protocol.
    """
    # Todo: review and annotate: ValidatorData
    validators: List[ValidatorData] = field(metadata={'codec': Array(ValidatorData.to_codec_def(), VALIDATOR_COUNT)})


@dataclass
class ValidatorPoolState(State, Serializable):
    """
    GP-0.5.0-eq:6.7 (κ) | Keys and metadata for validators of the current epoch.

    Attributes
    ----------
    validators: Array(ValidatorData,constant_V)
        GP-0.5.0-eq:6.7 (κ) | A fixed size set of keys and metadata for validators of the current epoch.
    """
    # Todo: review and annotate: ValidatorData
    validators: List[ValidatorData] = field(metadata={'codec': Array(ValidatorData.to_codec_def(), VALIDATOR_COUNT)})


@dataclass
class ValidatorArchiveState(State, Serializable):
    """
    GP-0.5.0-eq:6.7 (λ) | Keys and metadata for validators of the previous epoch.

    Attributes
    ----------
    validators: Array(ValidatorData,constant_V)
        GP-0.5.0-eq:6.7 (λ) | A fixed size set of keys and metadata for validators of the previous epoch.
    """
    # Todo: review and annotate: ValidatorData
    validators: List[ValidatorData] = field(metadata={'codec': Array(ValidatorData.to_codec_def(), VALIDATOR_COUNT)})


@dataclass
class AuthorizerPoolsState(State, Serializable):
    """
    GP-0.5.0-eq:8.1 (α) | A collections of pools of authorizations for all cores.

    Attributes
    ----------
    authorizer_pools: Array(Vec(H256),constant_C)
        GP-0.5.0-eq:8.1 (α) | A collections of pools of authorizations for all cores.
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
    GP-0.5.0-eq:E.8,E.9 (bold_b) | A Merkle Mountain Range.

    Attributes
    ----------

    peaks: Vec(Option(H256))
        GP-0.5.0-eq:7.1 (bold_b) | A collection of optional peaks in a Merkle Mountain Range
    """
    peaks: List[Optional[bytes]] = field(metadata={'codec': Vec(Option(H256))})

    def super_peak(self) -> bytes:
        mmr = MerkleMountainRange(self.peaks)
        return mmr.super_peak()



@dataclass
class ReportedWorkPackage(Serializable):
    """
    GP-0.5.0-eq:7.1 (bold_p) | A collection of hashes for each work-report made into the MMR, limited to the number
    of cores (constant_c=341)

    Attributes
    ----------
    hash: H256
        GP-0.5.0-eq:7.1 (blackboard_H in dictionary) | The segment_tree_lookup_item key.
    exports_root: H256
        GP-0.5.0-eq:7.1 (blackboard_H in dictionary) | The segment_tree_lookup_item key.
    """
    hash: bytes = field(metadata={'codec': H256})
    exports_root: bytes = field(metadata={'codec': H256})


@dataclass
class RecentBlock(Serializable):
    """
    GP-0.5.0-eq:7.1 (β) | A single item in the RecentHistory partition of the overall state.

    Attributes
    ----------

    header_hash: H256
        GP-0.5.0-eq:7.1 (h, blackboard_H) | Header hash of the recent block.
    beefy_root: H256
        GP-0.5.0-eq:7.1 (bold_b) | Beefy root of the recent block.
    state_root: H256
        GP-0.5.0-eq:7.1 (s, blackboard_H) | State root of the recent block.
    reported: Vec(ReportedWorkPackage)
        GP-0.5.0-eq:7.1 (bold_p) | A collection of ReportedWorkPackage for each work-report made into the MMR, limited
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
    GP-0.5.0-eq:7.1 (β) | RecentHistory partition of the overall state

    Attributes
    ----------
    recent_blocks: Vec(RecentBlock)
        GP-0.5.0-eq:7.1 (β) | A collection of items in the RecentHistory partition of the overall state of
        up to constant_H (8) items.
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
    GP-0.6.2-eq:9.3 (blackboard_A) | A service account.

    Attributes
    ----------
    code_hash: H256
        GP-0.6.2-eq:9.3 (c) | Hash of the service account's code
    balance: U64
        GP-0.6.2-eq:9.3 (b) | Balance of a service account
    gas_limit_accumulate: U64
        GP-0.6.2-eq:9.3 (g) | Minimum gas required to execute the Accumulate entry-point of the service account's code.
    gas_limit_on_transfer: U64
        GP-0.6.2-eq:9.3 (m) | Minimum gas required to execute the On-Transfer entry-point of the service account's code.
    footprint_storage_bytes: U64
        GP-0.6.2-eq:9.8 (o) | Storage footprint of the service account. The total number of bytes used in storage.
    footprint_storage_items: U32
        GP-0.6.2-eq:9.8 (i) | Storage footprint of the service account. The number of items in storage.
    threshold_balance: U64
        GP-0.6.2-eq:9.8 (t) | Minimum or threshold balance needed for the ServiceAccount in terms of its storage
        footprint.
    deposit_offset: U32
        GP-0.6.7-eq:9.3 (f) | Gratis deposit offset.
    creation_slot: U32
        GP-0.6.7-eq:9.3 (r) | Timeslot when created
    last_accumulation_slot: U64
        GP-0.6.7-eq:9.3 (a) | Timeslot when last accumulated
    parent_service: U64
        GP-0.6.7-eq:9.3 (p) | Parent service.
    storage_items: Dict(H256,Bytes)
        GP-0.6.2-eq:9.3 (bold_s) | Storage items dict. Provides storage item data for storage item hash.
    preimages: Dict(H256,Bytes)
        GP-0.6.2-eq:9.3 (bold_p) | Preimages dict. Provides preimage data for preimage hash (including: code_hash)
    preimage_availability: Dict(Tuple(H256,U32), Vec<U32>)
        GP-0.6.2-eq:9.3 (bold_l) | Preimages availability dict. Provides historical status of preimage availability.
    """
    # Remark: Only the following field need to be serialized/deserialized
    code_hash: bytes = field(metadata={'codec': H256})
    balance: int = field(metadata={'codec': U64})
    gas_limit_accumulate: int = field(metadata={'codec': U64})
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
        # GP-0.6.7-eq:9.8 (a_t)
        return max(0,
            MINIMUM_BALANCE_SERVICE + MINIMUM_BALANCE_ITEM * self.footprint_storage_items +
            MINIMUM_BALANCE_OCTET * self.footprint_storage_bytes - self.deposit_offset
        )

    @classmethod
    def from_serialized_bytes(cls, serialized_bytes: bytes) -> 'ServiceAccount':
        return ServiceAccount(
            code_hash=serialized_bytes[0:32],
            balance=U64.decode(JamBytes(serialized_bytes[32:40])),
            gas_limit_accumulate=U64.decode(JamBytes(serialized_bytes[40:48])),
            gas_limit_on_transfer=U64.decode(JamBytes(serialized_bytes[48:56])),
            footprint_storage_bytes=U64.decode(JamBytes(serialized_bytes[56:64])),
            deposit_offset=U64.decode(JamBytes(serialized_bytes[64:72])),
            footprint_storage_items=U32.decode(JamBytes(serialized_bytes[72:76])),
            creation_slot=U32.decode(JamBytes(serialized_bytes[76:80])),
            last_accumulation_slot=U32.decode(JamBytes(serialized_bytes[80:84])),
            parent_service=U32.decode(JamBytes(serialized_bytes[84:88])),
            storage_items={},
            preimages={},
            preimage_availability={},
        )

    def to_serialized_bytes(self) -> bytes:
        serialized_bytes = self.code_hash
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
        self.gas_limit_accumulate = service_account.gas_limit_on_transfer
        self.gas_limit_on_transfer = service_account.gas_limit_on_transfer

    def update_footprint_add_storage_item(self, key_len: int, value_len: int) -> None:
        """
        GP-0.6.7-eq:9.8
        """
        self.footprint_storage_items += 1
        self.footprint_storage_bytes += 34 + key_len + value_len

    def update_footprint_remove_storage_item(self, key_len: int, value_len: int) -> None:
        """
        GP-0.6.7-eq:9.8
        """
        self.footprint_storage_items -= 1
        self.footprint_storage_bytes -= 34 + key_len + value_len

    def update_footprint_update_storage_item(self, old_value_len: int, new_value_len: int) -> None:
        """
        GP-0.6.7-eq:9.8
        """
        self.footprint_storage_bytes += new_value_len - old_value_len

    def update_footprint_add_preimage(self, size: int) -> None:
        """
        GP-0.6.7-eq:9.8
        """
        self.footprint_storage_items += 2
        self.footprint_storage_bytes += 81 + size

    def update_footprint_remove_preimage(self, size: int) -> None:
        """
        GP-0.6.7-eq:9.8
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
class ServicesState(State, Serializable):
    """
    GP-0.5.2-eq:9.2 (δ) | Services partition of the overall state.

    Attributes
    ----------
    services: Dict(U32,ServiceAccount)
        GP-0.5.2-eq:9.1,9.2 (δ, blackboard_N_S, blackboard_A) | Services dict. Provides service account data for a
        service account index.
    """
    services: Union[Dict[int, ServiceAccount], ServiceAccountMap] = field(
        metadata={'codec': Map(U32, ServiceAccount.to_codec_def())}
    )

    def __deepcopy__(self, memo):
        # Create a new instance without calling __init__
        new_obj = self.__class__.__new__(self.__class__)
        memo[id(self)] = new_obj

        # Only copy attribute 'services'
        new_obj.services = deepcopy(self.services, memo)

        # Set new storage engine
        new_obj.set_storage_engine(self.storage_engine)

        return new_obj

    # TODO replace with storage transaction
    def set_storage_engine(self, storage_engine: StorageEngine):
        setattr(self, '_storage_engine', storage_engine)

    @property
    def storage_engine(self) -> Optional[StorageEngine]:
        return getattr(self, '_storage_engine', None)

    # TODO refactor to setter
    def set_storage_transaction(self, transaction: Transaction):
        setattr(self, '_storage_transaction', transaction)

    @property
    def storage_transaction(self) -> Optional[Transaction]:
        return getattr(self, '_storage_transaction', None)

    def retrieve_service_account(
            self,
            service_account_id: int
    ) -> ServiceAccount:

        service_account = None
        if service_account_id in self.services:
            service_account = self.services[service_account_id]
        else:
            if self.storage_engine is None:
                raise ValueError('storage engine must be set before retrieving preimage')

            storage_key = state_key_constructor_service_account(service_account_id)
            logging.debug(f'retrieve_service_account({service_account_id}): {storage_key.hex()}')

            data = self.storage_engine.get(storage_key)
            if data:
                service_account = ServiceAccount.from_serialized_bytes(data)

        if service_account is None:
            raise StateKeyNoResult(f'Service account not found for ID {service_account_id}')

        return service_account

    def store_service_account(self, service_account_id: int, service_account: ServiceAccount, commit=False):
        """
        Stores a service account

        Parameters
        ----------
        service_account_id
        service_account
        commit

        Returns
        -------

        """
        if service_account_id not in self.services:
            self.services[service_account_id] = service_account
        else:
            self.services[service_account_id].update_from(service_account)

        state_key = state_key_constructor_service_account(service_account_id)

        if commit:

            if self.storage_transaction is None:
                raise ValueError('storage_transaction must be set before storing a service account')

            data = service_account.to_serialized_bytes()

            self.storage_transaction.put(state_key, data)

        logging.debug(f'store_service_account({service_account_id}): code_hash={service_account.code_hash.hex()} balance={service_account.balance} min_item_gas={service_account.gas_limit_accumulate} min_memo_gas={service_account.gas_limit_on_transfer} f_i={service_account.footprint_storage_items} f_b={service_account.footprint_storage_bytes} commit={commit}')


    def delete_service_account(self, service_account_id: int, commit=False):
        """
        Deletes a service account

        Parameters
        ----------
        service_account_id

        Returns
        -------

        """

        if commit:

            if self.storage_transaction is None:
                raise ValueError('storage_transaction must be set before deleting service account data')

            state_key = state_key_constructor_service_account(service_account_id)

            self.storage_transaction.delete(state_key)

            del self.services[service_account_id]
        else:
            self.services[service_account_id] = None

        logging.debug(f'delete_service_account({service_account_id}) storage_key={state_key.hex()} commit={commit}')


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

        if service_account_id in self.services and preimage_hash in self.services[service_account_id].preimages:
            preimage = self.services[service_account_id].preimages[preimage_hash]
        else:
            if self.storage_engine is None:
                raise ValueError('storage engine must be set before retrieving preimage')

            storage_key = state_key_constructor_preimage(service_account_id, preimage_hash)
            logging.debug(f'retrieve_preimage({service_account_id}, {preimage_hash.hex()}): {storage_key.hex()}')

            preimage = self.storage_engine.get(storage_key)

        if preimage is None:
            raise StateKeyNoResult(f'Preimage not found for hash {preimage_hash}')

        return preimage

    #GP-0.6.4-eq:9.7 (historical lookup)
    def historical_preimage_lookup(self, service_account_id: int, timeslot: int, preimage_hash: bytes) -> Optional[bytes]:
        """
        historical lookup
        GP-0.6.4-eq:9.5
        GP-0.6.4-eq:9.7


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
        GP-0.5.4-eq:12.30 | Is preimage needed

        Parameters
        ----------
        preimage: Primage

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

    def store_preimage(self, service_account_id: int, preimage_blob: bytes, commit=False):
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

        if service_account_id not in self.services:
            self.services[service_account_id] = self.retrieve_service_account(service_account_id)

        preimage_hash = blake2b_256_hash(preimage_blob)
        self.services[service_account_id].preimages[preimage_hash] = preimage_blob

        storage_key = state_key_constructor_preimage(service_account_id, preimage_hash)

        if commit:

            if self.storage_transaction is None:
                raise ValueError('storage_transaction must be set before storing preimage data')

            self.storage_engine.put(storage_key, preimage_blob)

        logging.debug(f'store_preimage({service_account_id}, {preimage_hash.hex()}): sk={storage_key.hex()} commit={commit}')


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

        if service_account_id in self.services and (preimage_hash, preimage_length) in self.services[service_account_id].preimage_availability:
            preimage_availability = self.services[service_account_id].preimage_availability[(preimage_hash, preimage_length)]
        else:
            if self.storage_engine is None:
                raise ValueError('storage engine must be set before retrieving preimage availability')

            storage_key = state_key_constructor_preimage_availability(service_account_id, preimage_hash, preimage_length)

            data = self.storage_engine.get(storage_key)
            if data:
                availability = Vec(U32).new()
                availability.decode(JamBytes(data))
                preimage_availability = availability.value

        if preimage_availability is None:
            raise StateKeyNoResult(
                f'Preimage availability not found for hash {preimage_hash} and length {preimage_length}'
            )

        logging.debug(
            f'retrieve_preimage_availability({service_account_id}, {preimage_hash.hex()}, {preimage_length}): v={preimage_availability}'
            )

        return preimage_availability


    def store_preimage_availability(
            self, service_account_id: int, preimage_hash: bytes, preimage_length: int, value: List[int], commit=False
    ):

        if service_account_id not in self.services:
            self.services[service_account_id] = self.retrieve_service_account(service_account_id)

        storage_key = state_key_constructor_preimage_availability(service_account_id, preimage_hash, preimage_length)

        self.services[service_account_id].preimage_availability[(preimage_hash, preimage_length)] = value

        if commit:

            if self.storage_transaction is None:
                raise ValueError('storage_transaction must be set before storing preimage availability data')

            availability = Vec(U32).new()
            data = availability.encode(value)


            self.storage_transaction.put(storage_key, data.to_bytes())

        logging.debug(
            f'store_preimage_availability({service_account_id}, {preimage_hash.hex()}, {preimage_length}): v={value} {storage_key.hex()}'
        )


    def delete_preimage(self, service_account_id: int, preimage_hash: bytes, commit=False):

        if service_account_id not in self.services:
            self.services[service_account_id] = self.retrieve_service_account(service_account_id)

        storage_key = state_key_constructor_preimage(service_account_id, preimage_hash)

        if commit:

            if self.storage_transaction is None:
                raise ValueError('storage_transaction must be set before deleting preimage availability data')

            self.storage_transaction.delete(storage_key)
            del self.services[service_account_id].preimages[preimage_hash]
        else:
            self.services[service_account_id].preimages[preimage_hash] = None

        logging.debug(
            f'delete_preimage({service_account_id}, {preimage_hash.hex()}): {storage_key.hex()} commit={commit}'
            )


    def delete_preimage_availability(
            self, service_account_id: int, preimage_hash: bytes, preimage_length: int, commit=False
    ):

        if service_account_id not in self.services:
            self.services[service_account_id] = self.retrieve_service_account(service_account_id)

        storage_key = state_key_constructor_preimage_availability(service_account_id, preimage_hash, preimage_length)

        if commit:

            if self.storage_transaction is None:
                raise ValueError('storage_transaction must be set before deleting preimage availability data')

            self.storage_transaction.delete(storage_key)
            del self.services[service_account_id].preimage_availability[(preimage_hash, preimage_length)]

        else:
            self.services[service_account_id].preimage_availability[(preimage_hash, preimage_length)] = None

        logging.debug(
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

        if service_account_id in self.services and storage_item_hash in self.services[service_account_id].storage_items:
            data = self.services[service_account_id].storage_items[storage_item_hash]
        else:
            if self.storage_engine is None:
                raise ValueError('storage engine must be set before retrieving storage items')

            storage_key = state_key_constructor_storage_item(service_account_id, storage_item_hash)
            data = self.storage_engine.get(storage_key)

        if data is None:
            raise StateKeyNoResult(
                f'Storage item not found for hash {storage_item_hash} for service account {service_account_id}'
            )

        logging.debug(
            f'retrieve_storage_item(s={service_account_id}, k={storage_item_hash.hex()}): v={data.hex()}'
            )

        return data

    def store_storage_item(self, service_account_id: int, storage_key: bytes, value: bytes, commit=False):
        """
        Store a storage item in the storage engine
        """
        if service_account_id not in self.services:
            self.services[service_account_id] = self.retrieve_service_account(service_account_id)

        state_key = state_key_constructor_storage_item(service_account_id, storage_key)

        if commit:
            if self.storage_transaction is None:
                raise ValueError('storage_transaction must be set before storing storage items')
            self.storage_transaction.put(state_key, value)

        logging.debug(f'store_storage_item(s={service_account_id}, k={storage_key.hex()}): v={value.hex()} state_key={state_key.hex()} [commit={commit}]')

        self.services[service_account_id].storage_items[storage_key] = value


    def delete_storage_item(self, service_account_id: int, storage_item_hash: bytes, commit=False):
        """
        Delete a storage item in the storage engine
        """
        if service_account_id not in self.services:
            self.services[service_account_id] = self.retrieve_service_account(service_account_id)

        storage_key = state_key_constructor_storage_item(service_account_id, storage_item_hash)

        if commit:

            if self.storage_transaction is None:
                raise ValueError('storage_transaction must be set before deleting storage items')

            self.storage_transaction.delete(storage_key)

            del self.services[service_account_id].storage_items[storage_item_hash]

        else:
            self.services[service_account_id].storage_items[storage_item_hash] = None

        logging.debug(
            f'delete_storage_item(s={service_account_id}, k={storage_item_hash.hex()}): state_key={storage_key.hex()} [commit={commit}]'
            )


@dataclass
class AssurancesState(State, Serializable):
    """
    GP-0.5.0-eq:11.1 (ρ) | Assurances partition of the overall state.

    Attributes
    ----------
    assurances: Vec(Option(Assurance))
        GP-0.5.0-eq:11.1 (ρ) | A collection of optional assurances per core.
    """
    assurances: List[Optional[Assurance]] = field(
        metadata={'codec': Array(Option(Assurance.to_codec_def()), CORE_COUNT)}
    )


@dataclass
class AuthorizerQueuesState(State, Serializable):
    """
    GP-0.5.0-eq:8.1 (φ) | A collections of queues of authorizations for all cores.

    Attributes
    ----------
    authorizer_queues: Array(Array(H256,constant_Q),constant_C)
        GP-0.5.0-eq:8.1 (φ) | A collections of queues of authorizations for all cores.
    """
    authorizer_queues: List[List[bytes]] = field(
        metadata={'codec': Array(Array(H256, MAXIMUM_AUTHORIZATION_QUEUE_ITEMS), CORE_COUNT)}
    )


@dataclass
class PrivilegedServicesState(State, Serializable):
    """
    GP-0.6.7-eq:9.9 (χ) | The PrivilegedServices partition of the overall state.

    Attributes
    ----------
    manager: U32
        GP-0.5.0-eq:9.9 (χ_m) | The service index of the empower service. I.e. the service that allows state transitions
        of PrivilegedServices (χ).
    assigners: U32
        GP-0.5.0-eq:9.9 (χ_a) | The service index of the assign service. I.e. the service that allows state transitions
        of AuthorizerQueue (φ).
    delegator: U32
        GP-0.5.0-eq:9.9 (χ_v) | The service index of the designate service. I.e. the service that allows state
        transitions of ValidatorQueue (ι).
    always_accumulators: Dict(U32,U64)
        GP-0.5.0-eq:9.9 (χ_g) | Auto Accumulate Services dict. Provides gas limit data for a service account index.
    """
    manager: int = field(metadata={'codec': U32})
    assigners: List[int] = field(metadata={'codec': Array(U32, CORE_COUNT)})
    delegator: int = field(metadata={'codec': U32})
    always_accumulators: Dict[int, int] = field(metadata={'codec': Map(U32, U64)})


@dataclass
class DisputesState(State, Serializable):
    """
    GP-0.5.0-eq:9.9 (ψ) | A collection of judgements of validators over the validity of work reports.

    Attributes
    ----------
    good_set: Vec(H256)
        GP-0.5.0-eq:10.1,10.16 (ψ_g) | A collection of work reports hashes with a good verdict.
    bad_set: Vec(H256)
        GP-0.5.0-eq:10.1,10.17 (ψ_b) | A collection of work reports hashes with a bad verdict.
    wonky_set: Vec(H256)
        GP-0.5.0-eq:10.1,10.18 (ψ_w) | A collection of work reports hashes with a wonky verdict.
    offenders: Vec(H256)
        GP-0.5.0-eq:10.1,10.19 (ψ_o) | A collection Edwards 25519 keys for validators found guilty of offending.
    """
    good_set: List[bytes] = field(metadata={'codec': Vec(H256)})
    bad_set: List[bytes] = field(metadata={'codec': Vec(H256)})
    wonky_set: List[bytes] = field(metadata={'codec': Vec(H256)})
    offenders: List[bytes] = field(metadata={'codec': Vec(H256)})


@dataclass
class ActivityRecord(Serializable):
    """
    GP-0.5.0-eq:13.1 (π.0.V) | A set of cumulative metrics for a single validator in a single epochs.

    Attributes
    ----------
    blocks: U32
        GP-0.5.0-eq:13.1 (b) | The number of blocks produced by the validator.
    tickets: U32
        GP-0.5.0-eq:13.1 (t) | The number of tickets introduced by the validator.
    pre_images: U32
        GP-0.5.0-eq:13.1 (p) | The number of preimages introduced by the validator.
    pre_images_size: U32
        GP-0.5.0-eq:13.1 (d) | The number of total number of bytes across all preimages introduced by the validator.
    guarantees: U32
        GP-0.5.0-eq:13.1 (g) | The number of reports guaranteed by the validator.
    assurances: U32
        GP-0.5.0-eq:13.1 (a) | The number of availability assurances made by the validator.
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
    GP-0.6.4-eq:13.6 | Core activity statistics

    Attributes
    ----------
    da_load: U32
        GP-0.6.4-eq:13.6 (d) | Amount of bytes which are placed into either Audits or Segments DA.
    popularity: U16
        GP-0.6.4-eq:13.6 (p) | Number of validators which formed super-majority for assurance.
    imports: U16
        GP-0.6.4-eq:13.6 (i) | Number of segments imported from DA made by core for reported work.
    exports: U16
        GP-0.6.4-eq:13.6 (e) | Number of segments exported into DA made by core for reported work.
    extrinsic_size: U32
        GP-0.6.4-eq:13.6 (z) | Total size of extrinsics used by core for reported work.
    extrinsic_count: U16
        GP-0.6.4-eq:13.6 (x) | Total number of extrinsics used by core for reported work.
    bundle_size: U32
        GP-0.6.4-eq:13.6 (b) | The work-bundle size. This is the size of data being placed into Audits DA by the core.
    gas_used: U64
         GP-0.6.4-eq:13.6 (u) | Total gas consumed by core for reported work. Includes all refinement and authorizations
    """
    da_load: int = field(metadata={'codec': VarInt64})
    popularity: int = field(metadata={'codec': VarInt64})
    imports: int = field(metadata={'codec': VarInt64})
    exports: int = field(metadata={'codec': VarInt64})
    extrinsic_size: int = field(metadata={'codec': VarInt64})
    extrinsic_count: int = field(metadata={'codec': VarInt64})
    bundle_size: int = field(metadata={'codec': VarInt64})
    gas_used: int = field(metadata={'codec': VarInt64})

    def update(self,
               core_index: int,
               incoming_work_reports: List[WorkReport],
               available_work_reports: List[WorkReport],
               extrinsic_assurances: List['ExtrinsicAssurance']
    ):
        """
         GP-0.6.4-eq:13.8 | Updating core stats for specified core
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
        GP-0.6.4-eq:13.9 (R) | Updating core stats using incoming work-reports in extrinsic data (GP-0.6.4-eq:11.28)
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
        GP-0.6.4-eq:13.10 (D) | Updating core stats using available work-reports (bold_W) (GP-0.6.4-eq:11.16)
        """
        self.da_load = sum([
            w.package_spec.length + EC_SEGMENT_SIZE * ceil(w.package_spec.exports_count * 65/64)
            for w in available_work_reports if w.core_index == core_index
        ])

@dataclass
class ServiceActivityRecord(Serializable):
    """

    Attributes
    ----------
    provided_count: U16
        GP-0.6.4-eq:13.7 (p_0) | Number of preimages provided to this service.
    provided_size: U32
        GP-0.6.4-eq:13.7 (p_1)| Total size of preimages provided to this service.
    refinement_count: U32
        GP-0.6.4-eq:13.7 (r_0)| Number of work-items refined by service for reported work.
    refinement_gas_used: U64
        GP-0.6.4-eq:13.7 (r_0)| Amount of gas used for refinement by service for reported work.
    imports: U32
        GP-0.6.4-eq:13.7 (i) | Number of segments imported from the DL by service for reported work.
    extrinsic_size: U32
        GP-0.6.4-eq:13.7 (z) | Total size of extrinsics used by service for reported work.
    extrinsic_count: U32
        GP-0.6.4-eq:13.7 (x) | Total number of extrinsics used by service for reported work.
    exports: U32
        GP-0.6.4-eq:13.7 (e) | Number of segments exported into the DL by service for reported work.
    accumulate_count: U32
        GP-0.6.4-eq:13.7 (a_0) | Number of work-items accumulated by service.
    accumulate_gas_used: U64
        GP-0.6.4-eq:13.7 (a_1) | Amount of gas used for accumulation by service.
    on_transfers_count: U32
        GP-0.6.4-eq:13.7 (t_0) | Number of transfers processed by service.
    on_transfers_gas_used: U64
        GP-0.6.4-eq:13.7 (t_1) | Amount of gas used for processing transfers by service.
    """
    provided_count: int = field(metadata={'codec': VarInt64}, default=0)
    provided_size: int = field(metadata={'codec': VarInt64}, default=0)
    refinement_count: int = field(metadata={'codec': VarInt64}, default=0)
    refinement_gas_used: int = field(metadata={'codec': VarInt64}, default=0)
    imports: int = field(metadata={'codec': VarInt64}, default=0)
    exports: int = field(metadata={'codec': VarInt64}, default=0)
    extrinsic_size: int = field(metadata={'codec': VarInt64}, default=0)
    extrinsic_count: int = field(metadata={'codec': VarInt64}, default=0)
    accumulate_count: int = field(metadata={'codec': VarInt64}, default=0)
    accumulate_gas_used: int = field(metadata={'codec': VarInt64}, default=0)
    on_transfers_count: int = field(metadata={'codec': VarInt64}, default=0)
    on_transfers_gas_used: int = field(metadata={'codec': VarInt64}, default=0)


@dataclass
class StatisticsState(State, Serializable):
    """
    GP-0.6.4-eq:13.1 (π) | A collection of statistics for all validators for two epochs.

    Attributes
    ----------

    vals_current: Array(Statistic,constant_V)
        GP-0.6.4-eq:13.1 (π) | A collection of statistics for all validators for current epoch.
    vals_last: Array(Statistic,constant_V)
        GP-0.6.4-eq:13.1 (π) | A collection of statistics for all validators for last epoch.
    cores: Array(Statistic,constant_C)
        GP-0.6.4-eq:13.1 (π) | Core activity statistics for last block.
    services: Map(U32, ServiceActivityRecord)
        GP-0.6.4-eq:13.1 (π) | Service activity statistics for last block.
    """
    vals_current: List[ActivityRecord] = field(metadata={'codec': Array(ActivityRecord.to_codec_def(), VALIDATOR_COUNT)})
    vals_last: List[ActivityRecord] = field(metadata={'codec': Array(ActivityRecord.to_codec_def(), VALIDATOR_COUNT)})
    cores: List[CoreActivityRecord] = field(metadata={
        'codec': Array(CoreActivityRecord.to_codec_def(), CORE_COUNT)
    })
    services: Dict[int, ServiceActivityRecord] = field(metadata={
        'codec': Map(U32, ServiceActivityRecord.to_codec_def())
    })



@dataclass
class AccumulationQueueWorkPackage(Serializable):
    """
    GP-0.5.0-eq:13.1 (ϑ) | A not yet accumulated work package.

    Attributes
    ----------
    report: WorkReport
        GP-0.5.4-eq:12.3 (blackboard_W) | Work Report.
    dependencies: Vec(H256)
        GP-0.5.4-eq:12.3 ({blackboard_H}) | Set of Work Package hashes.
    """
    report: WorkReport = field(metadata={'codec': WorkReport.to_codec_def()})
    dependencies: List[bytes] = field(metadata={'codec': Vec(H256)})


@dataclass
class AccumulationQueueState(State, Serializable):
    """
    GP-0.5.0-eq:12.3 (ϑ) | A collection of unaccumulated work packages.

    Attributes
    ----------

    accumulation_queue: Array(Vec(AccumulationQueueWorkPackage),constant_E)
        GP-0.5.4-eq:12.3 (ϑ) | A collection of unaccumulated work packages.
    """
    accumulation_queue: List[List[AccumulationQueueWorkPackage]] = field(
        metadata={'codec': Array(Vec(AccumulationQueueWorkPackage.to_codec_def()), EPOCH_TIMESLOTS)}
    )


@dataclass
class AccumulationHistoryState(State, Serializable):
    """
    GP-0.5.0-eq:12.1 (ξ) | A history of what has been accumulated.

    Attributes
    ----------

    accumulation_history: Array(Vec(H256),constant_E)
        GP-0.5.0-eq:12.1 (ξ) | A history of what has been accumulated.
    """
    accumulation_history: List[List[bytes]] = field(
        metadata={'codec': Array(Vec(H256), EPOCH_TIMESLOTS)}
    )


@dataclass
class BeefyCommitmentMap(Serializable):
    """
    GP-0.6.1-eq:12.15 (B) | a service-indexed commitment to the accumulation output

    Attributes
    ----------
    beefy_commitment_map: Dict(U32,H256)
        GP-0.6.1-eq:12.15 (B) | Beefy Commitment Map dictionary. Provides accumulation
        result TreeRoot for accumulated services.
    """
    beefy_commitment_map: Dict[int, bytes] = field(metadata={'codec': Map(U32, H256)})

    def get_accumulate_root(self) -> bytes:
        """
        GP-0.6.1-eq:7.3 (r) | The accumulation-result tree root of the beefy commitment map.

        Returns
        -------
        bytes
        """
        items = sorted(self.beefy_commitment_map.items(), key=lambda x: x[0])
        data = [k.to_bytes(4, byteorder='little') + v for k, v in items]
        return WellBalancedMerkleTree(data, hash_function=keccak_256_hash).root()


@dataclass
class JamState(State, Serializable):
    """
    GP-0.6.4-eq:4.4 (σ) | Logically partitioned state into several largely independent segments which can help both
    visual clutter within the protocol description and provide formality over elements of computation which may be
    simultaneously calculated (i.e. parallelized).

    Attributes
    ----------
    authorizer_pools: AuthorizerPoolsState
        GP-0.6.4-eq:4.4 (α) | AuthorizerPool partition of the overall state
    recent_history: RecentHistoryState
        GP-0.6.4-eq:4.4 (β) | RecentHistory partition of the overall state
    safrole: SafroleState
        GP-0.6.4-eq:4.4 (γ) | Safrole partition of the overall state
    services: ServicesState
        GP-0.6.4-eq:4.4 (δ) | Services partition of the overall state
    entropy: EntropyState
        GP-0.6.4-eq:4.4 (η) | Entropy partition of the overall state
    validator_queue: ValidatorQueueState
        GP-0.6.4-eq:4.4 (ι) | ValidatorQueue partition of the overall state
    validator_pool: ValidatorPoolState
        GP-0.6.4-eq:4.4 (κ) | ValidatorPool partition of the overall state
    validator_archive: ValidatorArchiveState
        GP-0.6.4-eq:4.4 (λ) | ValidatorArchive partition of the overall state
    assurances: AssurancesState
        GP-0.6.4-eq:4.4 (ρ) | Assurances partition of the overall state
    timeslot: TimeslotState
        GP-0.6.4-eq:4.4 (τ) | Timeslot partition of the overall state
    authorizer_queues: AuthorizerQueuesState
        GP-0.6.4-eq:4.4 (φ) | AuthorizerQueue partition of the overall state
    privileged_services: PrivilegedServicesState
        GP-0.6.4-eq:4.4 (χ) | PrivilegedServices partition of the overall state
    disputes: DisputesState
        GP-0.6.4-eq:4.4 (ψ) | Disputes partition of the overall state
    statistics: StatisticsState
        GP-0.6.4-eq:4.4 (π) | Statistics partition of the overall state
    accumulation_queue: AccumulationQueueState
        GP-0.6.4-eq:4.4 (ϑ) | AccumulationQueue partition of the overall state
    accumulation_history: AccumulationHistoryState
        GP-0.6.4-eq:4.4 (ξ) | AccumulationHistory partition of the overall state
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
                always_accumulators={}
            ),
            disputes=DisputesState(
                good_set=[],
                bad_set=[],
                wonky_set=[],
                offenders=[],
            ),
            statistics=StatisticsState(
                vals_current=[ActivityRecord(0, 0, 0, 0, 0, 0) for _ in range(VALIDATOR_COUNT)],
                vals_last=[ActivityRecord(0, 0, 0, 0, 0, 0) for _ in range(VALIDATOR_COUNT)],
                cores=[CoreActivityRecord(0, 0, 0, 0, 0, 0 ,0, 0) for _ in range(CORE_COUNT)],
                services={},
            ),
            accumulation_queue=AccumulationQueueState(
                accumulation_queue=[
                    [] for _ in range(EPOCH_TIMESLOTS)
                ]
            ),
            accumulation_history=AccumulationHistoryState(
                accumulation_history=[[] for _ in range(EPOCH_TIMESLOTS)]
            )
        )


@dataclass
class DeferredTransfer(Serializable):
    """
    GP-0.5.2-eq:12.14 (blackboard_T) | A single deferred transfer.

    Attributes
    ----------
    sender: U32
        GP-0.5.2-eq:12.14 (s) | Sender of a deferred transfer.
    receiver: U32
        GP-0.5.2-eq:12.14 (d) | Receiver of a deferred transfer (destination).
    amount: U64
        GP-0.5.2-eq:12.14 (a) | Balance to be transferred (amount) of the deferred transfer.
    memo: Array(U8, SIZE_TRANSFER_MEMO)
        GP-0.5.2-eq:12.14 (m) | Constant length memo blob of the deferred transfer.
    gas_limit: U64
        GP-0.5.2-eq:12.14 (g) | Gas limit of the deferred transfer.
    """
    sender: int = field(metadata={'codec': U32})
    receiver: int = field(metadata={'codec': U32})
    amount: int = field(metadata={'codec': U64})
    memo: bytes = field(metadata={'codec': Array(U8, SIZE_TRANSFER_MEMO)})
    gas_limit: int = field(metadata={'codec': U64})


@dataclass
class DeferredTransfers(Serializable):
    """
    GP-0.5.2-eq:12.23 (Vec(blackboard_T)) | A collection of deferred transfers.

    Attributes
    ----------

    deferred_transfers: Vec(DeferredTransfer)
        GP-0.5.2-eq:12.23 (Vec(blackboard_T)) | A collection of deferred transfers.
    """
    deferred_transfers: List[DeferredTransfer] = field(metadata={'codec': Vec(DeferredTransfer.to_codec_def())})


@dataclass
class AccumulationStateComponents(Serializable):
    """
    GP-0.6.7-eq:12.13 (blackboard_U) | State components which are needed and mutable by the accumulation process.

    Attributes
    ----------
    services: ServicesState
        GP-0.5.2-eq:12.13 (bold_d) | Dictionary with services state.
    validator_queue: ValidatorQueueState
        GP-0.5.2-eq:12.13 (bold_i) | Validator Queue state.
    authorizer_queues: AuthorizerQueuesState
        GP-0.5.2-eq:12.13 (bold_q) | Authorizer Queues state.
    privileged_services: PrivilegedServicesState
        GP-0.5.2-eq:12.13 (bold_x) | Privileged Services state.
    """
    services: ServicesState = field(metadata={'codec': ServicesState.to_codec_def()})
    validator_queue: ValidatorQueueState = field(metadata={'codec': ValidatorQueueState.to_codec_def()})
    authorizer_queues: AuthorizerQueuesState = field(metadata={'codec': AuthorizerQueuesState.to_codec_def()})
    privileged_services: PrivilegedServicesState = field(metadata={'codec': PrivilegedServicesState.to_codec_def()})

    def check_service_id(self, service_id: int) -> int:
        """
        B.13 | Find an unused service id
        """
        if service_id not in self.services.services:
            return service_id
        else:
            return self.check_service_id((service_id - 2**8 + 1) % (2**32 - 2**9) + 2**8)


    def to_invocation_context(self, service_account_id: int, entropy: bytes, timeslot: int) -> 'AccumulateInvocationContext':
        """
        B.9 (I)

        entropy: eta_0
        timeslot: int post_state

        """
        # Generate new unique service id
        check_payload = int.from_bytes(blake2b_256_hash(
            service_account_id.to_bytes(length=4, byteorder='little') + entropy + timeslot.to_bytes(length=4, byteorder='little')
        )[:4], byteorder='little')

        new_service_account_id = self.check_service_id((check_payload % (2**32 - 2**9)) + 2**8)

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
    GP-0.6.2-eq:B.6 (blackboard_X) | Invocation Result Context

    TODO check service_account_id in state_context.services
    """
    service_account_id: int  # s
    state_context: AccumulationStateComponents  # u
    new_service_account_id: int  # i
    deferred_transfers: List[DeferredTransfer]  # t
    invocation_output: Optional[bytes]  # y
    preimages: List[Tuple[int, bytes]] # p


@dataclass
class AccumulateInvocationContext(InvocationContext):
    """
    GP-0.6.4-eq:B.7 (X) | Invocation Result Context
    """
    context: AccumulateContextItem           # GP-0.6.4-eq:B.11 X_x
    savepoint_context: AccumulateContextItem # GP-0.6.4-eq:B.11 X_y
    timeslot: int # TODO how to make available?
