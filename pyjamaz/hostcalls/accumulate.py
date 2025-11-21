from copy import deepcopy
from typing import List

from jamcodec.base import JamBytes
from jamcodec.types import U64, U32

from pyjamaz.exceptions import StateKeyNoResult
from pyjamaz.graypaper_constants import MAXIMUM_AUTHORIZATION_QUEUE_ITEMS, CORE_COUNT, VALIDATOR_COUNT, \
    PREIMAGE_EXPUNGE_TIMESLOTS, SIZE_TRANSFER_MEMO, MINIMUM_PUBLIC_SERVICE_ID
from pyjamaz.hashing import blake2b_256_hash
from pyjamaz.models.common import ValidatorData, DeferredTransfer
from pyjamaz.models.state import ServiceAccount, ServicesState
from pyjamaz.hostcalls.models import AccumulateInvocationContext
from pyjamaz.pvm.constants import ExitCondition, ExitReason, MEM_R
from pyjamaz.pvm.exceptions import PVMMemoryError
from pyjamaz.pvm.invocation import InvocationMutationOutput, PVMLogger
from pyjamaz.pvm.memory import PVMMemory
from pyjamaz.hostcalls.constants import HostCallResult
from pyjamaz.utils import format_hash


def hc_bless(
        registers: List[int],
        memory: PVMMemory,
        x: AccumulateInvocationContext,
        invocation_output: InvocationMutationOutput,
        logger: PVMLogger):
    """
    GP-0.7.1-section:B.7 (Ω_B) | Accumulate host function: bless.

    Set the privileged services.
    manager: The ID of the service which may effectually call bless in the future.
    assigners: The IDs of the services which may effectually call assign in the future (one per core).
    delegator: The ID of the service which may effectually call designate in the future.
    always_acc: The list of service IDs which accumulate at least once in every JAM block,
    together with the baseline gas they get for accumulation. This may be supplemented with
    additional gas should there be Work Items for the service.
    --------------------------
    State transition function for privileged services.
    Updates gas limits for privileged services

    Parameters
    ----------
    registers: List[int]
    memory: PVMMemory
    x: AccumulateInvocationContext
    invocation_output: InvocationMutationOutput
    logger: PVMLogger

    Returns
    ----------
    None
    """
    logger and logger.hc_regs(f"BLESS", "accumulate")

    invocation_output.gas_limit -= 10

    # Privileged services:
    m = registers[7] # m: index of manager service (manager of chi(X))
    a = registers[8] # a: address to read values of the assign services (authorization queue)
    v = registers[9] # v: index of designate service (validator queue)
    r = registers[10]  # r: index of registrar service
    o = registers[11] # offset to read service indices and accompanying gas limits from
    n = registers[12] # number of entries in the auto_accumulate_services dictionary to read

    assigners = None # GP: bold_a
    if memory.is_accessible(a, 4 * CORE_COUNT, MEM_R):
        try:
            assigners = []
            for idx in range(CORE_COUNT):
                offset = a + idx * 4
                assigners.append(U32.decode(JamBytes(memory.read_bytes(offset, 4))))
        except PVMMemoryError:
            assigners = None   # bold_a = ∇

    auto_accumulate_services = None #GP: bold_g
    if memory.is_accessible(o, 12 * n, MEM_R):
        try:
            auto_accumulate_services = {}
            for idx in range(n):
                offset = o + idx * 12
                service_idx = U32.decode(JamBytes(memory.read_bytes(offset, 4)))
                gas = U64.decode(JamBytes(memory.read_bytes(offset + 4, 8)))
                auto_accumulate_services[service_idx] = gas
        except PVMMemoryError:
            auto_accumulate_services = None   # bold_g = ∇

    if auto_accumulate_services is None or assigners is None:
        invocation_output.exit_condition = ExitCondition(reason=ExitReason.panic)
        logger and logger.hc_log("BLESS PANIC", f"m={m} a={a} v={v}")
    # TODO regressie huh?
    # elif x.context.service_account_id != x.context.state_context.privileged_services.manager:
    #     invocation_output.exit_condition = ExitCondition(reason=ExitReason.resume)
    #     invocation_output.registers[7] = HostCallResult.HUH.value
    #     logger and logger.hc_log("BLESS HUH", f"m={m} a={a} v={v}")
    elif m >= 2**32 or v >= 2**32 or r >= 2**32:
        invocation_output.exit_condition = ExitCondition(reason=ExitReason.resume)
        invocation_output.registers[7] = HostCallResult.WHO.value
        logger and logger.hc_log("BLESS WHO", f"m={m} a={a} v={v} r={r}")
    else:
        invocation_output.exit_condition = ExitCondition(reason=ExitReason.resume)
        invocation_output.registers[7] = HostCallResult.OK.value

        ps = x.context.state_context.privileged_services
        ps.manager = m
        ps.assigners = assigners
        ps.delegator = v
        ps.registrar = r
        ps.always_accumulators = auto_accumulate_services

        logger and logger.hc_log("BLESS OK", f"m={m} a={a} v={v} r={r}")


