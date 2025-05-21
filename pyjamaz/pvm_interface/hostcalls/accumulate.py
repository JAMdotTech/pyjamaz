from copy import deepcopy
from typing import List

from jamcodec.base import JamBytes
from jamcodec.types import U64, U32

from pyjamaz.exceptions import StateKeyNoResult
from pyjamaz.graypaper_constants import MAXIMUM_AUTHORIZATION_QUEUE_ITEMS, CORE_COUNT, VALIDATOR_COUNT, \
    PREIMAGE_EXPUNGE_TIMESLOTS, SIZE_TRANSFER_MEMO
from pyjamaz.hashing import blake2b_256_hash
from pyjamaz.models.common import ValidatorData
from pyjamaz.models.state import ServiceAccount, DeferredTransfer, AccumulateInvocationContext, ServicesState
from pyjamaz.pvm.constants import ExitCondition, ExitReason
from pyjamaz.pvm.exceptions import PVMMemoryError
from pyjamaz.pvm.invocation import InvocationMutationOutput
from pyjamaz.pvm.types import PVMMemoryMode, PVMLogger, PVMMemory
from pyjamaz.pvm_interface.hostcalls.constants import HostCallResult, HostCallDebug, HostCallGeneral, HostCallAccumulate
from pyjamaz.utils import format_hash


def hc_bless(
        registers: List[int],
        memory: PVMMemory,
        ctx_in: AccumulateInvocationContext,
        output: InvocationMutationOutput,
        logger: PVMLogger):
    """
    State transition function for privileged services.
    Updates gas limits for privileged services
    """
    logger.hc_regs(f"BLESS", "accumulate")

    output.gas_limit -= 10

    # Privileged services:
    m = registers[7] # m: index of manager service (manager of chi(X))
    a = registers[8] # a: index of assign service (authorization queue)
    v = registers[9] # v: index of designate service (validator queue)

    o = registers[10] # offset to read service indices and accompanying gas limits from
    n = registers[11] # number of entries in the auto_accumulate_services dictionary to read

    auto_accumulate_services = None #GP: bold_g
    if memory.is_accessible(o, 12 * n, PVMMemoryMode.readable):
        try:
            auto_accumulate_services = {}
            for idx in range(n):
                offset = o + idx * 12
                service_idx = U32.decode(JamBytes(memory.read_bytes(offset, 4)))
                gas = U64.decode(JamBytes(memory.read_bytes(offset + 4, 4+8)))
                auto_accumulate_services[service_idx] = gas
        except PVMMemoryError:
            auto_accumulate_services = None   # bold_g = ∇

    try:
        service_exists = any(ctx_in.context.state_context.services.retrieve_service_account(idx) for idx in [m, a, v])
    except (StateKeyNoResult, OverflowError):
        service_exists = False

    if auto_accumulate_services is None:
        output.exit_condition = ExitCondition(reason=ExitReason.panic)
        logger.hc_log("BLESS PANIC", f"m={m} a={a} v={v}")
    #TODO: volgens GP hoeven we alleen ints te checken?
    #elif any(idx >= 2**32 for idx in [m, a, v]):
    elif not service_exists:
        output.exit_condition = ExitCondition(reason=ExitReason.resume)
        output.registers[7] = HostCallResult.WHO.value
        logger.hc_log("BLESS WHO", f"m={m} a={a} v={v}")
    else:
        output.exit_condition = ExitCondition(reason=ExitReason.resume)
        output.registers[7] = HostCallResult.OK.value

        # TODO: mark dirty? maybe register changes
        ps = ctx_in.context.state_context.privileged_services
        ps.empower_service = m
        ps.assign_service = a
        ps.designate_service = v
        ps.auto_accumulate_services = auto_accumulate_services

        logger.hc_log("BLESS OK", f"m={m} a={a} v={v}")


