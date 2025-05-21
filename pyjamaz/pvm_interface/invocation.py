import logging
from dataclasses import dataclass
from typing import List, Dict

import numpy as np
import numpy.typing as npt

from pyjamaz.models.common import AccumulationOperand
from pyjamaz.models.state import AccumulationStateComponents, PvmAccumulateOutput, EntropyState, \
    AccumulateInvocationContext, AccumulatePvmArguments, ServiceAccount, DeferredTransfer, OnTransferPvmArguments, \
    OnTransferInvocationContext, PvmOnTransferOutput, ServicesState
from pyjamaz.pvm import PVMInterpreter
from pyjamaz.pvm.constants import ExitReason, ExitCondition
from pyjamaz.pvm.invocation import InvocationMutator, PVMInvocation, InvocationMutationOutput
from pyjamaz.pvm.types import PVMMemory
from pyjamaz.pvm_interface.hostcalls.accumulate import hc_bless, hc_assign, hc_designate, hc_checkpoint, hc_upgrade, \
    hc_transfer, hc_eject, hc_query, hc_solicit, hc_forget, hc_yield, hc_new, hc_provide
from pyjamaz.pvm_interface.hostcalls.constants import HostCallAccumulate, HostCallGeneral, HostCallDebug
from pyjamaz.pvm_interface.hostcalls.debug import hc_log
from pyjamaz.pvm_interface.hostcalls.general import hc_gas, hc_lookup, hc_read, hc_write, hc_info


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


# GP-0.6.4-section:B.4 | Accumulate Invocations
class AccumulateInvocationMutator(InvocationMutator):
    def execute(
            self,
            host_call_instr_nr: int,
            gas_limit: int,
            registers: List[int],
            memory: PVMMemory,
            invocation_context: AccumulateInvocationContext,
            _pvm: PVMInterpreter
    ) -> InvocationMutationOutput:
        """
        GP-0.6.4-eq:B.11 | F ∈ Ω⟨(X,X)⟩∶(n,ρ,ω,μ,(x,y))
        """
        logging.debug(f'PVM Accumulate host-call #{host_call_instr_nr}')

        invocation_output = InvocationMutationOutput(
            exit_condition=ExitCondition(reason=ExitReason.panic),
            gas_limit=gas_limit,
            registers=_pvm.reg,
            memory=_pvm.mem,
            context=invocation_context
        )

        service_id = invocation_context.context.service_account_id
        services = invocation_context.context.state_context.services

        match host_call_instr_nr:

            case HostCallDebug.log.value:
                hc_log(registers, memory, service_id, invocation_output, _pvm.log)

            case HostCallGeneral.gas.value:
                #GP-0.6.4-eq:B.12 | G
                hc_gas(registers, memory, invocation_output, _pvm.log)

            case HostCallGeneral.lookup.value:
                # GP-0.6.4-eq:B.12 | G
                service = services.retrieve_service_account(service_id)
                hc_lookup(registers, memory, service, service_id, services, invocation_output, _pvm.log)

            case HostCallGeneral.read.value:
                # GP-0.6.4-eq:B.12 | G
                service = services.retrieve_service_account(service_id)
                hc_read(registers, memory, service, service_id, services, invocation_output, _pvm.log)

            case HostCallGeneral.write.value:
                # GP-0.6.4-eq:B.12 | G
                service = services.retrieve_service_account(service_id)
                hc_write(registers, memory, service, service_id, services, invocation_output, _pvm.log)

            case HostCallGeneral.info.value:
                # GP-0.6.4-eq:B.12 | G
                service = services.retrieve_service_account(service_id)
                hc_info(registers, memory, service, service_id, services, invocation_output, _pvm.log)

            case HostCallAccumulate.bless.value:
                hc_bless(registers, memory, invocation_context, invocation_output, _pvm.log)

            case HostCallAccumulate.assign.value:
                hc_assign(registers, memory, invocation_context, invocation_output, _pvm.log)

            case HostCallAccumulate.designate.value:
                hc_designate(registers, memory, invocation_context, invocation_output, _pvm.log)

            case HostCallAccumulate.checkpoint.value:
                hc_checkpoint(registers, memory, invocation_context, invocation_output, _pvm.log)

            case HostCallAccumulate.upgrade.value:
                hc_upgrade(registers, memory, invocation_context, invocation_output, _pvm.log)

            case HostCallAccumulate.transfer.value:
                hc_transfer(registers, memory, invocation_context, invocation_output, _pvm.log)

            case HostCallAccumulate.eject.value:
                hc_eject(registers, memory, invocation_context, invocation_output, _pvm.log)

            case HostCallAccumulate.query.value:
                hc_query(registers, memory, invocation_context, invocation_output, _pvm.log)

            case HostCallAccumulate.solicit.value:
                hc_solicit(registers, memory, invocation_context, invocation_output, _pvm.log)

            case HostCallAccumulate.new.value:
                hc_new(registers, memory, invocation_context, invocation_output, _pvm.log)

            case HostCallAccumulate.forget.value:
                hc_forget(registers, memory, invocation_context, invocation_output, _pvm.log)

            case HostCallAccumulate._yield.value:
                hc_yield(registers, memory, invocation_context, invocation_output, _pvm.log)

            case HostCallAccumulate.provide.value:
                hc_provide(registers, memory, invocation_context, services, service_id, invocation_output, _pvm.log)
            case _:
                raise NotImplementedError(f"Accumulate invoked host-call {host_call_instr_nr} not implemented")

        return invocation_output