def hc_assign(
        registers: List[int],
        memory: PVMMemory,
        x: AccumulateInvocationContext,
        invocation_output: InvocationMutationOutput,
        logger: PVMLogger):
    """
    GP-0.7.1-section:B.7 (Ω_A) | Accumulate host function: assign.

    Assign a series of authorizers to a core.
    core: The index of the core to assign the authorizers to.
    auth_queue: The authorizer-queue to assign to the core. These are a series of AuthorizerHash values,
    which determine what kinds of Work Packages are allowed to be executed on the core.
    Returns Ok on success or Err if the operation failed. Failure can only happen if the value of core is out of range.
    --------------------------
    Update authorization queue (state transition function of Phi)

    Parameters
    ----------
    registers: List[int]
    memory: PVMMemory
    x: AccumulateInvocationContext
    invocation_output: InvocationMutationOutput
    logger: PVMLogger

    Returns
    ----------
    None
    """
    logger and logger.hc_regs(f"ASSIGN", "accumulate")
    invocation_output.gas_limit -= 10

    # Privileged services:
    core_index = registers[7] # Core index to update (0..341)
    o = registers[8] # memory offset
    a = registers[9] # new assigner service

    if memory.is_accessible(o, 32 * MAXIMUM_AUTHORIZATION_QUEUE_ITEMS, MEM_R):
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
        invocation_output.exit_condition = ExitCondition(reason=ExitReason.panic)
        logger and logger.hc_log("ASSIGN PANIC", f"c={core_index}")

    elif core_index >= CORE_COUNT:
        invocation_output.exit_condition = ExitCondition(reason=ExitReason.resume)
        invocation_output.registers[7] = HostCallResult.CORE.value
        logger and logger.hc_log("ASSIGN CORE", f"c={core_index}")

    elif x.context.service_account_id != x.context.state_context.privileged_services.assigners[core_index]:
        invocation_output.exit_condition = ExitCondition(reason=ExitReason.resume)
        invocation_output.registers[7] = HostCallResult.HUH.value
        logger and logger.hc_log("ASSIGN HUH", f"X_s={x.context.service_account_id}")

    elif a >= 2**32:
        invocation_output.exit_condition = ExitCondition(reason=ExitReason.resume)
        invocation_output.registers[7] = HostCallResult.WHO.value
        logger and logger.hc_log("ASSIGN WHO", f"a={a}")

    else:
        invocation_output.exit_condition = ExitCondition(reason=ExitReason.resume)
        invocation_output.registers[7] = HostCallResult.OK.value

        x.context.state_context.authorizer_queues.authorizer_queues[core_index] = authorization_queue
        x.context.state_context.privileged_services.assigners[core_index] = a

        logger and logger.hc_log("ASSIGN OK", f"c={core_index} o={o} a={a}")


def hc_designate(
        registers: List[int],
        memory: PVMMemory,
        x: AccumulateInvocationContext,
        invocation_output: InvocationMutationOutput,
        logger: PVMLogger):
    """
    GP-0.7.1-section:B.7 (Ω_D) | Accumulate host function: designate.

    Designate the new validator keys.
    keys: The new validator keys.
    Only callable by the designated delegator service.
    --------------------------
    Update the validator Queue (State transition function for the validator queue)

    Parameters
    ----------
    registers: List[int]
    memory: PVMMemory
    x: AccumulateInvocationContext
    invocation_output: InvocationMutationOutput
    logger: PVMLogger

    Returns
    ----------
    None
    """
    logger and logger.hc_regs(f"DESIGNATE", "accumulate")
    invocation_output.gas_limit -= 10

    o = registers[7] # memory offset

    if memory.is_accessible(o, 336 * VALIDATOR_COUNT, MEM_R):
        validator_queue = [] #GP: bold_v
        try:
            for idx in range(VALIDATOR_COUNT):
                offset = o + idx * 336
                validator_data = ValidatorData.from_jam_bytes(JamBytes(memory.read_bytes(offset, 336)))
                validator_queue.append(validator_data)
        except PVMMemoryError:
            validator_queue = None # GP: bold_v = ∇
    else:
        validator_queue = None # GP: bold_v = ∇

    if validator_queue is None:
        invocation_output.exit_condition = ExitCondition(reason=ExitReason.panic)
        logger and logger.hc_log("DESIGNATE PANIC", f"o={o}")

    elif x.context.service_account_id != x.context.state_context.privileged_services.delegator:
        invocation_output.exit_condition = ExitCondition(reason=ExitReason.resume)
        invocation_output.registers[7] = HostCallResult.HUH.value
        logger and logger.hc_log("DESIGNATE HUH", f"Xs={x.context.service_account_id}")

    else:
        invocation_output.exit_condition = ExitCondition(reason=ExitReason.resume)
        invocation_output.registers[7] = HostCallResult.OK.value

        x.context.state_context.validator_queue.validators = validator_queue
        logger and logger.hc_log("DESIGNATE OK", f"o={o}")


