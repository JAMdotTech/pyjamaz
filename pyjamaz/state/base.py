import typing
from typing import List

from pyjamaz.constants import WELL_KNOWN_STORAGE_KEYS
from pyjamaz.exceptions import StateComponentNotFound
from pyjamaz.storage import StorageInterface

if typing.TYPE_CHECKING:
    from pyjamaz.types.state import JamState
    from pyjamaz.models.block import Block


T = typing.TypeVar('T')


class State:
    def allow_read(self) -> List['StateManager']:
        pass

    def allow_write(self) -> List['StateManager']:
        pass

    def __setattr__(self, key, value):
        super().__setattr__(key, value)

    def retrieve(self):
        """
        Retrieve from Storage TODO
        Returns
        -------

        """
        pass

    def store(self):
        pass


def state_key_constructor_component(state_component_id: int) -> bytes:
    """
    GP-ref:280,281 Only wellknown storage keys

    :param state_component_id:
    :return:
    """
    try:
        return WELL_KNOWN_STORAGE_KEYS[state_component_id]
    except IndexError:
        raise StateComponentNotFound(f"State component ID {state_component_id} not found")


class StateManager:

    component_id: int

    def __init__(self, storage_engine: StorageInterface, app, **kwargs):
        self.storage_engine = storage_engine
        # TODO make nicer (tm) e.g. StateComponentManager
        self.app = app
        # self.state = self.retrieve()
        self.pre_state = None
        self.post_state = None

    def get_state_component(self, component_id: typing.Type[T]) -> T:
        return self.app.state_managers[component_id]

    def state_transition(self, block: 'Block'):
        raise NotImplementedError

    def retrieve(self):
        return self.storage_engine.retrieve(WELL_KNOWN_STORAGE_KEYS[self.component_id])

    def store(self, data: bytes):
        self.storage_engine.store(state_key_constructor_component(self.component_id), data)

    def store_state(self):
        data = self.post_state.to_scale_bytes().to_bytes()
        self.store(data)

    def retrieve_state(self):
        raise NotImplementedError



# def state_key_constructor_service(state_component_id: int, service_account_id: int) -> bytes:
#     """
#     GP-ref:280,281 Generates storage keys for individual service
#
#     :param state_component_id:
#     :param service_account_id:
#     :return:
#     """
#     return bytes([s, i, h])
#
#
# def state_key_constructor_service_item(service_account_id: int, service_account_key: bytes) -> bytes:
#     """
#     GP-ref:280,281 Generates storage keys for items within an individual service
#
#     :param service_account_id:
#     :param service_account_key:
#     :return:
#     """
#     return bytes([s, i, h])
