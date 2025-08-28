import typing
from copy import deepcopy
from dataclasses import dataclass, field
from typing import List, Optional, Dict

from jamcodec.mixins import Serializable
from jamcodec.types import U32, Vec, VarInt64, Bytes, H256, U16

from pyjamaz.hashing import blake2b_256_hash
from pyjamaz.models.common import AccumulationOperand, RefinementContext, WorkPackage, WorkExecResult
from pyjamaz.models.state import AccumulationStateComponents, DeferredTransfer, ServiceAccount, ServicesState

from pyjamaz.pvm.constants_new import ExitCondition
from pyjamaz.pvm.invocation import InvocationContext
from pyjamaz.pvm.types_new import PVMCode, PVMMemory


@dataclass
class PvmAccumulateOutput:
    state_context: AccumulationStateComponents
    deferred_transfers: List[DeferredTransfer]
    accumulation_output: Optional[bytes]
    gas_used: int
    preimages: List[typing.Tuple[int, bytes]]


@dataclass
class PvmOnTransferOutput:
    service_account: ServiceAccount
    gas_used: int


@dataclass
class PvmIsAuthorizedOutput:
    work_exec_result: WorkExecResult
    gas_used: int


@dataclass
class PvmRefineOutput:
    work_exec_result: WorkExecResult # r
    export_segments: List[bytes]     # bold_e GP-0.6.6-eq:B.6 [blackboard_G]
    gas_used: int                    # u


@dataclass
class AccumulateContextItem:
    """
    GP-0.6.2-eq:B.6 (X) | Invocation Result Context

    TODO check service_account_id in state_context.services
    """
    service_account_id: int  # s
    state_context: AccumulationStateComponents  # u
    new_service_account_id: int  # i
    deferred_transfers: List[DeferredTransfer]  # t
    invocation_output: Optional[bytes]  # y
    preimages: List[typing.Tuple[int, bytes]]  # p


@dataclass
class AccumulateInvocationContext(InvocationContext):
    """
    GP-0.6.4-eq:B.7 (X) | Invocation Result Context
    """
    context: AccumulateContextItem           # GP-0.6.4-eq:B.11 X_x
    savepoint_context: AccumulateContextItem # GP-0.6.4-eq:B.11 X_y
    timeslot: int # TODO how to make available?

    @classmethod
    def create_from_accumulation_state(
            cls, accumulation_state: AccumulationStateComponents, service_account_id: int, entropy: bytes, timeslot: int
    ) -> 'AccumulateInvocationContext':
        """
                B.10 (I)

                entropy: eta_0
                timeslot: int post_state

                """
        # Generate new unique service id
        check_payload = int.from_bytes(
            blake2b_256_hash(
                VarInt64.encode(service_account_id).to_bytes() +
                entropy +
                VarInt64.encode(timeslot).to_bytes()
            )[:4],
            byteorder='little'
        )

        new_service_account_id = accumulation_state.check_service_id((check_payload % (2 ** 32 - 2 ** 9)) + 2 ** 8)

        return AccumulateInvocationContext(
            context=AccumulateContextItem(
                service_account_id=service_account_id,
                state_context=deepcopy(accumulation_state),
                new_service_account_id=new_service_account_id,
                deferred_transfers=[],
                invocation_output=None,
                preimages=[]
            ),
            savepoint_context=AccumulateContextItem(
                service_account_id=service_account_id,
                state_context=deepcopy(accumulation_state),
                new_service_account_id=new_service_account_id,
                deferred_transfers=[],
                invocation_output=None,
                preimages = []
            ),
            timeslot=timeslot
        )


@dataclass
class AccumulatePvmArguments(Serializable):
    timeslot: int = field(metadata={'codec': VarInt64})
    service_id: int = field(metadata={'codec': VarInt64})
    operands_length: int = field(metadata={'codec': VarInt64})


@dataclass
class OnTransferInvocationContext(InvocationContext):
    service_id: int           # GP-0.6.4-eq:B.16 s
    service_account: ServiceAccount  # GP-0.6.4-eq:B.16 bold_s
    services_state: ServicesState # GP-0.6.4-eq:B.16 bold_D


@dataclass
class OnTransferPvmArguments(Serializable):
    timeslot: int = field(metadata={'codec': VarInt64})
    service_id: int = field(metadata={'codec': VarInt64})
    deferred_transfer_count: int = field(metadata={'codec': VarInt64})


@dataclass
class IsAuthorizedPvmArguments(Serializable):
    core_index: int = field(metadata={'codec': U16})


@dataclass
class RefinePvmArguments(Serializable):
    work_item_index: int = field(metadata={'codec': VarInt64})  # GP-0.6.6-eq:B.5 i
    service_id: int = field(metadata={'codec': VarInt64})  # GP-0.6.6-eq:B.5 w_s
    payload_blob: bytes = field(metadata={'codec': Bytes}) # GP-0.6.4-eq:B.5 w_y
    work_package_hash: bytes = field(metadata={'codec': H256}) # GP-0.6.4-eq:B.5 H(p)


@dataclass
class IntegratedPVM:
    """
    GP-0.6.4-eq:B.4 bold_M
    """
    code: PVMCode              # GP-0.6.4-eq:B.6 bold_p
    memory: PVMMemory            # GP-0.6.4-eq:B.6 bold_u
    program_counter: int     # GP-0.6.4-eq:B.6 italic_i


@dataclass
class RefineInvocationContext(InvocationContext):
    inner_pvm_lookup: Dict[int, IntegratedPVM]   # GP-0.6.4-eq:B.6 bold_M
    export_segments: List[bytes]                   # GP-0.6.4-eq:B.6 bold_e