def hc_assign(
        registers: List[int],
        memory: PVMMemory,
        ctx_in: AccumulateInvocationContext,
        output: InvocationMutationOutput,
        logger: PVMLogger):
    """
    Update authorization queue (state transition function of Phi)
    """
    logger.hc_regs(f"ASSIGN", "accumulate")
    output.gas_limit -= 10

    # Privileged services:
    core_index = registers[7] # Core index to update (0..341)
    o = registers[8] # memory offset

    if memory.is_accessible(o, 32 * MAXIMUM_AUTHORIZATION_QUEUE_ITEMS, PVMMemoryMode.readable):
        authorization_queue = [] #GP: bold_c
        try:
            for idx in range(MAXIMUM_AUTHORIZATION_QUEUE_ITEMS):
                offset = o + idx * 32
                authorization_queue.append(memory.read_bytes(offset, 32))
        except PVMMemoryError:
            authorization_queue = None
    else:
        authorization_queue = None # bold_c = ∇

    if authorization_queue is None:
        output.exit_condition = ExitCondition(reason=ExitReason.panic)
        logger.hc_log("ASSIGN PANIC", f"c={core_index}")
    elif core_index >= CORE_COUNT:
        output.exit_condition = ExitCondition(reason=ExitReason.resume)
        output.registers[7] = HostCallResult.CORE.value
        logger.hc_log("ASSIGN CORE", f"c={core_index}")
    else:
        output.exit_condition = ExitCondition(reason=ExitReason.resume)
        output.registers[7] = HostCallResult.OK.value
        # TODO: mark dirty? maybe register changes
        ctx_in.context.state_context.authorizer_queues.authorizer_queues[core_index] = authorization_queue
        logger.hc_log("ASSIGN OK", f"c={core_index} o={o}")


def hc_designate(
        registers: List[int],
        memory: PVMMemory,
        ctx_in: AccumulateInvocationContext,
        output: InvocationMutationOutput,
        logger: PVMLogger):
    """
    Update the validator Queue (State transition function for the validator queue)
    """
    logger.hc_regs(f"DESIGNATE", "accumulate")
    output.gas_limit -= 10

    o = registers[7] # memory offset

    if memory.is_accessible(o, 336 * VALIDATOR_COUNT, PVMMemoryMode.readable):
        validator_queue = [] #GP: bold_v
        try:
            for idx in range(MAXIMUM_AUTHORIZATION_QUEUE_ITEMS):
                offset = o + idx * 336
                validator_data = ValidatorData.from_jam_bytes(JamBytes(memory.read_bytes(offset, 336)))
                validator_queue.append(validator_data)
        except PVMMemoryError:
            validator_queue = None # GP: bold_v = ∇
    else:
        validator_queue = None # GP: bold_v = ∇

    if validator_queue is None:
        output.exit_condition = ExitCondition(reason=ExitReason.panic)
        logger.hc_log("DESIGNATE PANIC", f"o={o}")
    else:
        output.exit_condition = ExitCondition(reason=ExitReason.resume)
        output.registers[7] = HostCallResult.OK.value
        # TODO: mark dirty? maybe register changes
        ctx_in.context.state_context.validator_queue.validators = validator_queue
        logger.hc_log("DESIGNATE OK", f"o={o}")


def hc_checkpoint(
        registers: List[int],
        memory: PVMMemory,
        ctx_in: AccumulateInvocationContext,
        output: InvocationMutationOutput,
        logger: PVMLogger):
    """
    Copy the invocation result context x to y
    """
    logger.hc_regs(f"CHECKPOINT", "accumulate")
    output.gas_limit -= 10
    output.registers[7] = output.gas_limit
    output.exit_condition = ExitCondition(reason=ExitReason.resume)
    # TODO: optimize deepcopy?
    ctx_in.savepoint_context = deepcopy(ctx_in.context)


