# from dataclasses import dataclass
# from typing import List
#
# from pyjamaz.models.state import AccumulateInvocationContext
# from pyjamaz.pvm.types import PVMMemory
# from pyjamaz.pvm_interface.hostcalls import debug
# from pyjamaz.pvm_interface.hostcalls import general
# from pyjamaz.pvm_interface.hostcalls import accumulate
# from pyjamaz.pvm_interface.hostcalls import refine
#
# from pyjamaz.pvm_interface.hostcalls.constants import HostCallDebug, HostCallGeneral, HostCallAccumulate, HostCallRefine
#
#
# HostCallLookup = {
#     HostCallDebug.log.value: debug.hc_log,
#
#     HostCallGeneral.gas.value: general.hc_gas,
#     HostCallGeneral.lookup.value: general.hc_lookup,
#     HostCallGeneral.read.value: general.hc_read,
#     HostCallGeneral.write.value: general.hc_write,
#     HostCallGeneral.info.value: general.hc_info,
#
#     HostCallAccumulate.bless.value: accumulate.hc_bless,
#     HostCallAccumulate.assign.value: accumulate.hc_assign,
#     HostCallAccumulate.designate.value: accumulate.hc_designate,
#     HostCallAccumulate.checkpoint.value: accumulate.hc_checkpoint,
#     HostCallAccumulate.new.value: accumulate.hc_new,
#     HostCallAccumulate.upgrade.value: accumulate.hc_upgrade,
#     HostCallAccumulate.transfer.value: accumulate.hc_transfer,
#     HostCallAccumulate.eject.value: accumulate.hc_eject,
#     HostCallAccumulate.query.value: accumulate.hc_query,
#     HostCallAccumulate.solicit.value: accumulate.hc_solicit,
#     HostCallAccumulate.forget.value: accumulate.hc_forget,
#     HostCallAccumulate._yield.value: accumulate.hc_yield,
#
#     HostCallRefine.historical_lookup.value: refine.hc_historical_lookup,
#     HostCallRefine.fetch.value: refine.hc_fetch,
#     HostCallRefine.export.value: refine.hc_export,
#     HostCallRefine.machine.value: refine.hc_machine,
#     HostCallRefine.peek.value: refine.hc_peek,
#     HostCallRefine.poke.value: refine.hc_poke,
#     HostCallRefine.zero.value: refine.hc_zero,
#     HostCallRefine.void.value: refine.hc_void,
#     HostCallRefine.invoke.value: refine.hc_invoke,
#     HostCallRefine.expunge.value: refine.hc_expunge
# }
#
#
