from dataclasses import dataclass, field
from typing import List

from pyjamaz.types.safrole import TicketEnvelope
from pyjamaz.serialization import Serializable
from pyjamaz.state.base import State


@dataclass
class Header(Serializable, State):
    # TODO: complete header type definition
    timeslot: int = field(metadata={'length': 4})  # Block's timeslot
    vrf_signature: bytes = field(metadata={'length': 32})  # entropy-yielding VRF signature

    # TODO: suggestion for type definition of header below
    # parent_hash: bytes = field(metadata={'length': 32})  # GP-0.3.6-eq:38 (H_p) | Hash of the header of the block's parent
    # prior_state_root: bytes = field(metadata={'length': 32})  # GP-0.3.6-eq:42 (H_r) | Merkle root of the block's parent posterior state
    # extrinsic_hash: bytes = field(metadata={'length': 32})  # GP-0.3.6-eq:40 (H_x) | Hash of the block's extrinsic data
    # timeslot: int = field(metadata={'length': 4})  # GP-0.3.6-eq:41 (H_t) | Block's timeslot
    # # TODO: add or reference dataclass for EpochMark from /types/safrole.py
    # epoch_mark: Optional[EpochMark] = None  # GP-0.3.6-eq:44 (H_e) | Optional block's epoch marker; fallback keys and entropy for next epoch
    # # TODO: suggested name change into winning_tickets_mark
    # # TODO: add or reference dataclass for TicketsMark from /types/safrole.py
    # tickets_mark: Optional[TicketsMark] = field(default=None, metadata={'size': EPOCH_TIMESLOTS}) # GP-0.3.6-eq:44 (H_w) | Optional block's winning tickets marker; provides a series of 600 slot sealing tickets for the next epoch
    # # TODO: add dataclass for OffendersMark
    # offenders_mark: List[OffendersMark] = field(metadata={'length': 32}) # GP-0.3.6-eq:44 (H_o) | List of Ed25519 keys for offenders
    # author_key_idx: int = field(metadata={'length': 4})  # GP-0.3.6-eq:43 (H_i) | Index to identify the block author into th posterior state of the current validator set (kappa)
    # # TODO: double check: Appendix I.1.2. states that Bandersnatch Signatures (output of function blackboard F) have a length of 64 bytes.
    # vrf_signature: bytes = field(metadata={'length': 64})  # GP-0.3.6-eq:61 (H_v) | entropy-yielding VRF signature
    # # TODO: double check: Appendix I.1.2. states that Bandersnatch Signatures (output of function blackboard F) have a length of 64 bytes.
    # seal: bytes = field(metadata={'length': 64})  # GP-0.3.6-eq:59,60 (H_s) | seal signature


@dataclass
class Extrinsic(Serializable, State):
    # TODO: complete extrinsic type definition
    tickets: List[TicketEnvelope] = field(metadata={}) # GP-0.3.6-eq:14 (E_t) | Manages selection of validators for permissioning of block authoring

    # # TODO: suggestion for type definition of extrinsic below
    # tickets: List[TicketEnvelope] = field(metadata={}) # GP-0.3.6-eq:14 (E_t) | Manages selection of validators for permissioning of block authoring
    # # TODO: add placeholder dataclass for Judgement
    # # TODO: consider renaming judgement(s) to dispute(s)
    # judgements: List[Judgement] = field(metadata={}) # GP-0.3.6-eq:14 (E_d) | Votes by validators on disputes
    # # TODO: add placeholder dataclass for Preimage
    # preimages: List[Preimage] = field(metadata={}) # GP-0.3.6-eq:14 (E_p) | Static data presently being requested to be available for workloads to be able to fetch on demand
    # # TODO: add placeholder dataclass for Assurance
    # # TODO: consider renaming availability to assurances
    # availability: List[Assurance] = field(metadata={}) # GP-0.3.6-eq:14 (E_a) | Assurances by each validator concerning which of the input data of workloads they have correctly received and are storing locally
    # # TODO: add placeholder dataclass for Report
    # reports: List[Report] = field(metadata={}) # GP-0.3.6-eq:14 (E_g) | Reports of newly completed workloads whose accuracy is guaranteed by specific validators


@dataclass
class Block(Serializable, State):
    header: Header
    extrinsic: Extrinsic