def hc_new(
        registers: List[int],
        memory: PVMMemory,
        ctx_in: AccumulateInvocationContext,
        output: InvocationMutationOutput,
        logger: PVMLogger):
    """
    Creates a new service
    """
    logger.hc_regs(f"NEW", "accumulate")
    output.gas_limit -= 10

    o = registers[7]  # offset to read service data from
    l = registers[8]  # size (byte length) of the code blob
    g = registers[9]  # gas_limit_accumulate
    m = registers[10] # gas_limit_on_transfer

    code_hash = None
    if 0 < l < 2**32 and memory.is_accessible(o, 32, PVMMemoryMode.readable):
        try:
            code_hash = memory.read_bytes(o, 32)  # GP: c
        except PVMMemoryError:
            pass

    service_id = ctx_in.context.service_account_id
    service_account = None
    new_service_id = None
    deducted_balance = None
    new_service_account = None  # GP: bold_s
    if not code_hash is None:
        new_service_account = ServiceAccount(
            code_hash=code_hash,
            balance=0,
            gas_limit_accumulate=g,
            gas_limit_on_transfer=m,
            footprint_storage_items=0,
            footprint_storage_bytes=0,
            storage_items={},  # bold_s
            preimages={},  # bold_p
            preimage_availability={}  # {(code_hash, l): []} #bold_l
        )
        new_service_id = ctx_in.context.new_service_account_id
        new_service_account.update_footprint_add_preimage(l)
        new_service_account.balance = new_service_account.threshold_balance
        service_account = ctx_in.context.state_context.services.retrieve_service_account(service_id)
        deducted_balance = service_account.balance - new_service_account.threshold_balance

    if code_hash is None:
        output.exit_condition = ExitCondition(reason=ExitReason.panic)
        logger.hc_log("NEW PANIC", f"old_service={service_id}")
    elif deducted_balance < service_account.threshold_balance:
        output.exit_condition = ExitCondition(reason=ExitReason.resume)
        output.registers[7] = HostCallResult.CASH.value
        logger.hc_log("NEW CASH", f"old_service={service_id} deducted_balance={deducted_balance} threshold_balance={service_account.threshold_balance} code_hash={code_hash} code_len={l}")
    else:
        output.exit_condition = ExitCondition(reason=ExitReason.resume)
        output.registers[7] = new_service_id
        updated_new_service_id = 2 ** 8 + (new_service_id - 2 ** 8 + 42) % (2 ** 32 - 2 ** 9)
        # TODO: mark dirty? maybe register changes
        ctx_in.context.new_service_account_id = ctx_in.context.state_context.check_service_id(
            updated_new_service_id)
        service_account.balance = deducted_balance
        # TODO inefficient; move to end, only once per service
        ctx_in.context.state_context.services.store_service_account(service_id, service_account)
        # TODO inefficient; move to end, only once per service
        ctx_in.context.state_context.services.store_service_account(new_service_id, new_service_account)
        ctx_in.context.state_context.services.store_preimage_availability(new_service_id, code_hash, l, [])
        logger.hc_log("NEW OK", f"old_service={service_id} code_hash={code_hash} code_len={l}")


def hc_upgrade(
        registers: List[int],
        memory: PVMMemory,
        ctx_in: AccumulateInvocationContext,
        output: InvocationMutationOutput,
        logger: PVMLogger):
    """
    Updates codehash and gas limits for a service account
    """
    logger.hc_regs(f"UPGRADE", "accumulate")
    output.gas_limit -= 10

    o = registers[7]  # offset for service codehash
    g = registers[8]  # gas_limit_accumulate
    m = registers[9]  # gas_limit_on_transfer

    service_id = ctx_in.context.service_account_id
    service_account = ctx_in.context.state_context.services.retrieve_service_account(service_id)

    try:
        code_hash = memory.read_bytes(o, 32)
    except PVMMemoryError:
        code_hash = None # GP: c = ∇

    if code_hash is None:
        output.exit_condition = ExitCondition(reason=ExitReason.panic)
        logger.hc_log("UPGRADE PANIC", "")
    else:
        output.exit_condition = ExitCondition(reason=ExitReason.resume)
        output.registers[7] = HostCallResult.OK.value

        # TODO: mark dirty? maybe register changes
        service_account.code_hash = code_hash
        service_account.gas_limit_accumulate = g
        service_account.gas_limit_on_transfer = m
        # TODO inefficient; move to end, only once per service
        ctx_in.context.state_context.services.store_service_account(service_id, service_account)
        logger.hc_log("UPGRADE OK", f"code_hash={code_hash} ")


