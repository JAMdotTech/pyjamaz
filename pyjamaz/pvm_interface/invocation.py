import logging
from dataclasses import dataclass
from typing import List, Dict

import numpy as np
import numpy.typing as npt

from pyjamaz.models.common import AccumulationOperand
from pyjamaz.models.state import AccumulationStateComponents, PvmAccumulateOutput, EntropyState, \
    AccumulateInvocationContext, AccumulatePvmArguments, ServiceAccount, DeferredTransfer, OnTransferPvmArguments, \
    OnTransferInvocationContext, PvmOnTransferOutput
from pyjamaz.pvm import PVMInterpreter
from pyjamaz.pvm.constants import ExitReason, ExitCondition
from pyjamaz.pvm.invocation import InvocationMutator, PVMInvocation, InvocationMutationOutput
from pyjamaz.pvm.types import PVMMemory
from pyjamaz.pvm_interface.hostcalls.accumulate import HostCallLookup, hc_bless
from pyjamaz.pvm_interface.hostcalls.constants import HostCallAccumulate


@dataclass
class GenericAccumulationInput:
    """
    """
    service_id: int
    invocation_context: AccumulateInvocationContext
    gas_before: int
    gas_limit: int
    registers: List[int]
    memory: PVMMemory


class AccumulateInvocationMutator(InvocationMutator):
    def execute(
            self,
            host_call_instr_nr: int,
            gas_limit: int,
            registers: npt.NDArray[np.uint64],
            memory: PVMMemory,
            invocation_context: AccumulateInvocationContext,
            _pvm: PVMInterpreter  # TODO: temporary, only used for logging calls, pass logger
    ) -> InvocationMutationOutput:
        """
        B.10 | F ∈ Ω⟨(X,X)⟩∶(n,ρ,ω,μ,(x,y))
        """
        logging.debug(f'PVM host-call #{host_call_instr_nr}')

        # ctx_in = InvocationInput(
        #     service_id=invocation_context.context.service_account_id,
        #     invocation_context=invocation_context,
        #     gas_before=int(_pvm.gas),
        #     gas_limit=gas_limit,
        #     registers=registers,
        #     memory=memory
        # )
        ctx_out = InvocationMutationOutput(
            exit_condition=ExitCondition(reason=ExitReason.panic),
            gas_limit=gas_limit,
            registers=registers,
            memory=memory,
            context=invocation_context
        )


        HostCallAccumulate.assign.value: hc_assign,
        HostCallAccumulate.designate.value: hc_designate,
        HostCallAccumulate.checkpoint.value: hc_checkpoint,
        HostCallAccumulate.new.value: hc_new,
        HostCallAccumulate.upgrade.value: hc_upgrade,
        HostCallAccumulate.transfer.value: hc_transfer,
        HostCallAccumulate.eject.value: hc_eject,
        HostCallAccumulate.query.value: hc_query,
        HostCallAccumulate.solicit.value: hc_solicit,
        HostCallAccumulate.forget.value: hc_forget,
        HostCallAccumulate._yield.value: hc_yield,

        match host_call_instr_nr:

            case HostCallAccumulate.bless.value:
                ctx_in = GenericAuccumulationInput(
                    service_id=invocation_context.context.service_account_id,
                    invocation_context=invocation_context,
                    gas_before=int(_pvm.gas),
                    gas_limit=gas_limit,
                    registers=registers,
                    memory=memory
                )
                hc_bless(ctx_in, ctx_out, _pvm.log)

        invoke_hostcall = HostCallLookup.get(host_call_instr_nr, None)
        if invoke_hostcall:
            #TODO: context / signature can be different per hostcall category -> general hostcalls should accept/work with both accumulate
            invoke_hostcall(ctx_in, ctx_out, _pvm.log)
        else:
            raise NotImplementedError(f"Host-call {host_call_instr_nr} not implemented")

        return ctx_out


class OnTransferInvocationMutator(InvocationMutator):
    def execute(
            self,
            host_call_instr_nr: int,
            gas_limit: int,
            registers: npt.NDArray[np.uint64],
            memory: PVMMemory,
            invocation_context: OnTransferInvocationContext,
            _pvm: PVMInterpreter  # TODO: TMP!
    ) -> InvocationMutationOutput:

        return InvocationMutationOutput(
            exit_condition=ExitCondition(reason=ExitReason.resume),
            gas_limit=gas_limit,
            registers=registers,
            memory=memory,
            context=invocation_context
        )


