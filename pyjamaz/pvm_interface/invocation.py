import logging
from dataclasses import dataclass
from typing import List, Dict

from pyjamaz.constants import PVM_MARSHALLING_OFFSET_ACCUMULATE, PVM_MARSHALLING_OFFSET_TRANSFER, \
    PVM_MARSHALLING_OFFSET_AUTH, PVM_MARSHALLING_OFFSET_REFINE
from pyjamaz.exceptions import StateKeyNoResult
from pyjamaz.graypaper_constants import GAS_INVOKE, MAXIMUM_SIZE_SERVICE_CODE, MAXIMUM_SIZE_IS_AUTH_CODE
from pyjamaz.models.common import AccumulationOperand, Preimage, WorkPackage, WorkExecResult
from pyjamaz.models.state import AccumulationStateComponents, EntropyState, \
    ServiceAccount, DeferredTransfer, ServicesState
from pyjamaz.pvm_interface.models import PvmAccumulateOutput, PvmOnTransferOutput, PvmIsAuthorizedOutput, \
    PvmRefineOutput, AccumulateInvocationContext, AccumulatePvmArguments, OnTransferInvocationContext, \
    OnTransferPvmArguments, IsAuthorizedPvmArguments, RefinePvmArguments, RefineInvocationContext
from pyjamaz.pvm import PVMInterpreter
from pyjamaz.pvm.constants import ExitReason, ExitCondition
from pyjamaz.pvm.invocation import InvocationMutator, PVMInvocation, InvocationMutationOutput
from pyjamaz.pvm.types import PVMMemory
from pyjamaz.pvm_interface.hostcalls.accumulate import hc_bless, hc_assign, hc_designate, hc_checkpoint, hc_upgrade, \
    hc_transfer, hc_eject, hc_query, hc_solicit, hc_forget, hc_yield, hc_new, hc_provide
from pyjamaz.pvm_interface.hostcalls.constants import HostCallAccumulate, HostCallGeneral, HostCallDebug, HostCallRefine
from pyjamaz.pvm_interface.hostcalls.debug import hc_log
from pyjamaz.pvm_interface.hostcalls.general import hc_gas, hc_lookup, hc_read, hc_write, hc_info, hc_fetch
from pyjamaz.pvm_interface.hostcalls.refine import hc_historical_lookup, hc_export, hc_machine, hc_peek, \
    hc_poke, hc_zero, hc_void, hc_invoke, hc_expunge
from pyjamaz.utils import format_hash


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

    def __init__(self, post_entropy: EntropyState, accumulation_operands: List[AccumulationOperand]):
        self.post_entropy = post_entropy
        self.accumulation_operands = accumulation_operands

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

            case HostCallGeneral.fetch.value:
                # GP-0.6.6-eq:B.11 | Y
                hc_fetch(
                    registers=registers,
                    memory=memory,
                    work_package=None,
                    entropy=self.post_entropy.entropy[0],
                    authorizer_output=None,
                    work_item_index=None,
                    work_item_segs=None,
                    extrinsics=None,
                    accumulation_operands=self.accumulation_operands,
                    deferred_transfers=None,
                    invocation_output=invocation_output,
                    logger=_pvm.log
                )

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
                # TODO: implement B.16: (▸,ϱ−10,[ω0,...,ω6,WHAT,ω8,...],µ,s) otherwise
                raise NotImplementedError(f"Accumulate invoked host-call {host_call_instr_nr} not implemented")

        return invocation_output


