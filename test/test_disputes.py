import os

import ed25519_zebra
from parameterized import parameterized

from typing import Optional

from dataclasses import dataclass

import json
import unittest
from os import path

from jamcodec.types import Vec
from pyjamaz.app import PyjamazApp, AppConfig
from pyjamaz.graypaper_constants import MAXIMUM_AUTHORIZATION_QUEUE_ITEMS, CORE_COUNT, VALIDATOR_COUNT, EPOCH_TIMESLOTS
from pyjamaz.signing import Keypair
from pyjamaz.state.base import State
from pyjamaz.state.components import Disputes, ValidatorPool, ValidatorArchive
from pyjamaz.state.exceptions import StateTransitionError
from pyjamaz.storage import InMemoryStorage

from pyjamaz.types.block import Header, OutputMarks, Extrinsic, Assurance, ExtrinsicDisputes, RefinementContext, WorkReport, \
    WorkResult, Guarantee, Preimage, TicketEnvelope, Block, WorkItem, WorkPackage
from pyjamaz.types.common import ValidatorData
from pyjamaz.types.stf_output import SafroleErrorCode, SafroleOutput, DisputesOutput
from pyjamaz.types.state import DisputesState, AssurancesState, AuthorizerPoolsState, AuthorizerQueuesState, \
    EntropyState, PrivilegedServicesState, RecentHistoryState, SafroleState, StatisticsState, TimeslotState, \
    ValidatorArchiveState, ValidatorPoolState, ValidatorQueueState, ServiceAccount, ServicesState, JamState, Statistic, \
    SlotSealerSeries


@dataclass
class TestState(State):
    timeslot: TimeslotState
    disputes: DisputesState
    validator_pool: ValidatorPoolState
    validator_archive: ValidatorArchiveState
    assurances: AssurancesState


def get_test_vector_files(directories: list, file_filter: Optional[str] = None):
    test_vectors = []
    for directory in directories:
        abs_dir = path.join(path.join(path.dirname(path.abspath(__file__)), 'fixtures', 'disputes'), directory)
        for filename in os.listdir(str(abs_dir)):
            if filename.endswith('.json'):
                if file_filter is None or file_filter in filename:
                    test_vectors.append((f'{directory}_{filename}', directory, filename))
    return test_vectors


class TestDisputes(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.test_vector_dir = path.join(path.dirname(path.abspath(__file__)), 'fixtures', 'disputes')

    def create_block(self, test_vector_input: dict) -> Block:
        return Block(
            header=Header(
                parent=bytes(32),
                parent_state_root=bytes(32),
                extrinsic_hash=bytes(32),
                timeslot=1,
                epoch_marker=None,
                tickets_marker=None,
                offenders_marker=[],
                author_index=0,
                entropy_source=bytes(32),
                seal=bytes(96)
            ),
            extrinsic=Extrinsic(
                tickets=[],
                disputes=ExtrinsicDisputes.from_json(test_vector_input['disputes']),
                preimages=[],
                assurances=[],
                guarantees=[]
            )
        )

    def create_jam_state(self, test_vector: dict) -> JamState:

        jam_state = JamState.generate()
        jam_state.timeslot.number = test_vector['tau']
        jam_state.validator_pool = ValidatorPoolState.from_json({"validators": test_vector['kappa']})
        jam_state.validator_archive = ValidatorArchiveState.from_json({"validators": test_vector['lambda']})
        jam_state.disputes = DisputesState(
            good_set=[bytes.fromhex(i[2:]) for i in test_vector['psi']['psi_g']],
            bad_set=[bytes.fromhex(i[2:]) for i in test_vector['psi']['psi_b']],
            wonky_set=[bytes.fromhex(i[2:]) for i in test_vector['psi']['psi_w']],
            offenders=[bytes.fromhex(i[2:]) for i in test_vector['psi']['psi_o']],
        )

        return jam_state

    @parameterized.expand(get_test_vector_files(['tiny'], file_filter=''))
    def test_vector(self, name, directory, test_file):
        with open(path.join(self.test_vector_dir, directory, test_file)) as f:
            test_vector = json.load(f)

        pre_state = self.create_jam_state(test_vector['pre_state'])

        block = self.create_block(test_vector['input'])

        # Initialize app
        app = PyjamazApp(config=AppConfig(
            ring_data=bytes(),
            storage_engine=InMemoryStorage()
        ))
        app.init_state(pre_state)

        # Process block
        try:
            output = app.process_block(block)
            dispute_output = {'ok': {"offenders_mark": output.to_json()['offenders_mark']}}
        except StateTransitionError as e:
            dispute_output = {'err': e.custom_error_code.name}

        self.assertEqual(test_vector['output'], dispute_output)

        psi = app.get_state(Disputes).to_json()

        post_state = {
            "psi": {
                'psi_b': psi['bad_set'],
                'psi_g': psi['good_set'],
                'psi_o': psi['offenders'],
                'psi_w': psi['wonky_set'],
            },
            "kappa": app.get_state(ValidatorPool).to_json()['validators'],
            "lambda": app.get_state(ValidatorArchive).to_json()['validators'],
        }

        self.assertDictEqual(test_vector['post_state']['psi'], post_state['psi'])
        self.assertListEqual(test_vector['post_state']['kappa'], post_state['kappa'])
        self.assertListEqual(test_vector['post_state']['lambda'], post_state['lambda'])


if __name__ == '__main__':
    unittest.main()