# GP-0.6.4-section:B.5 | On-Transfer Invocations
class OnTransferInvocationMutator(InvocationMutator):
    def execute(
            self,
            host_call_instr_nr: int,
            gas_limit: int,
            registers: List[int],
            memory: PVMMemory,
            invocation_context: OnTransferInvocationContext,
            _pvm: PVMInterpreter
    ) -> InvocationMutationOutput:

        logging.debug(f'PVM On-Transfer host-call #{host_call_instr_nr}')

        ctx_out = InvocationMutationOutput(
            exit_condition=ExitCondition(reason=ExitReason.panic),
            gas_limit=gas_limit,
            registers=_pvm.reg,
            memory=_pvm.mem,
            context=invocation_context
        )

        service_id = invocation_context.service_id
        services = invocation_context.services_state

        match host_call_instr_nr:

            case HostCallDebug.log.value:
                hc_log(registers, memory, service_id, ctx_out, _pvm.log)

            case HostCallGeneral.gas.value:
                #GP-0.6.4-eq:B.12 | G
                hc_gas(registers, memory, ctx_out, _pvm.log)

            case HostCallGeneral.lookup.value:
                # GP-0.6.4-eq:B.12 | G
                service = services.retrieve_service_account(service_id)
                hc_lookup(registers, memory, service, service_id, services, ctx_out, _pvm.log)

            case HostCallGeneral.read.value:
                # GP-0.6.4-eq:B.12 | G
                service = services.retrieve_service_account(service_id)
                hc_read(registers, memory, service, service_id, services, ctx_out, _pvm.log)

            case HostCallGeneral.write.value:
                # GP-0.6.4-eq:B.12 | G
                service = services.retrieve_service_account(service_id)
                hc_write(registers, memory, service, service_id, services, ctx_out, _pvm.log)

            case HostCallGeneral.info.value:
                # GP-0.6.4-eq:B.12 | G
                service = services.retrieve_service_account(service_id)
                hc_info(registers, memory, service, service_id, services, ctx_out, _pvm.log)

            case _:
                raise NotImplementedError(f"On-Transfer invoked host-call {host_call_instr_nr} not implemented")

        return ctx_out


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
    post_entropy: EntropyState

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
            gas_used=0,
            #preimages=[]
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
        start_offset=5, #TODO: constant?
        gas_limit=gas_limit,
        argument_data=argument_data
    )

    # GP-0.6.2-eq:B.12 (C)
    if marshalling_output.exit_condition.reason in [ExitReason.out_of_gas, ExitReason.panic]:

        output = PvmAccumulateOutput(
            state_context=marshalling_output.context.savepoint_context.state_context,
            deferred_transfers=marshalling_output.context.savepoint_context.deferred_transfers,
            accumulation_output=marshalling_output.context.savepoint_context.invocation_output,
            gas_used=marshalling_output.gas_used,
            # preimages=marshalling_output.context.savepoint_context.preimages TODO 0.6.6
        )
        logging.debug(f'PVM accumulate failed: {marshalling_output.exit_condition.reason}')
    elif marshalling_output.exit_condition.reason == ExitReason.halt and len(marshalling_output.exit_condition.value) > 0:
        output = PvmAccumulateOutput(
            state_context=marshalling_output.context.context.state_context,
            deferred_transfers=marshalling_output.context.context.deferred_transfers,
            accumulation_output=marshalling_output.exit_condition.value,
            gas_used=marshalling_output.gas_used,
            # preimages=marshalling_output.context.context.preimages TODO 0.6.6
        )
        logging.debug(f'PVM accumulate succesful, output=0x{output.accumulation_output.hex()}')
    else:
        output = PvmAccumulateOutput(
            state_context=marshalling_output.context.context.state_context,
            deferred_transfers=marshalling_output.context.context.deferred_transfers,
            accumulation_output=marshalling_output.context.context.invocation_output,
            gas_used=marshalling_output.gas_used,
            # preimages=marshalling_output.context.context.preimages TODO 0.6.6
        )
        logging.debug(f'PVM accumulate succesful, no output')

    return output


def pvm_invoke_on_transfer(
        services_state: ServicesState,
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

    service_account = services_state.services.get(service_id)
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
                invocation_context=OnTransferInvocationContext(
                    service_id=service_id,
                    service_account=service_account,
                    services_state=services_state
                ),
                invocation_mutator=OnTransferInvocationMutator()
            )

            gas_limit = sum([t.gas_limit for t in deferred_transfers])

            marshalling_output = pvm_invocation.pvm_invoke_marshalling(
                serialized_program=serialized_program,
                start_offset=10,    #TODO: constant?
                gas_limit=gas_limit,
                argument_data=argument_data
            )

            service_account = marshalling_output.context.service_account
            gas_used = gas_limit - marshalling_output.gas_limit

    return PvmOnTransferOutput(
        service_account=service_account,
        gas_used=gas_used
    )