# GP-0.6.4-section:B.5 | On-Transfer Invocations
class OnTransferInvocationMutator(InvocationMutator):

    def __init__(self, deferred_transfers: List[DeferredTransfer], post_entropy: EntropyState):
        self.deferred_transfers = deferred_transfers
        self.post_entropy = post_entropy

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

            case HostCallGeneral.fetch.value:
                hc_fetch(
                    registers=registers,
                    memory=memory,
                    work_package=None,
                    entropy=self.post_entropy.entropy[0],
                    authorizer_output=None,
                    work_item_index=None,
                    work_item_segs=None,
                    extrinsics=None,
                    accumulation_operands=None,
                    deferred_transfers=self.deferred_transfers,
                    invocation_output=ctx_out,
                    logger=_pvm.log
                )

            case _:
                #TODO: implement B.16: (▸,ϱ−10,[ω0,...,ω6,WHAT,ω8,...],µ,s) otherwise
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

    invocation_context = AccumulateInvocationContext.create_from_accumulation_state(
        accumulation_state=state_context,
        service_account_id=service_id,
        entropy=post_entropy.entropy[0],
        timeslot=timeslot
    )

    try:

        service_account = state_context.services.retrieve_service_account(service_id)
        preimage_blob = state_context.services.retrieve_preimage(
            service_account_id=service_id,
            preimage_hash=service_account.code_hash
        )

        preimage = Preimage.extract(preimage_blob)
        serialized_program = preimage.serialized_program
        program_metadata = preimage.program_name
    except StateKeyNoResult:
        # Program not found
        preimage_blob = None

    if preimage_blob is None or len(preimage_blob) > MAXIMUM_SIZE_SERVICE_CODE:
        return PvmAccumulateOutput(
            state_context=state_context,
            deferred_transfers=[],
            accumulation_output=None,
            gas_used=0,
            preimages=[]
        )

    argument_data = AccumulatePvmArguments(
        timeslot=timeslot,
        service_id=service_id,
        operands_length=len(operands),
    ).to_jam_bytes().to_bytes()

    pvm_invocation = PVMInvocation(
        invocation_context=invocation_context,
        invocation_mutator=AccumulateInvocationMutator(
            post_entropy=post_entropy,
            accumulation_operands=operands,
        )
    )

    marshalling_output = pvm_invocation.pvm_invoke_marshalling(
        serialized_program=serialized_program,
        start_offset=PVM_MARSHALLING_OFFSET_ACCUMULATE,
        gas_limit=gas_limit,
        argument_data=argument_data,
        program_name=program_metadata
    )

    # GP-0.6.2-eq:B.12 (C)
    if marshalling_output.exit_condition.reason in [ExitReason.out_of_gas, ExitReason.panic]:

        output = PvmAccumulateOutput(
            state_context=marshalling_output.context.savepoint_context.state_context,
            deferred_transfers=marshalling_output.context.savepoint_context.deferred_transfers,
            accumulation_output=marshalling_output.context.savepoint_context.invocation_output,
            gas_used=marshalling_output.gas_used,
            preimages=marshalling_output.context.savepoint_context.preimages
        )
        logging.info(f'PVM accumulate failed: {marshalling_output.exit_condition.reason}')
    elif marshalling_output.exit_condition.reason == ExitReason.halt and len(marshalling_output.exit_condition.value) > 0:
        output = PvmAccumulateOutput(
            state_context=marshalling_output.context.context.state_context,
            deferred_transfers=marshalling_output.context.context.deferred_transfers,
            accumulation_output=marshalling_output.exit_condition.value,
            gas_used=marshalling_output.gas_used,
            preimages=marshalling_output.context.context.preimages
        )
        logging.debug(f'PVM accumulate successful, output=0x{output.accumulation_output.hex()}')
    else:
        output = PvmAccumulateOutput(
            state_context=marshalling_output.context.context.state_context,
            deferred_transfers=marshalling_output.context.context.deferred_transfers,
            accumulation_output=marshalling_output.context.context.invocation_output,
            gas_used=marshalling_output.gas_used,
            preimages=marshalling_output.context.context.preimages
        )
        logging.debug(f'PVM accumulate successful, no output')

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

    service_account = services_state.retrieve_service_account(service_id)
    preimage_blob = service_account.preimages.get(service_account.code_hash)
    gas_used = 0

    serialized_program = None
    program_name = None

    if preimage_blob is not None:
        try:
            preimage = Preimage.extract(preimage_blob)
            serialized_program = preimage.serialized_program
            program_name = preimage.program_name
        except Exception:
            pass

    if serialized_program is not None and len(serialized_program) <= MAXIMUM_SIZE_SERVICE_CODE and len(deferred_transfers) > 0:
        logging.info(f'💸 Processing transfer: s={service_id} t={[t.to_json() for t in deferred_transfers]}')

        # Update balance
        service_account.balance += sum([t.amount for t in deferred_transfers])

        argument_data = OnTransferPvmArguments(
            timeslot=timeslot,
            service_id=service_id,
            deferred_transfer_count=len(deferred_transfers),
        ).to_jam_bytes().to_bytes()

        pvm_invocation = PVMInvocation(
            invocation_context=OnTransferInvocationContext(
                service_id=service_id,
                service_account=service_account,
                services_state=services_state
            ),
            invocation_mutator=OnTransferInvocationMutator(deferred_transfers=deferred_transfers)
        )

        gas_limit = sum([t.gas_limit for t in deferred_transfers])

        marshalling_output = pvm_invocation.pvm_invoke_marshalling(
            serialized_program=serialized_program,
            start_offset=PVM_MARSHALLING_OFFSET_TRANSFER,
            gas_limit=gas_limit,
            argument_data=argument_data,
            program_name=program_name
        )

        service_account = marshalling_output.context.service_account
        gas_used = marshalling_output.gas_used

    return PvmOnTransferOutput(
        service_account=service_account,
        gas_used=gas_used
    )


