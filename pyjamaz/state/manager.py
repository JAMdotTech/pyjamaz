from typing import Dict, Type

from pyjamaz.exceptions import StateComponentNotFound
from pyjamaz.state.base import StateComponent, T
from pyjamaz.storage import StorageEngine


class StateManager:

    def __init__(self, storage_engine: StorageEngine):
        self.storage_engine: StorageEngine = storage_engine
        self.state_components: Dict[Type['StateComponent'], StateComponent] = {}
        self.state_components_by_id: Dict[int, StateComponent] = {}

    def add(self, state_component: Type['StateComponent'], **args):
        obj = state_component(
            self.storage_engine, **args
        )
        self.state_components_by_id[state_component.component_id] = obj
        self.state_components[state_component] = obj

    def get(self, state_component: Type[T]) -> T:
        try:
            return self.state_components[state_component]
        except KeyError:
            raise StateComponentNotFound(f"State component {state_component} not found")

    def initialize(self, state_component: Type[T]) -> T:
        component_obj = self.get(state_component)
        component_obj.initialize()
        return component_obj

    def get_by_id(self, state_component_id: int) -> 'StateComponent':
        try:
            return self.state_components_by_id[state_component_id]
        except KeyError:
            raise StateComponentNotFound(f"State component ID {state_component_id} not found")
