from pyjamaz.hostcalls.general import GeneralFunctionsMixin
from pyjamaz.types import AppType


class HostCalls(GeneralFunctionsMixin):

    def __init__(self, app:AppType):
        self.app = app
        self.service_db = app.get_service_db()