# GP-0.6.4-section:B.5 | On-Transfer Invocations
class IsAuthorizedInvocationMutator(InvocationMutator):

    def __init__(self, work_package: WorkPackage):
        self.work_package = work_package

    def execute(
            self,
            host_call_instr_nr: int,
            gas_limit: int,
            registers: List[int],
            memory: PVMMemory,
            invocation_context: None,
            _pvm: PVMInterpreter
    ) -> InvocationMutationOutput:

        logging.debug(f'PVM Is-Authorized host-call #{host_call_instr_nr}')

        ctx_out = InvocationMutationOutput(
            exit_condition=ExitCondition(reason=ExitReason.panic),
            gas_limit=gas_limit,
            registers=_pvm.reg,
            memory=_pvm.mem,
            context=invocation_context
        )

        match host_call_instr_nr:

            case HostCallDebug.log.value:
                hc_log(registers, memory, -1, ctx_out, _pvm.log)

            case HostCallGeneral.gas.value:
                #GP-0.6.4-eq:B.12 | G
                hc_gas(registers, memory, ctx_out, _pvm.log)

            case HostCallGeneral.fetch.value:
                # GP-0.6.4-eq:B.12 | G
                hc_fetch(
                    registers=registers,
                    memory=memory,
                    work_package=self.work_package,
                    entropy=None,
                    authorizer_output=None,
                    work_item_index=None,
                    work_item_segs=None,
                    extrinsics=None,
                    accumulation_operands=None,
                    deferred_transfers=None,
                    invocation_output=ctx_out,
                    logger=_pvm.log
                )
            case _:
                #TODO: implement B.2: (▸,ϱ−10,[ω0,...,ω6,WHAT,ω8,...],µ,s) otherwise
                raise NotImplementedError(f"On-Transfer invoked host-call {host_call_instr_nr} not implemented")

        return ctx_out


def pvm_invoke_is_authorized(
        work_package: 'WorkPackage',
        core_index: int
) -> PvmIsAuthorizedOutput:
    """
    GP-0.6.4-eq:B.1 (Ψ_I) | the is-authorized invocation function

    Parameters
    ----------

    Returns
    -------
    """

    if work_package.authorization_code is None:
        return PvmIsAuthorizedOutput(
            work_exec_result=WorkExecResult(bad_code=True),
            gas_used=0
        )

    elif len(work_package.authorization_code) > MAXIMUM_SIZE_IS_AUTH_CODE:
        return PvmIsAuthorizedOutput(
            work_exec_result=WorkExecResult(code_oversize=True),
            gas_used=0
        )

    argument_data = IsAuthorizedPvmArguments(
        core_index=core_index
    ).to_jam_bytes().to_bytes()

    pvm_invocation = PVMInvocation(
        invocation_context=None,
        invocation_mutator=IsAuthorizedInvocationMutator(work_package=work_package)
    )

    work_package_hash = work_package.hash()

    logging.debug(f'PVM is-auth: wp={format_hash(work_package_hash)} c={core_index} a={argument_data.hex()}')

    marshalling_output = pvm_invocation.pvm_invoke_marshalling(
        serialized_program=work_package.authorization_code,
        start_offset=PVM_MARSHALLING_OFFSET_AUTH,
        gas_limit=GAS_INVOKE,
        argument_data=argument_data,
        program_name=work_package.authorization_metadata
    )

    logging.debug(f'PVM is-auth result: exit={marshalling_output.exit_condition.reason} v={marshalling_output.exit_condition.value}')

    return PvmIsAuthorizedOutput(
        work_exec_result=WorkExecResult.from_exit_condition(marshalling_output.exit_condition),
        gas_used=marshalling_output.gas_used
    )