def hc_checkpoint(
        registers: List[int],
        memory: PVMMemory,
        x: AccumulateInvocationContext,
        invocation_output: InvocationMutationOutput,
        logger: PVMLogger):
    """
    GP-0.7.1-section:B.7 (Ω_C) | Accumulate host function: checkpoint.

    Checkpoint the state of the accumulation at present.
    In the case that accumulation runs out of gas or otherwise terminates unexpectedly, all changes extrinsic to the
    machine state, such as storage writes and transfers, will be rolled back to the most recent call to checkpoint,
    or the beginning of the accumulation if no checkpoint has been made.
    --------------------------
    Copy the invocation result context x to y

    Parameters
    ----------
    registers: List[int]
    memory: PVMMemory
    x: AccumulateInvocationContext
    invocation_output: InvocationMutationOutput
    logger: PVMLogger

    Returns
    ----------
    None
    """
    logger and logger.hc_regs(f"CHECKPOINT", "accumulate")
    invocation_output.gas_limit -= 10
    invocation_output.registers[7] = invocation_output.gas_limit
    invocation_output.exit_condition = ExitCondition(reason=ExitReason.resume)
    # TODO: optimize deepcopy?
    x.savepoint_context = deepcopy(x.context)
    x.context.state_context.services.state_storage.checkpoint(x.context.service_account_id)


def hc_new(
        registers: List[int],
        memory: PVMMemory,
        x: AccumulateInvocationContext,
        invocation_output: InvocationMutationOutput,
        logger: PVMLogger):
    """
    GP-0.7.1-section:B.7 (Ω_N) | Accumulate host function: new.

    Creates new service account.

    Parameters
    ----------
    registers: List[int]
    memory: PVMMemory
    x: AccumulateInvocationContext
    invocation_output: InvocationMutationOutput
    logger: PVMLogger

    Returns
    ----------
    None
    """
    logger and logger.hc_regs(f"NEW", "accumulate")
    invocation_output.gas_limit -= 10

    o = registers[7]  # offset to read service data from
    l = registers[8]  # size (byte length) of the code blob
    g = registers[9]  # gas_limit_accumulate
    m = registers[10] # gas_limit_on_transfer
    f = registers[11] # deposit_offset
    i = registers[12] # new public service ID

    code_hash = None
    if 0 < l < 2**32 and memory.is_accessible(o, 32, MEM_R):
        try:
            code_hash = memory.read_bytes(o, 32)  # GP: c
        except PVMMemoryError:
            pass

    service_id = x.context.service_account_id
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
            preimage_availability={},  # {(code_hash, l): []} #bold_l
            deposit_offset=f,
            creation_slot=x.timeslot,
            last_accumulation_slot=0,
            parent_service=x.context.service_account_id,
        )

        new_service_id = x.context.new_service_account_id
        new_service_account.update_footprint_add_preimage(l)
        new_service_account.balance = new_service_account.threshold_balance
        service_account = x.context.state_context.services.retrieve_service_account(service_id)
        deducted_balance = service_account.balance - new_service_account.threshold_balance

    if code_hash is None:
        invocation_output.exit_condition = ExitCondition(reason=ExitReason.panic)
        logger and logger.hc_log("NEW PANIC", f"service={service_id}")

    elif f != 0 and service_id != x.context.state_context.privileged_services.manager:
        invocation_output.exit_condition = ExitCondition(reason=ExitReason.resume)
        invocation_output.registers[7] = HostCallResult.HUH.value
        logger and logger.hc_log(
            "NEW HUH",
            f"service={service_id} attempted non-zero deposit_offset f={f} without manager privileges"
        )

    elif deducted_balance < service_account.threshold_balance:
        invocation_output.exit_condition = ExitCondition(reason=ExitReason.resume)
        invocation_output.registers[7] = HostCallResult.CASH.value
        logger and logger.hc_log("NEW CASH", f"service={service_id} deducted_balance={deducted_balance} threshold_balance={service_account.threshold_balance} code_hash={code_hash} code_len={l}")

    elif (service_id == x.context.state_context.privileged_services.registrar and i < MINIMUM_PUBLIC_SERVICE_ID and
          x.context.state_context.services.service_exists(i)):
        invocation_output.exit_condition = ExitCondition(reason=ExitReason.resume)

        invocation_output.registers[7] = HostCallResult.FULL.value
        logger and logger.hc_log(
            "NEW FULL",
            f"service={service_id} i={i} deducted_balance={deducted_balance} threshold_balance={service_account.threshold_balance} code_hash={code_hash} code_len={l}"
            )

    else:

        invocation_output.exit_condition = ExitCondition(reason=ExitReason.resume)

        if service_id == x.context.state_context.privileged_services.registrar and i < MINIMUM_PUBLIC_SERVICE_ID:
            new_service_id = i
        else:
            updated_new_service_id = (MINIMUM_PUBLIC_SERVICE_ID + (new_service_id - MINIMUM_PUBLIC_SERVICE_ID + 42) %
                                      (2 ** 32 - MINIMUM_PUBLIC_SERVICE_ID - 2 ** 8))
            x.context.new_service_account_id = x.context.state_context.check_service_id(
                updated_new_service_id
            )

        invocation_output.registers[7] = new_service_id

        service_account.balance = deducted_balance

        x.context.state_context.services.store_service_account(service_id, service_account)
        x.context.state_context.services.store_service_account(new_service_id, new_service_account)
        x.context.state_context.services.store_preimage_availability(new_service_id, code_hash, l, [])

        logger and logger.hc_log("NEW OK", f"old_service={service_id} code_hash={code_hash} code_len={l}")


