from typing import Any, Protocol

# Our App interface, see: https://peps.python.org/pep-0544/
class AppType(Protocol):
    hostcalls = None

    #TODO: add proper typings for interface return types!
    def get_service_db(self) -> Any:
        """Returns the db instances for services storage"""
    
    #TODO: add more properties defining an app interface!