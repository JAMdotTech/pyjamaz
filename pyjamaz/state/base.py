import typing
from typing import List

from pyjamaz.constants import WELL_KNOWN_STORAGE_KEYS
from pyjamaz.exceptions import StateComponentNotFound

if typing.TYPE_CHECKING:
    from pyjamaz.types.state import JamState
    from pyjamaz.models.block import Block


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


class StateManager:

    def __init__(self, current_state: 'JamState', pre_state: 'JamState'):
        self.state = current_state
        self.pre_state = pre_state
        self.post_state = None

    def state_transition(self, block: 'Block'):
        raise NotImplementedError

    def is_epoch_change(self):
        return self.state.timeslot.epoch_number() != self.pre_state.timeslot.epoch_number()


# TODO process

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


def state_key_constructor_service(state_component_id: int, service_account_id: int) -> bytes:
    """
    GP-ref:280,281 Generates storage keys for individual service

    :param state_component_id:
    :param service_account_id:
    :return:
    """
    return bytes([s, i, h])


def state_key_constructor_service_item(service_account_id: int, service_account_key: bytes) -> bytes:
    """
    GP-ref:280,281 Generates storage keys for items within an individual service

    :param service_account_id:
    :param service_account_key:
    :return:
    """
    return bytes([s, i, h])