def hc_upgrade(
        registers: List[int],
        memory: PVMMemory,
        x: AccumulateInvocationContext,
        invocation_output: InvocationMutationOutput,
        logger: PVMLogger):
    """
    GP-0.7.1-section:B.7 (Ω_U) | Accumulate host function: upgrade.

    Upgrade the code of the service.
    code_hash: The hash of the code to upgrade to, to be found in the service's preimage store.
    min_item_gas: The minimum gas required to be set aside for the accumulation of a single Work
    Item in the new service.
    min_memo_gas: The minimum gas required to be set aside for any single transfer of funds and
    corresponding processing of a memo in the new service.
    --------------------------
    Updates codehash and gas limits for a service account

    Parameters
    ----------
    registers: List[int]
    memory: PVMMemory
    x: AccumulateInvocationContext
    invocation_output: InvocationMutationOutput
    logger: PVMLogger

    Returns
    ----------
    None
    """
    logger and logger.hc_regs(f"UPGRADE", "accumulate")
    invocation_output.gas_limit -= 10

    o = registers[7]  # offset for service codehash
    g = registers[8]  # gas_limit_accumulate
    m = registers[9]  # gas_limit_on_transfer

    service_id = x.context.service_account_id
    service_account = x.context.state_context.services.retrieve_service_account(service_id)

    try:
        code_hash = memory.read_bytes(o, 32)
    except PVMMemoryError:
        code_hash = None # GP: c = ∇

    if code_hash is None:
        invocation_output.exit_condition = ExitCondition(reason=ExitReason.panic)
        logger and logger.hc_log("UPGRADE PANIC", "")
    else:
        invocation_output.exit_condition = ExitCondition(reason=ExitReason.resume)
        invocation_output.registers[7] = HostCallResult.OK.value

        service_account.code_hash = code_hash
        service_account.gas_limit_accumulate = g
        service_account.gas_limit_on_transfer = m

        x.context.state_context.services.store_service_account(service_id, service_account)
        logger and logger.hc_log("UPGRADE OK", f"code_hash={code_hash} ")


def hc_transfer(
        registers: List[int],
        memory: PVMMemory,
        x: AccumulateInvocationContext,
        invocation_output: InvocationMutationOutput,
        logger: PVMLogger):
    """
    GP-0.7.1-section:B.7 (Ω_T) | Accumulate host function: transfer.

    Transfer data and/or funds to another service asynchronously.
    destination: The ID of the service to transfer to. This service must exist at present.
    amount: The amount of funds to transfer to the destination service. Reducing the services
    balance by this amount must not result in it falling below the minimum balance required.
    gas_limit: The amount of gas to set aside for the processing of the transfer by the
    destination service. This must be at least the service's min_memo_gas. The
    effective gas cost of this call is increased by this amount.
    memo: A piece of data to give the destination service.
    --------------------------
    Creates a new transfer and add to the deferred transfers

    Parameters
    ----------
    registers: List[int]
    memory: PVMMemory
    x: AccumulateInvocationContext
    invocation_output: InvocationMutationOutput
    logger: PVMLogger

    Returns
    ----------
    None
    """
    logger and logger.hc_regs(f"TRANSFER", "accumulate")
    gas_limit = registers[9] & ((1 << 64) - 1) # TODO: should wrap around??
    gas_usage = 10 + registers[9]
    if gas_usage > invocation_output.gas_limit:
        # Note: keep gas negative (otherwise a int wrap around could make it positive again)
        invocation_output.gas_limit = -1 #invocation_output.gas_limit - gas_usage
    else:
        invocation_output.gas_limit -= gas_usage

    d = registers[7]     # destination
    a = registers[8]     # amount
    g = gas_limit        # gas_limit
    o = registers[10]    # offset for memo

    service_id = x.context.service_account_id
    service_account = x.context.state_context.services.retrieve_service_account(service_id)
    try:
        dest_service_account = x.context.state_context.services.retrieve_service_account(d)   #GP: bold_d
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
        invocation_output.exit_condition = ExitCondition(reason=ExitReason.panic)

    elif dest_service_account is None:
        invocation_output.exit_condition = ExitCondition(reason=ExitReason.resume)
        invocation_output.registers[7] = HostCallResult.WHO.value
        logger and logger.hc_log("TRANSFER WHO", f"sender={transfer.sender} receiver={transfer.receiver} amount={transfer.amount} gaslimit={transfer.gas_limit}")

    elif g < dest_service_account.gas_limit_on_transfer:
        invocation_output.exit_condition = ExitCondition(reason=ExitReason.resume)
        invocation_output.registers[7] = HostCallResult.LOW.value
        logger and logger.hc_log("TRANSFER LOW", f"sender={transfer.sender} receiver={transfer.receiver} amount={transfer.amount} gaslimit={transfer.gas_limit}")

    elif b < service_account.threshold_balance:   # insufficient funds
        invocation_output.exit_condition = ExitCondition(reason=ExitReason.resume)
        invocation_output.registers[7] = HostCallResult.CASH.value
        logger and logger.hc_log("TRANSFER CASH", f"sender={transfer.sender} receiver={transfer.receiver} amount={transfer.amount} gaslimit={transfer.gas_limit}")

    else:
        invocation_output.exit_condition = ExitCondition(reason=ExitReason.resume)
        invocation_output.registers[7] = HostCallResult.OK.value

        service_account.balance = b
        x.context.deferred_transfers.append(transfer)

        x.context.state_context.services.store_service_account(service_id, service_account)
        logger and logger.hc_log("TRANSFER OK", f"sender={transfer.sender} receiver={transfer.receiver} amount={transfer.amount} gaslimit={transfer.gas_limit}")