def hc_transfer(
        registers: List[int],
        memory: PVMMemory,
        ctx_in: AccumulateInvocationContext,
        output: InvocationMutationOutput,
        logger: PVMLogger):
    """
    Create a new transfer and add to the deferred transfers
    """
    logger.hc_regs(f"TRANSFER", "accumulate")
    gas_cost = 10 + registers[9]
    output.gas_limit -= gas_cost

    d = registers[7]     # destination
    a = registers[8]     # amount
    g = registers[9]     # gas_limit
    o = registers[10]    # offset for memo

    service_id = ctx_in.context.service_account_id
    service_account = ctx_in.context.state_context.services.retrieve_service_account(service_id)
    try:
        dest_service_account = ctx_in.context.state_context.services.retrieve_service_account(d)   #GP: bold_d
    except StateKeyNoResult:
        dest_service_account = None

    try:
        m = memory.read_bytes(o, SIZE_TRANSFER_MEMO)   # Transaction Memo (blob)
        # GP: bold_t
        transfer = DeferredTransfer(
            sender=service_id,
            receiver=d,
            amount=a,
            memo=m,
            gas_limit=g,
        )
        b = service_account.balance - a
    except PVMMemoryError:
        transfer = None
        b = None

    if transfer is None:
        output.exit_condition = ExitCondition(reason=ExitReason.panic)
    elif dest_service_account is None:
        output.exit_condition = ExitCondition(reason=ExitReason.resume)
        output.registers[7] = HostCallResult.WHO.value
        logger.hc_log("TRANSFER WHO", f"sender={transfer.sender} receiver={transfer.receiver} amount={transfer.amount} gaslimit={transfer.gas_limit}")
    elif g < dest_service_account.gas_limit_on_transfer:
        output.exit_condition = ExitCondition(reason=ExitReason.resume)
        output.registers[7] = HostCallResult.LOW.value
        logger.hc_log("TRANSFER LOW", f"sender={transfer.sender} receiver={transfer.receiver} amount={transfer.amount} gaslimit={transfer.gas_limit}")
    elif b < service_account.threshold_balance:   # insufficient funds
        output.exit_condition = ExitCondition(reason=ExitReason.resume)
        output.registers[7] = HostCallResult.CASH.value
        logger.hc_log("TRANSFER CASH", f"sender={transfer.sender} receiver={transfer.receiver} amount={transfer.amount} gaslimit={transfer.gas_limit}")
    else:
        output.exit_condition = ExitCondition(reason=ExitReason.resume)
        output.registers[7] = HostCallResult.OK.value

        # TODO: mark dirty? maybe register changes
        service_account.balance = b
        ctx_in.context.deferred_transfers.append(transfer)
        # TODO inefficient; move to end, only once per service
        ctx_in.context.state_context.services.store_service_account(service_id, service_account)
        logger.hc_log("TRANSFER OK", f"sender={transfer.sender} receiver={transfer.receiver} amount={transfer.amount} gaslimit={transfer.gas_limit}")


def hc_eject(
        registers: List[int],
        memory: PVMMemory,
        ctx_in: AccumulateInvocationContext,
        output: InvocationMutationOutput,
        logger: PVMLogger):
    """
    """
    logger.hc_regs(f"EJECT", "accumulate")
    output.gas_limit -= 10

    d = registers[7]
    o = registers[8]

    # gp: h
    try:
        preimage_hash = memory.read_bytes(o, 32)
    except PVMMemoryError:
        preimage_hash = None

    state = ctx_in.context.state_context
    service_id = ctx_in.context.service_account_id
    service_account = ctx_in.context.state_context.services.retrieve_service_account(service_id)

    l = None
    updated_balance = None
    preimage_availability = None
    eject_service_account = None  # GP: bold_d
    if d != service_id:
        try:
            eject_service_account = state.services.retrieve_service_account(d)
            l = max(81, eject_service_account.footprint_storage_bytes) - 81
            updated_balance = service_account.balance + eject_service_account.balance
            try:
                preimage_availability = state.services.retrieve_preimage_availability(d, preimage_hash, l)
            except StateKeyNoResult:
                preimage_availability = None
        except StateKeyNoResult as e:
            eject_service_account = None  #GP: bold_d = ∇

    if preimage_hash is None:
        output.exit_condition = ExitCondition(reason=ExitReason.panic)
        logger.hc_log("EJECT PANIC", f"")
    elif eject_service_account is None or eject_service_account.code_hash != int(service_id).to_bytes(length=32, byteorder="little"):
        # Note: eject service grants eject by setting code_hash to current service_id
        output.exit_condition = ExitCondition(reason=ExitReason.resume)
        output.registers[7] = HostCallResult.WHO.value
        logger.hc_log("EJECT WHO", f"")
    elif eject_service_account.footprint_storage_items != 2 or preimage_availability is None:
        # Note: if this storage_account emptied and the preimage exists
        output.exit_condition = ExitCondition(reason=ExitReason.resume)
        output.registers[7] = HostCallResult.HUH.value
        logger.hc_log("EJECT HUH", f"preimage_availability={preimage_availability}")
    elif len(preimage_availability) == 2 and preimage_availability[1] < ctx_in.timeslot - PREIMAGE_EXPUNGE_TIMESLOTS:
        output.exit_condition = ExitCondition(reason=ExitReason.resume)
        output.registers[7] = HostCallResult.OK.value

        # TODO: nodig?
        # TODO: mark dirty? maybe register changes
        state.services.delete_preimage(d, preimage_hash)
        state.services.delete_preimage_availability(d, preimage_hash, l)
        state.services.delete_service_account(d)
        service_account.balance = updated_balance
        state.services.store_service_account(service_id, service_account) # TODO: meenemen in de finalize vd transactie
        logger.hc_log("EJECT OK", f"preimage_availability={preimage_availability} d={d} preimage_hash={preimage_hash.hex()} l={l} updated_balance={updated_balance}")
    else:
        output.exit_condition = ExitCondition(reason=ExitReason.resume)
        output.registers[7] = HostCallResult.HUH.value
        logger.hc_log("EJECT HUH", f"preimage_availability={preimage_availability} d={d} preimage_hash={preimage_hash.hex()} l={l} updated_balance={updated_balance}")