# GP-0.6.4-section:B.5 | Refine Invocations
class RefineInvocationMutator(InvocationMutator):
    def __init__(
        self,
        authorizer_output: bytes,
        work_items_import_segments: List[List[bytes]],
        export_segment_offset: int,
        services: ServicesState,
        service_account_id: int,
        timeslot: int,
        work_item_index: int,
        work_package: WorkPackage,
        extrinsics: List[List[bytes]]
    ):
        self.authorizer_output = authorizer_output
        self.work_items_import_segments = work_items_import_segments
        self.export_segment_offset = export_segment_offset
        self.services = services
        self.service_account_id = service_account_id
        self.timeslot = timeslot
        self.work_item_index = work_item_index
        self.work_package = work_package
        self.extrinsics = extrinsics

    def execute(
            self,
            host_call_instr_nr: int,
            gas_limit: int,
            registers: List[int],
            memory: PVMMemory,
            invocation_context: RefineInvocationContext,
            _pvm: PVMInterpreter
    ) -> InvocationMutationOutput:

        logging.debug(f'PVM Refine host-call #{host_call_instr_nr}')

        ctx_out = InvocationMutationOutput(
            exit_condition=ExitCondition(reason=ExitReason.panic),
            gas_limit=gas_limit,
            registers=_pvm.reg,
            memory=_pvm.mem,
            context=invocation_context
        )

        match host_call_instr_nr:

            case HostCallDebug.log.value:
                hc_log(registers, memory, self.service_account_id, ctx_out, _pvm.log)

            case HostCallGeneral.gas.value:
                #GP-0.6.4-eq:B.12 | G
                hc_gas(registers, memory, ctx_out, _pvm.log)

            case HostCallRefine.historical_lookup.value:
                #GP-0.6.4-eq:B.12 | G
                hc_historical_lookup(
                    registers=registers,
                    memory=memory,
                    m_e=invocation_context,
                    services=self.services,
                    service_id=self.service_account_id,
                    timeslot=self.timeslot,
                    invocation_output=ctx_out,
                    logger=_pvm.log
                )

            case HostCallGeneral.fetch.value:

                hc_fetch(
                    registers=registers,
                    memory=memory,
                    work_package=self.work_package,
                    entropy=bytes(32),
                    authorizer_output=self.authorizer_output,
                    work_item_index=self.work_item_index,
                    work_item_segs=self.work_items_import_segments,
                    extrinsics=self.extrinsics,
                    accumulation_operands=None,
                    deferred_transfers=None,
                    invocation_output=ctx_out,
                    logger=_pvm.log
                )

            case HostCallRefine.export.value:
                hc_export(
                    registers=registers,
                    memory=memory,
                    m_e=invocation_context,
                    export_segment_offset=self.export_segment_offset,
                    invocation_output=ctx_out,
                    logger=_pvm.log
                )

            case HostCallRefine.machine.value:
                hc_machine(
                    registers=registers,
                    memory=memory,
                    m_e=invocation_context,
                    invocation_output=ctx_out,
                    logger=_pvm.log
                )

            case HostCallRefine.peek.value:
                hc_peek(
                    registers=registers,
                    memory=memory,
                    m_e=invocation_context,
                    invocation_output=ctx_out,
                    logger=_pvm.log
                )

            case HostCallRefine.poke.value:
                hc_poke(
                    registers=registers,
                    memory=memory,
                    m_e=invocation_context,
                    invocation_output=ctx_out,
                    logger=_pvm.log
                )

            case HostCallRefine.zero.value:
                hc_zero(
                    registers=registers,
                    memory=memory,
                    m_e=invocation_context,
                    invocation_output=ctx_out,
                    logger=_pvm.log
                )

            case HostCallRefine.void.value:
                hc_void(
                    registers=registers,
                    memory=memory,
                    m_e=invocation_context,
                    invocation_output=ctx_out,
                    logger=_pvm.log
                )

            case HostCallRefine.invoke.value:
                hc_invoke(
                    registers=registers,
                    memory=memory,
                    m_e=invocation_context,
                    invocation_output=ctx_out,
                    logger=_pvm.log
                )

            case HostCallRefine.expunge.value:
                hc_expunge(
                    registers=registers,
                    memory=memory,
                    m_e=invocation_context,
                    invocation_output=ctx_out,
                    logger=_pvm.log
                )

            case _:
                #TODO: implement B.2: (▸,ϱ−10,[ω0,...,ω6,WHAT,ω8,...],µ,s) otherwise
                raise NotImplementedError(f"Refine invoked host-call {host_call_instr_nr} not implemented")

        return ctx_out