def hc_eject(
        registers: List[int],
        memory: PVMMemory,
        x: AccumulateInvocationContext,
        invocation_output: InvocationMutationOutput,
        logger: PVMLogger):
    """
    GP-0.7.1-section:B.7 (Ω_E) | Accumulate host function: eject.

    Remove the target zombie service, drop its final preimage item code_hash and transfer
    remaining balance to this service.
    target: The ID of a zombie service which nominated the caller service as its ejector.
    code_hash: The hash of the only preimage item of the target service. It must be
    unrequested and droppable.
    Target must therefore satisfy several requirements:
    - it should have a code hash which is simply the LE32-encoding of the caller service's ID;
    - it should have only one preimage lookup item, code_hash;
    - it should have nothing in its storage.
    --------------------------
    Performs an ejection of a Service Account's preimage

    Parameters
    ----------
    registers: List[int]
    memory: PVMMemory
    x: AccumulateInvocationContext
    invocation_output: InvocationMutationOutput
    logger: PVMLogger

    Returns
    ----------
    None
    """
    logger and logger.hc_regs(f"EJECT", "accumulate")
    invocation_output.gas_limit -= 10

    d = registers[7]
    o = registers[8]

    # gp: h
    try:
        preimage_hash = memory.read_bytes(o, 32)
    except PVMMemoryError:
        preimage_hash = None

    state = x.context.state_context
    service_id = x.context.service_account_id
    service_account = x.context.state_context.services.retrieve_service_account(service_id)

    l = None
    updated_balance = None
    preimage_availability = None
    eject_service_account = None  # GP: bold_d

    if preimage_hash is not None and d != service_id:
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
        invocation_output.exit_condition = ExitCondition(reason=ExitReason.panic)
        logger and logger.hc_log("EJECT PANIC", f"")
    elif eject_service_account is None or eject_service_account.code_hash != int(service_id).to_bytes(length=32, byteorder="little"):
        # Note: eject service grants eject by setting code_hash to current service_id
        invocation_output.exit_condition = ExitCondition(reason=ExitReason.resume)
        invocation_output.registers[7] = HostCallResult.WHO.value
        logger and logger.hc_log("EJECT WHO", f"")
    elif eject_service_account.footprint_storage_items != 2 or preimage_availability is None:
        # Note: if this storage_account emptied and the preimage exists
        invocation_output.exit_condition = ExitCondition(reason=ExitReason.resume)
        invocation_output.registers[7] = HostCallResult.HUH.value
        logger and logger.hc_log("EJECT HUH", f"preimage_availability={preimage_availability}")
    elif len(preimage_availability) == 2 and preimage_availability[1] < x.timeslot - PREIMAGE_EXPUNGE_TIMESLOTS:
        invocation_output.exit_condition = ExitCondition(reason=ExitReason.resume)
        invocation_output.registers[7] = HostCallResult.OK.value

        state.services.delete_preimage(d, preimage_hash)
        state.services.delete_preimage_availability(d, preimage_hash, l)
        state.services.delete_service_account(d)
        service_account.balance = updated_balance
        state.services.store_service_account(service_id, service_account)
        logger and logger.hc_log("EJECT OK", f"preimage_availability={preimage_availability} d={d} preimage_hash={preimage_hash.hex()} l={l} updated_balance={updated_balance}")
    else:
        invocation_output.exit_condition = ExitCondition(reason=ExitReason.resume)
        invocation_output.registers[7] = HostCallResult.HUH.value
        logger and logger.hc_log("EJECT HUH", f"preimage_availability={preimage_availability} d={d} preimage_hash={preimage_hash.hex()} l={l} updated_balance={updated_balance}")


