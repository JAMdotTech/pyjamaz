# from pyjamaz.hostcalls.accumulate import AccumulateInvocationsMixin
# from pyjamaz.hostcalls.general import GeneralFunctionsMixin
# from pyjamaz.hostcalls.refine import RefineInvocationsMixin
# from pyjamaz.types import AppType
#
#
# class HostCalls(GeneralFunctionsMixin, AccumulateInvocationsMixin):
#
#     # GP_B.1 Is-Authorized Invocation ΨI
#     # def is_authorized(self, p:WorkPackageSet, c:CoreIndex):
#     #     check if a core is authorized to execute a given workpackage
#
#     def __init__(self, app:AppType):
#         self.app = app
#         self.service_db = app.get_service_db()