def hc_query(
        registers: List[int],
        memory: PVMMemory,
        ctx_in: AccumulateInvocationContext,
        output: InvocationMutationOutput,
        logger: PVMLogger):
    """
    Determines the availability of a preimage
    """
    logger.hc_regs(f"QUERY", "accumulate")
    output.gas_limit -= 10

    o = registers[7]    # memory offset
    preimage_length = registers[8]    # preimage length

    service_id = ctx_in.context.service_account_id

    # GP: h
    try:
        preimage_hash = memory.read_bytes(o, 32)
    except PVMMemoryError:
        preimage_hash = None

    # GP: bold_a
    try:
        # GP: (xs)l[h,z] == bold_a
        preimage_availability = ctx_in.context.state_context.services.retrieve_preimage_availability(
            service_id,
            preimage_hash,
            preimage_length
        )
    except StateKeyNoResult as e:
        preimage_availability = None

    if preimage_hash is None:
        output.exit_condition = ExitCondition(reason=ExitReason.panic)
        logger.hc_log("QUERY PANIC", f"")
    elif preimage_availability is None:
        output.exit_condition = ExitCondition(reason=ExitReason.resume)
        output.registers[7] = HostCallResult.NONE.value
        output.registers[8] = 0
        logger.hc_log("QUERY NONE", f"r7={registers[7]} (NONE) r8={registers[8]}")
    elif len(preimage_availability) == 0:
        # Note: Marked as requested
        output.exit_condition = ExitCondition(reason=ExitReason.resume)
        output.registers[7] = 0
        output.registers[8] = 0
        logger.hc_log("QUERY 0", f"r7={registers[7]} r8={registers[8]}")
    elif len(preimage_availability) == 1:
        # Note: Marked as available
        output.exit_condition = ExitCondition(reason=ExitReason.resume)
        output.registers[7] = 1 + 2 ** 32 * preimage_availability[0]
        output.registers[8] = 0
        logger.hc_log(f"QUERY 1", f"r7={registers[7]} r8={registers[8]}")
    elif len(preimage_availability) == 2:
        # Note: Marked as unavailable
        output.exit_condition = ExitCondition(reason=ExitReason.resume)
        output.registers[7] = 2 + 2 ** 32 * preimage_availability[0]
        output.registers[8] = preimage_availability[1]
        logger.hc_log(f"QUERY 2", f"r7={registers[7]} r8={registers[8]}")
    elif len(preimage_availability) == 3:
        # Note: Marked as re-available
        output.exit_condition = ExitCondition(reason=ExitReason.resume)
        output.registers[7] = 3 + 2 ** 32 * preimage_availability[0]
        output.registers[8] = preimage_availability[1] + 2 ** 32 * preimage_availability[2]
        logger.hc_log(f"QUERY 3", f"r7={registers[7]} r8={registers[8]}")
    else:
        output.exit_condition = ExitCondition(reason=ExitReason.panic)
        logger.hc_log("QUERY PANIC", f"")