def hc_query(
        registers: List[int],
        memory: PVMMemory,
        x: AccumulateInvocationContext,
        invocation_output: InvocationMutationOutput,
        logger: PVMLogger):
    """
    GP-0.7.1-section:B.7 (Ω_Q) | Accumulate host function: query.

    Query the status of a preimage.
    hash: The hash of the preimage to be queried.
    length: The length of the preimage to be queried.
    Returns Some if hash/length has an active solicitation outstanding or None if not.
    Status values indicate: 0=requested, 1=available, 2=unavailable, 3=re-available.
    --------------------------
    Determines the availability of a preimage

    Parameters
    ----------
    registers: List[int]
    memory: PVMMemory
    x: AccumulateInvocationContext
    invocation_output: InvocationMutationOutput
    logger: PVMLogger

    Returns
    ----------
    None
    """
    logger and logger.hc_regs(f"QUERY", "accumulate")
    invocation_output.gas_limit -= 10

    o = registers[7]    # memory offset
    preimage_length = registers[8]    # preimage length

    service_id = x.context.service_account_id

    # GP: h
    try:
        preimage_hash = memory.read_bytes(o, 32)
        # GP: bold_a
        try:
            # GP: (xs)l[h,z] == bold_a
            preimage_availability = x.context.state_context.services.retrieve_preimage_availability(
                service_id,
                preimage_hash,
                preimage_length
            )
        except StateKeyNoResult as e:
            preimage_availability = None
    except PVMMemoryError:
        preimage_hash = None

    if preimage_hash is None:
        invocation_output.exit_condition = ExitCondition(reason=ExitReason.panic)
        logger and logger.hc_log("QUERY PANIC", f"")
    elif preimage_availability is None:
        invocation_output.exit_condition = ExitCondition(reason=ExitReason.resume)
        invocation_output.registers[7] = HostCallResult.NONE.value
        invocation_output.registers[8] = 0
        logger and logger.hc_log("QUERY NONE", f"r7={registers[7]} (NONE) r8={registers[8]}")
    elif len(preimage_availability) == 0:
        # Note: Marked as requested
        invocation_output.exit_condition = ExitCondition(reason=ExitReason.resume)
        invocation_output.registers[7] = 0
        invocation_output.registers[8] = 0
        logger and logger.hc_log("QUERY 0", f"r7={registers[7]} r8={registers[8]}")
    elif len(preimage_availability) == 1:
        # Note: Marked as available
        invocation_output.exit_condition = ExitCondition(reason=ExitReason.resume)
        invocation_output.registers[7] = 1 + 2 ** 32 * preimage_availability[0]
        invocation_output.registers[8] = 0
        logger and logger.hc_log(f"QUERY 1", f"r7={registers[7]} r8={registers[8]}")
    elif len(preimage_availability) == 2:
        # Note: Marked as unavailable
        invocation_output.exit_condition = ExitCondition(reason=ExitReason.resume)
        invocation_output.registers[7] = 2 + 2 ** 32 * preimage_availability[0]
        invocation_output.registers[8] = preimage_availability[1]
        logger and logger.hc_log(f"QUERY 2", f"r7={registers[7]} r8={registers[8]}")
    elif len(preimage_availability) == 3:
        # Note: Marked as re-available
        invocation_output.exit_condition = ExitCondition(reason=ExitReason.resume)
        invocation_output.registers[7] = 3 + 2 ** 32 * preimage_availability[0]
        invocation_output.registers[8] = preimage_availability[1] + 2 ** 32 * preimage_availability[2]
        logger and logger.hc_log(f"QUERY 3", f"r7={registers[7]} r8={registers[8]}")
    else:
        invocation_output.exit_condition = ExitCondition(reason=ExitReason.panic)
        logger and logger.hc_log("QUERY PANIC", f"")