def pvm_invoke_accumulate(
        state_context: AccumulationStateComponents,
        timeslot: int,
        service_id: int,
        gas_limit: int,
        operands: List[AccumulationOperand],
        post_entropy: EntropyState
) -> PvmAccumulateOutput:
    """
    GP-0.6.4-eq:B.9 (Ψ_A) | Accumulation invocation function

    Parameters
    ----------
    state_context: AccumulationStateComponents
    timeslot: int
    service_id: int
    gas_limit: int
    operands: List[AccumulationOperand]

    Returns
    -------
    PvmAccumulateOutput
    """

    logging.debug(f'PVM invoke accumulate: s={service_id} operands={[o.to_json() for o in operands]}')

    invocation_context = state_context.to_invocation_context(
        service_account_id=service_id,
        entropy=post_entropy.entropy[0],
        timeslot=timeslot
    )
    try:
        code_hash = state_context.services.services[service_id].code_hash
        serialized_program = state_context.services.services[service_id].preimages[code_hash]
    except KeyError:
        # program not found
        return PvmAccumulateOutput(
            state_context=state_context,
            deferred_transfers=[],
            accumulation_output=None,
            gas_limit=0
        )

    argument_data = AccumulatePvmArguments(
        timeslot=timeslot,
        service_id=service_id,
        operands=operands,
    ).to_jam_bytes().to_bytes()

    pvm_invocation = PVMInvocation(
        invocation_context=invocation_context,
        invocation_mutator=AccumulateInvocationMutator()
    )

    marshalling_output = pvm_invocation.pvm_invoke_marshalling(
        serialized_program=serialized_program,
        start_offset=5,
        gas_limit=gas_limit,
        argument_data=argument_data
    )

    # GP-0.6.2-eq:B.12 (C)
    if marshalling_output.exit_condition.reason in [ExitReason.out_of_gas, ExitReason.panic]:

        output = PvmAccumulateOutput(
            state_context=marshalling_output.context.savepoint_context.state_context,
            deferred_transfers=marshalling_output.context.savepoint_context.deferred_transfers,
            accumulation_output=marshalling_output.context.savepoint_context.invocation_output,
            gas_limit=marshalling_output.gas_limit,
            gas_used=gas_limit - marshalling_output.gas_limit
        )
        logging.debug(f'PVM accumulate failed: {marshalling_output.exit_condition.reason}')
    elif marshalling_output.exit_condition.reason == ExitReason.halt and len(marshalling_output.exit_condition.value) > 0:
        output = PvmAccumulateOutput(
            state_context=marshalling_output.context.context.state_context,
            deferred_transfers=marshalling_output.context.context.deferred_transfers,
            accumulation_output=marshalling_output.exit_condition.value,
            gas_limit=marshalling_output.gas_limit,
            gas_used=gas_limit - marshalling_output.gas_limit
        )
        logging.debug(f'PVM accumulate succesful, output=0x{output.accumulation_output.hex()}')
    else:
        output = PvmAccumulateOutput(
            state_context=marshalling_output.context.context.state_context,
            deferred_transfers=marshalling_output.context.context.deferred_transfers,
            accumulation_output=marshalling_output.context.context.invocation_output,
            gas_limit=marshalling_output.gas_limit,
            gas_used=gas_limit - marshalling_output.gas_limit
        )
        logging.debug(f'PVM accumulate succesful, no output')

    return output


def pvm_invoke_on_transfer(
        services: Dict[int, ServiceAccount],
        timeslot: int,
        service_id: int,
        deferred_transfers: List[DeferredTransfer]
) -> PvmOnTransferOutput:
    """
    GP-0.6.2-eq:B.14 (Ψ_T) | the on-transfer service-account invocation function

    Parameters
    ----------
    services: Dict[int, ServiceAccount]
    timeslot: int
    service_id: int
    deferred_transfers: List[DeferredTransfer]

    Returns
    -------
    ServiceAccount
    """

    service_account = services.get(service_id)
    gas_used = 0

    if len(deferred_transfers) > 0:
        logging.debug(f'PVM invoke on_transfer: s={service_id} t={[t.to_json() for t in deferred_transfers]}')

        # Update balance
        service_account.balance += sum([t.amount for t in deferred_transfers])

        serialized_program = service_account.preimages.get(service_account.code_hash)

        if serialized_program:

            argument_data = OnTransferPvmArguments(
                timeslot=timeslot,
                service_id=service_id,
                deferred_transfers=deferred_transfers,
            ).to_jam_bytes().to_bytes()

            pvm_invocation = PVMInvocation(
                invocation_context=OnTransferInvocationContext(service_account=service_account),
                invocation_mutator=OnTransferInvocationMutator()
            )

            gas_limit = sum([t.gas_limit for t in deferred_transfers])

            marshalling_output = pvm_invocation.pvm_invoke_marshalling(
                serialized_program=serialized_program,
                start_offset=10,
                gas_limit=gas_limit,
                argument_data=argument_data
            )

            service_account = marshalling_output.context.service_account
            gas_used = marshalling_output.gas_limit

    return PvmOnTransferOutput(
        service_account=service_account,
        gas_used=gas_used
    )