# GP-0.6.6-eq:B.5: ΨR (refine invoke)
def pvm_invoke_refine(
    work_item_index: int,      # GP-0.6.4-eq:B.5: italic_i index of workitem
    work_package: 'WorkPackage', # GP-0.6.4-eq:B.5: italic_p workpackage
    authorizer_output: bytes,  # GP-0.6.4-eq:B.5: bold_r is_authorized output
    work_items_import_segments: List[List[bytes]],  # GP-0.6.4-eq:B.5: bold_i_flat list of import segments per workitem
    export_segment_offset: int, # GP-0.6.4-eq:B.5: c_cedie export segment offset
    services_state: ServicesState,
    extrinsics: List[List[bytes]] # GP-0.6.6-eq:B.6: x_flat list of extrinsics per workitem
) -> PvmRefineOutput:
    """
    GP-0.6.6-eq:B.5 (Ψ_R) | the refine service-account invocation function

    # TODO integrate with app?

    Parameters
    ----------

    Returns
    -------
    """
    work_item = work_package.items[work_item_index]
    service_account_id = work_item.service

    # GP-0.6.6-eq:B.5 (extract preimage data)
    preimage_data = services_state.historical_preimage_lookup(
        service_account_id,
        work_package.context.lookup_anchor_slot,
        work_item.code_hash
    )

    if preimage_data is None:
        return PvmRefineOutput(
            work_exec_result=WorkExecResult(bad_code=True),
            export_segments=[],
            gas_used=0
        )
    elif len(preimage_data) > MAXIMUM_SIZE_SERVICE_CODE:
        return PvmRefineOutput(
            work_exec_result=WorkExecResult(code_oversize=True),
            export_segments=[],
            gas_used=0
        )

    preimage = Preimage.extract(preimage_data)

    work_package_hash = work_package.hash()

    argument_data = RefinePvmArguments(
        work_item_index=work_item_index,
        service_id=service_account_id,
        payload_blob=work_item.payload,
        work_package_hash=work_package_hash
    ).to_jam_bytes().to_bytes()

    logging.debug(f'PVM refine start: wp={format_hash(work_package_hash)} a={argument_data.hex()}')

    pvm_invocation = PVMInvocation(
        invocation_context=RefineInvocationContext(
            inner_pvm_lookup={},
            export_segments=[]
        ),
        invocation_mutator=RefineInvocationMutator(
            authorizer_output=authorizer_output,
            work_items_import_segments=work_items_import_segments,
            export_segment_offset=export_segment_offset,
            services=services_state,
            service_account_id=service_account_id,
            timeslot=work_package.context.lookup_anchor_slot,
            work_package=work_package,
            work_item_index=work_item_index,
            extrinsics=extrinsics
        )
    )

    marshalling_output = pvm_invocation.pvm_invoke_marshalling(
        serialized_program=preimage.serialized_program,
        start_offset=PVM_MARSHALLING_OFFSET_REFINE,
        gas_limit=GAS_INVOKE,
        argument_data=argument_data,
        program_name=preimage.program_name
    )

    work_exec_result = WorkExecResult.from_exit_condition(marshalling_output.exit_condition)

    logging.debug(f'PVM refine work result: {work_exec_result.to_json()}')

    return PvmRefineOutput(
        work_exec_result=work_exec_result,
        export_segments=marshalling_output.context.export_segments,
        gas_used=marshalling_output.gas_used
    )