def hc_solicit(
        registers: List[int],
        memory: PVMMemory,
        x: AccumulateInvocationContext,
        invocation_output: InvocationMutationOutput,
        logger: PVMLogger):
    """
    GP-0.7.1-section:B.7 (Ω_S) | Accumulate host function: solicit.

    Request that preimage data be available for lookup.
    hash: The hash of the preimage to be made available.
    length: The length of the preimage to be made available.
    Returns Ok on success or Err if the request failed.
    A preimage may only be solicited once for any service and soliciting a preimage raises the
    minimum balance required to be held by the service.
    --------------------------
    Modifies the preimage availability lookup (requests a preimage to be made available)

    Parameters
    ----------
    registers: List[int]
    memory: PVMMemory
    x: AccumulateInvocationContext
    invocation_output: InvocationMutationOutput
    logger: PVMLogger

    Returns
    ----------
    None
    """
    logger and logger.hc_regs(f"SOLICIT", "accumulate")
    invocation_output.gas_limit -= 10

    state = x.context.state_context
    service_id = x.context.service_account_id
    service_account = x.context.state_context.services.retrieve_service_account(service_id) # GP: bold_a

    o = registers[7]
    preimage_length = registers[8]    # GP: z

    #GP: h
    try:
        preimage_hash = memory.read_bytes(o, 32)

        try:
            # GP: bold_a
            preimage_availability = state.services.retrieve_preimage_availability(
                service_id,
                preimage_hash,
                preimage_length
            )

        except StateKeyNoResult:
            preimage_availability = None

            # preimage is being requested that is not already present in storage
            service_account.update_footprint_add_preimage(preimage_length)

    except PVMMemoryError:
        preimage_hash = None #GP: h = ∇
        preimage_availability = None

    if preimage_hash is None:
        invocation_output.exit_condition = ExitCondition(reason=ExitReason.panic)
        logger and logger.hc_log("SOLICIT PANIC", f"")
    elif preimage_availability is not None and len(preimage_availability) != 2:
        invocation_output.exit_condition = ExitCondition(reason=ExitReason.resume)
        invocation_output.registers[7] = HostCallResult.HUH.value
        logger and logger.hc_log("SOLICIT HUH", f"h={preimage_hash} newvalue={preimage_availability}")
    elif service_account.balance < service_account.threshold_balance:
        invocation_output.exit_condition = ExitCondition(reason=ExitReason.resume)
        invocation_output.registers[7] = HostCallResult.FULL.value
        logger and logger.hc_log("SOLICIT FULL", f"h={preimage_hash} newvalue={preimage_availability}")
    else:
        invocation_output.exit_condition = ExitCondition(reason=ExitReason.resume)
        invocation_output.registers[7] = HostCallResult.OK.value

        if preimage_availability is None:

            state.services.store_preimage_availability(
                service_id,
                preimage_hash,
                preimage_length,
                []
            )

        elif len(preimage_availability) == 2:
            state.services.store_preimage_availability(
                service_id,
                preimage_hash,
                preimage_length,
                preimage_availability + [x.timeslot]
            )

        state.services.store_service_account(service_id, service_account)

        logger and logger.hc_log("SOLICIT OK", f"h={preimage_hash.hex()} newvalue={preimage_availability}")


def hc_forget(
        registers: List[int],
        memory: PVMMemory,
        x: AccumulateInvocationContext,
        invocation_output: InvocationMutationOutput,
        logger: PVMLogger):
    """
    GP-0.7.1-section:B.7 (Ω_F) | Accumulate host function: forget.

    No longer request that preimage data be available for lookup, or drop preimage data once time limit has passed.
    hash: The hash of the preimage to be forgotten.
    length: The length of the preimage to be forgotten.
    Returns Ok on success or Err if the request failed.
    This function is used twice in the lifetime of a requested preimage; once to indicate that the preimage is no longer
    needed and again to "clean up" the preimage once the required duration has passed. Whether it does one or the other
    is determined by the current state of the preimage request.
    --------------------------
    Deletes PreimageAvailability (status queue)

    Parameters
    ----------
    registers: List[int]
    memory: PVMMemory
    x: AccumulateInvocationContext
    invocation_output: InvocationMutationOutput
    logger: PVMLogger

    Returns
    ----------
    None
    """
    logger and logger.hc_regs(f"FORGET", "accumulate")
    invocation_output.gas_limit -= 10

    o = registers[7]
    preimage_length = registers[8]  #GP: z

    state = x.context.state_context
    service_id = x.context.service_account_id
    service_account = x.context.state_context.services.retrieve_service_account(service_id) # GP: bold_a

    #GP: h
    try:
        preimage_hash = memory.read_bytes(o, 32)

        timeslot = x.timeslot  # GP: t
        # Note: x & y & w refer to the cardinality of the preimage_availability dictionary, see 9.2.2 EQ9.7
        preimage_updated = False  # GP: bold_a = ∇

        try:
            preimage_availability = state.services.retrieve_preimage_availability(
                service_id,
                preimage_hash,
                preimage_length
            )

            preimage_cardinality = len(preimage_availability)
            if preimage_cardinality == 0 or preimage_cardinality == 2 and preimage_availability[1] < (
                    timeslot - PREIMAGE_EXPUNGE_TIMESLOTS):

                state.services.delete_preimage_availability(service_id, preimage_hash, preimage_length)
                state.services.delete_preimage(service_id, preimage_hash)
                # Update footprint
                service_account.update_footprint_remove_preimage(preimage_length)
                state.services.store_service_account(service_id, service_account)

                preimage_updated = True
            elif preimage_cardinality == 1:

                state.services.store_preimage_availability(
                    service_id,
                    preimage_hash,
                    preimage_length,
                    preimage_availability + [timeslot]
                )
                preimage_updated = True
            elif preimage_cardinality == 3 and preimage_availability[1] < (timeslot - PREIMAGE_EXPUNGE_TIMESLOTS):

                # Note: reset unreferenced preimage expunge time with current timeslot
                state.services.store_preimage_availability(
                    service_id,
                    preimage_hash,
                    preimage_length,
                    [preimage_availability[2], timeslot]
                )
                preimage_updated = True
        except StateKeyNoResult:
            pass

    except PVMMemoryError:
        preimage_hash = None #GP: h = ∇

    if preimage_hash is None:
        invocation_output.exit_condition = ExitCondition(reason=ExitReason.panic)
        logger and logger.hc_log("FORGET PANIC", f"")
    elif preimage_updated is False:
        invocation_output.exit_condition = ExitCondition(reason=ExitReason.resume)
        invocation_output.registers[7] = HostCallResult.HUH.value
        logger and logger.hc_log("FORGET HUH", f"preimage_hash={preimage_hash.hex()}")
    else:
        invocation_output.exit_condition = ExitCondition(reason=ExitReason.resume)
        invocation_output.registers[7] = HostCallResult.OK.value
        logger and logger.hc_log("FORGET OK", f"preimage_hash={preimage_hash.hex()}")


