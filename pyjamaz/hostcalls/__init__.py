from general import GeneralFunctionsMixin
from pyjamaz.types import AppType


class HostCalls(GeneralFunctionsMixin):

    def __init__(self, app:AppType):
        self._app = app
        self.service_db = app.get_service_db()
