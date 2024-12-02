from copy import deepcopy
from typing import TypeVar, Optional

import pyjamaz.graypaper_constants as gp_const
from jamcodec.mixins import Serializable
from pyjamaz.constants import WELL_KNOWN_STORAGE_KEYS
from pyjamaz.exceptions import StateComponentNotFound, StateKeyNoResult
from pyjamaz.storage import StorageEngine, Transaction

T = TypeVar('T')


class State(Serializable):

    def __setattr__(self, key, value):
        super().__setattr__(key, value)


class StateComponent:

    component_id: int

    def __init__(self, storage_engine: StorageEngine, **kwargs):

        self.output = None
        self.storage_engine = storage_engine

    def state_transition(self, *args):
        raise NotImplementedError

    def _state_key_constructor_component(self) -> bytes:
        """
        GP-0.3.8-eq:290,291 Only wellknown storage keys
        """
        try:
            return WELL_KNOWN_STORAGE_KEYS[self.component_id]
        except IndexError:
            raise StateComponentNotFound(f"State component ID {self.component_id} not found")

    def retrieve(self):
        result = self.storage_engine.get(self._state_key_constructor_component())
        if result is None:
            raise StateKeyNoResult(f"No result for state component {self.component_id}")
        return result

    def store(self, data: bytes, transaction: Transaction = None):
        if transaction is not None:
            transaction.put(self._state_key_constructor_component(), data)
        else:
            self.storage_engine.put(self._state_key_constructor_component(), data)

    def store_state(self, state: State, transaction: Optional[Transaction] = None):
        data = state.to_jam_bytes().to_bytes()
        self.store(data, transaction)

    def retrieve_state(self):
        raise NotImplementedError

    @staticmethod
    def is_epoch_change(pre_slotnumber: int, post_slotnumber: int) -> bool:
        """
        GP-0.3.8-general: `e!=e' ? T, F` | Helper function that determines if the epoch has changed.

        Returns
        -------
        bool
            `True` when epoch has changed, `False` otherwise.
        """
        if pre_slotnumber == 0 and post_slotnumber % gp_const.EPOCH_TIMESLOTS != 0:
            # TODO double-check what initial behavior should be when
            return False
        return pre_slotnumber // gp_const.EPOCH_TIMESLOTS != post_slotnumber // gp_const.EPOCH_TIMESLOTS

    @staticmethod
    def slot_phase_index(slot_number: int) -> int:
        """
        GP-0.3.8-eq:46 (m) | Function that returns the phase index into the epoch of the timeslot

        Returns
        -------
        number: int
            Phase index into the epoch of the timeslot

        """
        return slot_number % gp_const.EPOCH_TIMESLOTS

    @staticmethod
    def epoch_number(slot_number: int) -> int:
        """
        GP-0.3.8-eq:46 (e) | Function that returns the epoch index

        Returns
        -------
        number: int
            Epoch index of the timeslot

        """
        return slot_number // gp_const.EPOCH_TIMESLOTS

# def state_key_constructor_service(state_component_id: int, service_account_id: int) -> bytes:
#     """
#     GP-0.3.8-eq:290,291 Generates storage keys for individual service
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
#     GP-0.3.8-eq:290,291 Generates storage keys for items within an individual service
#
#     :param service_account_id:
#     :param service_account_key:
#     :return:
#     """
#     return bytes([s, i, h])