def hc_solicit(
        registers: List[int],
        memory: PVMMemory,
        ctx_in: AccumulateInvocationContext,
        output: InvocationMutationOutput,
        logger: PVMLogger):
    """
    Modifies the preimage availability lookup (requests a preimage to be made available)
    """
    logger.hc_regs(f"SOLICIT", "accumulate")
    output.gas_limit -= 10

    state = ctx_in.context.state_context
    service_id = ctx_in.context.service_account_id
    service_account = ctx_in.context.state_context.services.retrieve_service_account(service_id) # GP: bold_a

    o = registers[7]
    preimage_length = registers[8]    # GP: z

    #GP: h
    try:
        preimage_hash = memory.read_bytes(o, 32)
    except PVMMemoryError:
        preimage_hash = None #GP: h = ∇

    try:
        # GP: bold_a
        preimage_availability = state.services.retrieve_preimage_availability(
            service_id,
            preimage_hash,
            preimage_length
        )
    except StateKeyNoResult:
        preimage_availability = None

    if preimage_hash is not None and preimage_availability is None:
        # TODO: mark dirty? maybe register changes
        # preimage is being requested that is not already present in storage
        service_account.update_footprint_add_preimage(preimage_length)

    if preimage_hash is None:
        output.exit_condition = ExitCondition(reason=ExitReason.panic)
        logger.hc_log("SOLICIT PANIC", f"")
    elif preimage_availability is not None and len(preimage_availability) != 2:
        output.exit_condition = ExitCondition(reason=ExitReason.resume)
        output.registers[7] = HostCallResult.HUH.value
        logger.hc_log("SOLICIT HUH", f"h={preimage_hash} newvalue={preimage_availability}")
    elif service_account.balance < service_account.threshold_balance:
        output.exit_condition = ExitCondition(reason=ExitReason.resume)
        output.registers[7] = HostCallResult.FULL.value
        logger.hc_log("SOLICIT FULL", f"h={preimage_hash} newvalue={preimage_availability}")
    else:
        output.exit_condition = ExitCondition(reason=ExitReason.resume)
        output.registers[7] = HostCallResult.OK.value

        if preimage_availability is None:

            # TODO: mark dirty? maybe register changes
            state.services.store_preimage_availability(
                service_id,
                preimage_hash,
                preimage_length,
                []
            )

        elif len(preimage_availability) == 2:

            # TODO: mark dirty? maybe register changes
            state.services.store_preimage_availability(
                service_id,
                preimage_hash,
                preimage_length,
                preimage_availability + [ctx_in.timeslot]
            )

        logger.hc_log("SOLICIT OK", f"h={preimage_hash.hex()} newvalue={preimage_availability}")


def hc_forget(
        registers: List[int],
        memory: PVMMemory,
        ctx_in: AccumulateInvocationContext,
        output: InvocationMutationOutput,
        logger: PVMLogger):
    """
    Deletes PreimageAvailability (status queue)
    """
    logger.hc_regs(f"FORGET", "accumulate")
    output.gas_limit -= 10

    o = registers[7]
    preimage_length = registers[8]  #GP: z

    state = ctx_in.context.state_context
    service_id = ctx_in.context.service_account_id
    service_account = ctx_in.context.state_context.services.retrieve_service_account(service_id) # GP: bold_a

    #GP: h
    try:
        preimage_hash = memory.read_bytes(o, 32)
    except PVMMemoryError:
        preimage_hash = None #GP: h = ∇

    timeslot = ctx_in.timeslot #GP: t
    # Note: x & y & w refer to the cardinality of the preimage_availability dictionary, see 9.2.2 EQ9.7
    preimage_updated = True #GP: bold_a = ∇

    try:
        preimage_availability = state.services.retrieve_preimage_availability(
            service_id,
            preimage_hash,
            preimage_length
        )

        preimage_cardinality = len(preimage_availability)
        if preimage_cardinality in (0, 2) and preimage_availability[1] < (timeslot - PREIMAGE_EXPUNGE_TIMESLOTS):
            # TODO: mark dirty? maybe register changes
            state.services.delete_preimage_availability(service_id, preimage_hash, preimage_length)
            state.services.delete_preimage(service_id, preimage_hash)
            # Update footprint
            service_account.update_footprint_remove_preimage(preimage_length)
        elif preimage_cardinality == 1:
            # TODO: mark dirty? maybe register changes
            state.services.store_preimage_availability(
                service_id,
                preimage_hash,
                preimage_length,
                preimage_availability + [timeslot]
            )
        elif preimage_cardinality == 3 and preimage_availability[1] < (timeslot - PREIMAGE_EXPUNGE_TIMESLOTS):
            # TODO: mark dirty? maybe register changes
            # Note: reset unreferenced preimage expunge time with current timeslot
            state.services.store_preimage_availability(
                service_id,
                preimage_hash,
                preimage_length,
                [preimage_availability[2], timeslot]
            )
        else:
            preimage_updated = False
    except StateKeyNoResult:
        preimage_updated = False

    if preimage_hash is None:
        output.exit_condition = ExitCondition(reason=ExitReason.panic)
        logger.hc_log("FORGET PANIC", f"preimage_hash={preimage_hash.hex()}")
    elif preimage_updated is False:
        output.exit_condition = ExitCondition(reason=ExitReason.resume)
        output.registers[7] = HostCallResult.HUH.value
        logger.hc_log("FORGET HUH", f"preimage_hash={preimage_hash.hex()}")
    else:
        output.exit_condition = ExitCondition(reason=ExitReason.resume)
        output.registers[7] = HostCallResult.OK.value
        logger.hc_log("FORGET OK", f"preimage_hash={preimage_hash.hex()}")