def hc_yield(
        registers: List[int],
        memory: PVMMemory,
        x: AccumulateInvocationContext,
        invocation_output: InvocationMutationOutput,
        logger: PVMLogger):
    """
    GP-0.7.1-section:B.7 (Ω_Y) | Accumulate host function: yield.

    Set the default result hash of Accumulation.
    hash: The hash to be used as the Accumulation result.
    This value will be returned from Accumulation on success. It may be overridden by further calls to this function or
    by explicitly returning Some value from the Service::accumulate function. The checkpoint function may be used after
    a call to this function to ensure that this value is returned in the case of an irregular termination.
    --------------------------
    Sets the invocation output given what is put in pvm memory

    Parameters
    ----------
    registers: List[int]
    memory: PVMMemory
    x: AccumulateInvocationContext
    invocation_output: InvocationMutationOutput
    logger: PVMLogger

    Returns
    ----------
    None
    """
    logger and logger.hc_regs(f"YIELD", "accumulate")
    invocation_output.gas_limit -= 10
    o = registers[7]

    # gp: h
    if memory.is_accessible(o, 32, MEM_R):
        invocation_data = memory.read_bytes(o, 32)
    else:
        invocation_data = None

    if invocation_data is None:
        invocation_output.exit_condition = ExitCondition(reason=ExitReason.panic)
        logger and logger.hc_log("YIELD PANIC", f"")
    else:
        invocation_output.exit_condition = ExitCondition(reason=ExitReason.resume)
        invocation_output.registers[7] = HostCallResult.OK.value
        x.context.invocation_output = invocation_data
        logger and logger.hc_log("YIELD OK", f"invocation_data={invocation_data.hex()}")


def hc_provide(
        registers: List[int],
        memory: PVMMemory,
        ctx_in: AccumulateInvocationContext,
        services: ServicesState,
        service_id: int,
        invocation_output: InvocationMutationOutput,
        logger: PVMLogger):
    """
    GP-0.7.1-section:B.7 (Ω_P) | Accumulate host function: provide.

    Provides a preimage for specified service ID

    Parameters
    ----------
    registers: List[int]
    memory: PVMMemory
    ctx_in: AccumulateInvocationContext
    services: ServicesState
    service_id: int
    invocation_output: InvocationMutationOutput
    logger: PVMLogger

    Returns
    ----------
    None
    """

    logger and logger.hc_regs(f"PROVIDE", "accumulate")
    invocation_output.gas_limit -= 10

    preimage_address = registers[8] # GP: o
    preimage_length = registers[9]  # GP: z

    # GP: s*
    if registers[7] == 2 ** 64 - 1:
        service_account_id = service_id
    else:
        service_account_id = registers[7]

    # GP: i
    if memory.is_accessible(preimage_address, preimage_length, MEM_R):
        preimage_blob = memory.read_bytes(preimage_address, preimage_length)
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
        invocation_output.exit_condition = ExitCondition(reason=ExitReason.panic)
        logger and logger.hc_log("PROVIDE PANIC", f"")

    elif service_account is None:
        invocation_output.exit_condition = ExitCondition(reason=ExitReason.resume)
        invocation_output.registers[7] = HostCallResult.WHO.value
        logger and logger.hc_log("PROVIDE WHO", f"")

    elif preimage_availability != []:
        invocation_output.exit_condition = ExitCondition(reason=ExitReason.resume)
        invocation_output.registers[7] = HostCallResult.HUH.value
        logger and logger.hc_log("PROVIDE HUH", f"")

    elif (service_account_id, preimage_blob) in ctx_in.context.preimages:
        invocation_output.exit_condition = ExitCondition(reason=ExitReason.resume)
        invocation_output.registers[7] = HostCallResult.HUH.value
        logger and logger.hc_log("PROVIDE HUH", f"")

    else:
        invocation_output.exit_condition = ExitCondition(reason=ExitReason.resume)
        invocation_output.registers[7] = HostCallResult.OK.value

        # Add preimage to invocation context
        ctx_in.context.preimages.append((service_account_id, preimage_blob))

        logger and logger.hc_log("PROVIDE OK", f"h={format_hash(blake2b_256_hash(preimage_blob))}")
