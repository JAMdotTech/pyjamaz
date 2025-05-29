from dataclasses import dataclass, field

from jamcodec.mixins import Serializable
from jamcodec.types import H256, U64, Array, U8, U32, Null


@dataclass
class CreateServiceInstruction(Serializable):
    # Hash of the code of the new service.
    code_hash: bytes = field(metadata={'codec': H256})
    # Length of the code of the new service.
    code_len: int = field(metadata={'codec': U64})
    # Minimum gas required for each work-item to be accumulated.
    min_item_gas: int = field(metadata={'codec': U64})
    # Minimum gas required for each incoming transfer.
    min_memo_gas: int = field(metadata={'codec': U64})
    # The balance to be transferred to the new service.
    endowment: int = field(metadata={'codec': U64})
    # The memo to be attached to the transfer.
    memo: bytes = field(metadata={'codec': Array(U8, 128)})


@dataclass
class UpgradeInstruction(Serializable):
    # Hash of the code to be upgraded. This must already be in the service's preimage store.
    code_hash: bytes = field(metadata={'codec': H256})
    # Minimum gas required for each work-item to be accumulated.
    min_item_gas: int = field(metadata={'codec': U64})
    # Minimum gas required for each incoming transfer.
    min_memo_gas: int = field(metadata={'codec': U64})


@dataclass
class TransferInstruction(Serializable):
    # The destination service.
    destination: int = field(metadata={'codec': U32})
    # The amount to be transferred.
    amount: int = field(metadata={'codec': U64})
    # The amount of gas for the processing of the transfer by the destination service.
    gas_limit: int = field(metadata={'codec': U64})
    # The memo to give the destination service for the transfer.
    memo: bytes = field(metadata={'codec': Array(U8, 128)})


@dataclass
class ZombifyInstruction(Serializable):
    # The service which will be able to eject the zombie.
    ejector: int = field(metadata={'codec': U32})

"""
Zombify {
		/// The service which will be able to eject the zombie.
		ejector: ServiceId,
	},
	/// Destroy a zombie service with this as its ejector.
	Eject {
		/// The target service. This must have empty storage and exactly one preimage, whose hash
		/// is `code_hash` and which must be unrequested and droppable.
		target: ServiceId,
		/// The code hash of the target service, which should be unrequested and droppable.
		code_hash: CodeHash,
	},
	/// Delete some items from the storage of the service.
	DeleteItems {
		/// List of keys to be deleted.
		storage_items: Vec<Vec<u8>>,
	},
	/// Request that preimage data be placed in the service's preimage store.
	Solicit {
		/// The hash of the data to solicit.
		hash: AnyHash,
		/// The length of the data to solicit.
		len: u64,
	},
	/// Revoke request that preimage data be placed in the service's preimage store or drop
	/// preimage data once they have sat without request for sufficiently long.
	Forget {
		/// The hash of the previously requested data.
		hash: AnyHash,
		/// The length of the previously requested data.
		len: u64,
	},
	/// Look up preimage data.
	Lookup {
		/// Service ID which has the preimage data in its preimage store.
		service: ServiceId,
		/// The hash of the data.
		hash: AnyHash,
	},
	/// Import segments from the JAM D3L.
	Import {
		/// The index and length pairs of each of the segments to be imported.
		items: Vec<(
			u64, // index
			u64, // len
		)>,
	},
	/// Export segments to the JAM D3L.
	Export {
		/// The blobs of data to be exported.
		data: Vec<Vec<u8>>,
	},
	/// Reset the JAM privileged services.
	Bless {
		/// The manager service ID.
		manager: ServiceId,
		/// The assigner service ID.
		assign: ServiceId,
		/// The designator service ID.
		designate: ServiceId,
		/// The auto-accumulator service IDs, together with the baseline gas they get.
		auto_acc: Vec<(ServiceId, UnsignedGas)>,
	},
	/// Assign the queue of a core.
	Assign {
		/// The index of the core to be assigned.
		core: CoreIndex,
		/// The authorization queue to assign.
		queue: AuthQueue,
	},
	/// Designate the new validator key set.
	Designate {
		/// The keys of the new validator set.
		keys: OpaqueValKeysets,
	},
	/// Specify a value for accumulate to return.
	Yield {
		/// The hash to be yielded.
		hash: Hash,
	},
	/// Checkpoint the accumulation state.
	Checkpoint,
	/// Panic.
	Panic,
"""

@dataclass
class RandomStorageRefineInstruction(Serializable):
    seed: int = field(metadata={'codec': U64})
    nb_items: int = field(metadata={'codec': U8})


@dataclass
class Instruction(Serializable):

    CreateService: CreateServiceInstruction = field(default=None, metadata={'codec': CreateServiceInstruction.to_codec_def()})
    Upgrade: UpgradeInstruction = field(default=None, metadata={'codec': UpgradeInstruction.to_codec_def()})
    Transfer: TransferInstruction = field(default=None, metadata={'codec': TransferInstruction.to_codec_def()})
    Zombify: ZombifyInstruction = field(default=None, metadata={'codec': ZombifyInstruction.to_codec_def()})
    Eject: None = field(default=None, metadata={'codec': Null})
    DeleteItems: None = field(default=None, metadata={'codec': Null})
    Solicit: None = field(default=None, metadata={'codec': Null})
    Forget: None = field(default=None, metadata={'codec': Null})
    Lookup: None = field(default=None, metadata={'codec': Null})
    Import: None = field(default=None, metadata={'codec': Null})
    Export: None = field(default=None, metadata={'codec': Null})
    Bless: None = field(default=None, metadata={'codec': Null})
    Assign: None = field(default=None, metadata={'codec': Null})
    Designate: None = field(default=None, metadata={'codec': Null})
    Yield: None = field(default=None, metadata={'codec': Null})
    Checkpoint: None = field(default=None, metadata={'codec': Null})
    Panic: None = field(default=None, metadata={'codec': Null})
    LookedUp: None = field(default=None, metadata={'codec': Null})
    Imported: None = field(default=None, metadata={'codec': Null})
    Exported: None = field(default=None, metadata={'codec': Null})
    RandomStorageRefine: RandomStorageRefineInstruction = field(default=None, metadata={'codec': RandomStorageRefineInstruction.to_codec_def()})

    _codec_enum = True
