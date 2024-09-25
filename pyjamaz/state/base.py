from copy import deepcopy
from typing import TypeVar

import pyjamaz.graypaper_constants as gp_const
from pyjamaz.constants import WELL_KNOWN_STORAGE_KEYS
from pyjamaz.exceptions import StateComponentNotFound
from pyjamaz.storage import StorageInterface, Transaction

T = TypeVar('T')


class State:

    def __setattr__(self, key, value):
        super().__setattr__(key, value)


class StateComponent:

    component_id: int

    def __init__(self, storage_engine: StorageInterface, **kwargs):

        self.pre_state = None
        self.post_state = None
        self.storage_engine = storage_engine

    def initialize(self):
        """
        Sets all required variable to perform a state transition

        Parameters
        ----------
        pre_state

        Returns
        -------

        """
        self.pre_state = self.retrieve_state()
        self.post_state = deepcopy(self.pre_state)

    def state_transition(self, *args):
        raise NotImplementedError

    def _state_key_constructor_component(self) -> bytes:
        """
        GP-ref:280,281 Only wellknown storage keys
        """
        try:
            return WELL_KNOWN_STORAGE_KEYS[self.component_id]
        except IndexError:
            raise StateComponentNotFound(f"State component ID {self.component_id} not found")

    def retrieve(self):
        return self.storage_engine.retrieve(self._state_key_constructor_component())

    def store(self, data: bytes, transaction: Transaction = None):
        if transaction is not None:
            transaction.store(self._state_key_constructor_component(), data)
        else:
            self.storage_engine.store(self._state_key_constructor_component(), data)

    def store_state(self, transaction: Transaction = None):
        data = self.post_state.to_jam_bytes().to_bytes()
        self.store(data, transaction)

    def retrieve_state(self):
        raise NotImplementedError

    @staticmethod
    def is_epoch_change(pre_slotnumber: int, post_slotnumber: int) -> bool:
        return pre_slotnumber // gp_const.EPOCH_TIMESLOTS != post_slotnumber // gp_const.EPOCH_TIMESLOTS

    @staticmethod
    def slot_phase_index(slot_number: int) -> int:
        """
        GP-0.3.6-eq:46 (m) | Function that returns the phase index into the epoch of the timeslot

        Returns
        -------
        number: int
            Phase index into the epoch of the timeslot

        """
        return slot_number % gp_const.EPOCH_TIMESLOTS

    @staticmethod
    def epoch_number(slot_number: int) -> int:
        """
        GP-0.3.6-eq:46 (e) | Function that returns the epoch index

        Returns
        -------
        number: int
            Epoch index of the timeslot

        """
        return slot_number // gp_const.EPOCH_TIMESLOTS

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