def hc_yield(
        registers: List[int],
        memory: PVMMemory,
        ctx_in: AccumulateInvocationContext,
        output: InvocationMutationOutput,
        logger: PVMLogger):
    """
    Sets the invocation output
    """
    logger.hc_regs(f"YIELD", "accumulate")
    output.gas_limit -= 10
    o = registers[7]

    # gp: h
    if memory.is_accessible(o, 32, PVMMemoryMode.readable):
        invocation_data = memory.read_bytes(o, 32)
    else:
        invocation_data = None

    if invocation_data is None:
        output.exit_condition = ExitCondition(reason=ExitReason.panic)
        logger.hc_log("YIELD PANIC", f"")
    else:
        output.exit_condition = ExitCondition(reason=ExitReason.resume)
        output.registers[7] = HostCallResult.OK.value
        ctx_in.context.invocation_output = invocation_data
        logger.hc_log("YIELD OK", f"invocation_data={invocation_data.hex()}")


def hc_provide(
        registers: List[int],
        memory: PVMMemory,
        ctx_in: AccumulateInvocationContext,
        services: ServicesState,
        service_id: int,
        output: InvocationMutationOutput,
        logger: PVMLogger):
    """
    Provides a preimage for specified service ID
    """

    logger.hc_regs(f"PROVIDE", "accumulate")
    output.gas_limit -= 10

    preimage_address = registers[8] # GP: o
    preimage_length = registers[9]  # GP: z

    # GP: s*
    if registers[7] == 2 ** 64 - 1:
        service_account_id = service_id
    else:
        service_account_id = registers[7]

    # GP: i
    if memory.is_accessible(preimage_address, preimage_length, PVMMemoryMode.readable):
        preimage_blob = memory.read_bytes(preimage_address, preimage_length)
        # TODO -6 offset met DUNA testdata????????
        # preimage_blob = memory.read_bytes(preimage_address - 6, preimage_length)
    else:
        preimage_blob = None

    # GP: bold_a
    try:
        service_account = services.retrieve_service_account(service_account_id)
    except StateKeyNoResult:
        service_account = None  # bold_a = ∅

    # GP: A_l[(H(i), z)]
    if preimage_blob is not None:
        try:
            preimage_availability = services.retrieve_preimage_availability(
                service_account_id, blake2b_256_hash(preimage_blob), preimage_length
            )
        except StateKeyNoResult:
            preimage_availability = None
    else:
        preimage_availability = None

    if preimage_blob is None:
        output.exit_condition = ExitCondition(reason=ExitReason.panic)
        logger.hc_log("PROVIDE PANIC", f"")
    elif service_account is None:
        output.exit_condition = ExitCondition(reason=ExitReason.resume)
        output.registers[7] = HostCallResult.WHO.value
        logger.hc_log("PROVIDE WHO", f"")
    elif preimage_availability != []:
        output.exit_condition = ExitCondition(reason=ExitReason.resume)
        output.registers[7] = HostCallResult.HUH.value
        logger.hc_log("PROVIDE HUH", f"")
    elif (service_account_id, preimage_blob) in ctx_in.context.preimages:
        output.exit_condition = ExitCondition(reason=ExitReason.resume)
        output.registers[7] = HostCallResult.HUH.value
        logger.hc_log("PROVIDE HUH", f"")
    else:
        output.exit_condition = ExitCondition(reason=ExitReason.resume)
        output.registers[7] = HostCallResult.OK.value
        ctx_in.context.preimages.append((service_id, preimage_blob))
        logger.hc_log("PROVIDE OK", f"h={format_hash(blake2b_256_hash(preimage_blob))}")


