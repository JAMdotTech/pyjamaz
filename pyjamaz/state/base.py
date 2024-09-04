from typing import List, Union, TYPE_CHECKING, TypeVar, Dict, Type, Optional

from pyjamaz.constants import WELL_KNOWN_STORAGE_KEYS
from pyjamaz.exceptions import StateComponentNotFound
from pyjamaz.storage import StorageInterface, Transaction
from pyjamaz.types.safrole import OutputMarks

if TYPE_CHECKING:
    from pyjamaz.types.block import Block


T = TypeVar('T')


class State:

    def __setattr__(self, key, value):
        super().__setattr__(key, value)


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

    def __init__(self, storage_engine: StorageInterface):
        self.storage_engine = storage_engine
        self.state_components: Dict[Type['StateComponent'], StateComponent] = {}
        self.state_components_by_id: Dict[int, StateComponent] = {}

    def add(self, state_component: Type['StateComponent'], **args):
        obj = state_component(
            self.storage_engine, self, **args
        )
        self.state_components_by_id[state_component.component_id] = obj
        self.state_components[state_component] = obj

    def get(self, state_component: Type['StateComponent']) -> 'StateComponent':
        try:
            return self.state_components[state_component]
        except KeyError:
            raise StateComponentNotFound(f"State component {state_component} not found")

    def get_by_id(self, state_component_id: int) -> 'StateComponent':
        try:
            return self.state_components_by_id[state_component_id]
        except KeyError:
            raise StateComponentNotFound(f"State component ID {state_component_id} not found")

    def __iter__(self):
        return iter(self.state_components.values())


class StateComponent:

    component_id: int

    def __init__(self, storage_engine: StorageInterface, state_manager: StateManager, **kwargs):
        self.storage_engine = storage_engine
        self.state_manager = state_manager

        self.pre_state = None
        self.post_state = None
        self.output_marks: Optional[OutputMarks] = None

    def initialize(self, pre_state: State, post_state: State, output_marks: OutputMarks):
        """
        Sets all required variable to perform a state transition

        Parameters
        ----------
        pre_state
        post_state
        output_marks

        Returns
        -------

        """
        self.pre_state = pre_state
        self.post_state = post_state
        self.output_marks = output_marks

    def get_state_component(self, state_component: Type[T]) -> T:
        return self.state_manager.get_by_id(state_component.component_id)

    def state_transition(self, block: 'Block'):
        raise NotImplementedError

    def retrieve(self):
        return self.storage_engine.retrieve(WELL_KNOWN_STORAGE_KEYS[self.component_id])

    def store(self, data: bytes, transaction: Transaction = None):
        if transaction is not None:
            transaction.store(state_key_constructor_component(self.component_id), data)
        else:
            self.storage_engine.store(state_key_constructor_component(self.component_id), data)

    def store_state(self, transaction: Transaction = None):
        data = self.post_state.to_jam_bytes().to_bytes()
        self.store(data, transaction)

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
