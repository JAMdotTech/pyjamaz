import json
import os
import unittest
from copy import deepcopy
from dataclasses import dataclass, field
from os import path
from typing import Optional, List

from parameterized import parameterized

from jamcodec.mixins import Serializable
from jamcodec.types import U32, H256, Vec, Array, U8, Option, Enum
from pyjamaz.graypaper_constants import MAXIMUM_AUTHORIZATION_QUEUE_ITEMS, CORE_COUNT, VALIDATOR_COUNT, EPOCH_TIMESLOTS
from pyjamaz.app import AppConfig, PyjamazApp
from pyjamaz.state.components import Timeslot, Entropy, ValidatorArchive, ValidatorPool, Safrole, ValidatorQueue
from pyjamaz.exceptions import PyjamazAppError
from pyjamaz.storage import InMemoryStorage
from pyjamaz.models.common import ValidatorData
from pyjamaz.models.stf_output import SafroleErrorCode
from pyjamaz.models.block import Block, Header, Extrinsic, ExtrinsicDisputes, TicketEnvelope, TicketBody, \
    EpochMark, TicketsMark
from pyjamaz.models.state import JamState, TimeslotState, EntropyState, SafroleState, ValidatorQueueState, \
    ValidatorPoolState, ValidatorArchiveState, RecentHistoryState, ServicesState, AssurancesState, \
    PrivilegedServicesState, DisputesState, StatisticsState, AuthorizerPoolsState, \
    AuthorizerQueuesState, Statistic, SlotSealerSeries


@dataclass
class SafroleTestState(Serializable):
    # Most recent block's timeslot.
    tau: int = field(metadata={'codec': U32})

    eta: List[bytes] = field(metadata={'codec': Array(H256, 4)})
    lambda_: List[ValidatorData] = field(
        metadata={'codec': Array(ValidatorData.to_codec_def(), VALIDATOR_COUNT)}
        )  # Validator keys and metadata which were active in the prior epoch.
    kappa: List[ValidatorData] = field(
        metadata={'codec': Array(ValidatorData.to_codec_def(), VALIDATOR_COUNT)}
        )  # Validator keys and metadata currently active.
    gamma_k: List[ValidatorData] = field(
        metadata={'codec': Array(ValidatorData.to_codec_def(), VALIDATOR_COUNT)}
        )  # Validator keys for the following epoch.
    iota: List[ValidatorData] = field(
        metadata={'codec': Array(ValidatorData.to_codec_def(), VALIDATOR_COUNT)}
        )  # Validator keys and metadata to be drawn from next.
    gamma_a: List[TicketBody] = field(
        metadata={'codec': Vec(TicketBody.to_codec_def())}
        )  # Sealing-key contest ticket accumulator.
    gamma_s: SlotSealerSeries = field(
        metadata={'codec': SlotSealerSeries.to_codec_def()})  # Sealing-key series of the current epoch.
    gamma_z: bytes = field(metadata={'codec': Array(U8, 144)})  # Bandersnatch ring commitment.


@dataclass
# Todo: (Re)move, annotate, reference-GP
class SafroleOutputMarks(Serializable):
    epoch_mark: Optional[EpochMark] = field(default=None, metadata={'codec': Option(EpochMark.to_codec_def())})   # New epoch signal. OPTIONAL
    tickets_mark: Optional[TicketsMark] = field(default=None, metadata={'codec': Option(Array(TicketBody.to_codec_def(), EPOCH_TIMESLOTS))})  # Tickets signal. OPTIONAL


@dataclass
class SafroleTestOutput(Serializable):
    ok: Optional[SafroleOutputMarks] = field(default=None, metadata={'codec': Option(SafroleOutputMarks.to_codec_def())})  # Markers
    err: Optional[SafroleErrorCode] = field(default=None, metadata={'codec': Option(SafroleErrorCode.to_codec_def())})  # Error code (not specified in the Graypaper)

    _codec_type_def = Enum(
        ok=SafroleOutputMarks.to_codec_def(),
        err=SafroleErrorCode.to_codec_def()
    )

    def serialize(self) -> dict:
        if self.err is not None:
            return {'err': self.err.serialize()}
        else:
            return {'ok': self.ok.serialize()}


@dataclass
class SafroleInput(Serializable):
    slot: int = field(metadata={'codec': U32})  # Current slot. U32
    entropy: bytes = field(metadata={'codec': H256})  # Per block entropy (originated from block entropy source VRF)
    extrinsic: List[TicketEnvelope] = field(metadata={'codec': Vec(TicketEnvelope.to_codec_def())})  # Safrole extrinsic. SEQUENCE (SIZE(0..16)) OF TicketEnvelope
    post_offenders: List[bytes] = field(metadata={'codec': Vec(H256)})


@dataclass
class Testcase(Serializable):
    input: SafroleInput = field(metadata={'codec': SafroleInput.to_codec_def()})  # Input.
    pre_state: SafroleTestState = field(metadata={'codec': SafroleTestState.to_codec_def()})  # Pre-execution state.
    output: SafroleTestOutput = field(metadata={'codec': SafroleTestOutput.to_codec_def()})  # Output.
    post_state: SafroleTestState = field(metadata={'codec': SafroleTestState.to_codec_def()})  # Post-execution state.


def get_test_vector_files(directories: list, file_filter: Optional[str] = None):
    test_vectors = []
    for directory in directories:
        abs_dir = path.join(path.dirname(path.abspath(__file__)), 'fixtures', 'safrole', directory)
        for filename in os.listdir(str(abs_dir)):
            if filename.endswith('.json'):
                if file_filter is None or file_filter in filename:
                    test_vectors.append((f'{directory}_{filename}', directory, filename))
    return test_vectors


class TestSafroleVector(unittest.IsolatedAsyncioTestCase):

    @classmethod
    def setUpClass(cls):
        # Set up ring data
        data_dir = path.join(path.dirname(path.abspath(__file__)), '..', 'pyjamaz', 'data')
        with open(path.join(data_dir, 'zcash-srs-2-11-uncompressed.bin'), 'rb') as fp:
            cls.ring_data = fp.read()

        cls.config = AppConfig(
            ring_data=cls.ring_data,
            storage_engine=InMemoryStorage(),
            common_era=0
        )

    @staticmethod
    def load_test_vector_data(directory, test_vector_file):
        test_vector_file = path.join(
            path.dirname(path.abspath(__file__)), 'fixtures', 'safrole', directory, test_vector_file
            )
        with open(test_vector_file) as f:
            return json.load(f)

    @parameterized.expand(get_test_vector_files(['tiny'], file_filter=''))
    async def test_vector(self, name, directory, test_file):

        test_vector = self.load_test_vector_data(directory, test_file)

        test_vector['pre_state']['lambda_'] = test_vector['pre_state'].pop('lambda')
        test_vector['post_state']['lambda_'] = test_vector['post_state'].pop('lambda')

        test_case = Testcase.from_json(test_vector)

        # TODO make type factory to bootstrap state SCALE models with correct constants
        # if directory == 'tiny':
        #     gp_const.VALIDATOR_COUNT = 6
        #     gp_const.EPOCH_TIMESLOTS = 12
        #     gp_const.TICKET_SUBMISSION_END_SLOT = 10
        # else:
        #     gp_const.VALIDATOR_COUNT = 1023
        #     gp_const.EPOCH_TIMESLOTS = 600
        #     gp_const.TICKET_SUBMISSION_END_SLOT = 500

        # Build initial state
        jam_state = JamState.generate()

        jam_state.timeslot = TimeslotState(
            number=test_case.pre_state.tau
        )
        jam_state.entropy = EntropyState(
            entropy=test_case.pre_state.eta
        )
        jam_state.safrole = SafroleState(
            ticket_accumulator=test_case.pre_state.gamma_a,
            validators=test_case.pre_state.gamma_k,
            slot_sealer_series=test_case.pre_state.gamma_s,
            ring_commitment=test_case.pre_state.gamma_z,
        )
        jam_state.validator_queue = ValidatorQueueState(
            validators=test_case.pre_state.iota
        )
        jam_state.validator_pool = ValidatorPoolState(
            validators=test_case.pre_state.kappa
        )
        jam_state.validator_archive = ValidatorArchiveState(
            validators=test_case.pre_state.lambda_
        )
        jam_state.disputes.offenders = test_case.input.post_offenders

        # Convert test case input to block
        test_case_input = deepcopy(test_case.input)

        extrinsic = Extrinsic(
            tickets=test_case_input.extrinsic,
            disputes=ExtrinsicDisputes(verdicts=[], culprits=[], faults=[]),
            preimages=[],
            assurances=[],
            guarantees=[]
        )

        block = Block(
            header=Header(
                parent=bytes(32),
                parent_state_root=bytes(32),
                extrinsic_hash=extrinsic.generate_extrinsic_hash(),
                timeslot=test_case_input.slot,
                epoch_marker=None,
                tickets_marker=None,
                offenders_marker=[],
                author_index=0,
                entropy_source=test_case_input.entropy.ljust(96, b'\x00'),
                seal=bytes(96)
            ),
            extrinsic=extrinsic
        )

        # Initialize app
        app = PyjamazApp(config=self.config)
        # app.state = jam_state
        app.store_jam_state(jam_state)

        # Process block
        try:
            app.state = app.retrieve_jam_state()

            # TODO temp check
            if block.header.timeslot <= app.state.timeslot.number:
                raise PyjamazAppError(SafroleErrorCode.bad_slot)

            output = await app.import_block(block, validate=False)
            output = SafroleTestOutput(
                ok=SafroleOutputMarks(
                    epoch_mark=output.epoch_mark, tickets_mark=output.tickets_mark
                )
            )
        except PyjamazAppError as e:
            output = SafroleTestOutput(err=e.custom_error_code)

        self.assertEqual(test_case.output, output, f'{name}: output does not match')
        self.assertEqual(test_case.post_state.tau, app.components.timeslot.retrieve_state().number, f'{name}:tau does not match')
        self.assertEqual(test_case.post_state.eta, app.components.entropy.retrieve_state().entropy, f'{name}: eta does not match')
        self.assertEqual(test_case.post_state.lambda_, app.components.validator_archive.retrieve_state().validators, f'{name}: lambda_ does not match')
        self.assertEqual(test_case.post_state.kappa, app.components.validator_pool.retrieve_state().validators, f'{name}: kappa does not match')
        self.assertEqual(test_case.post_state.gamma_k, app.components.safrole.retrieve_state().validators, f'{name}: gamma_k does not match')
        self.assertEqual(test_case.post_state.iota, app.components.validator_queue.retrieve_state().validators, f'{name}: iota does not match')
        self.assertEqual(test_case.post_state.gamma_a, app.components.safrole.retrieve_state().ticket_accumulator, f'{name}: gamma_a does not match')
        self.assertEqual(test_case.post_state.gamma_s, app.components.safrole.retrieve_state().slot_sealer_series, f'{name}: gamma_s does not match')
        self.assertEqual(test_case.post_state.gamma_z, app.components.safrole.retrieve_state().ring_commitment, f'{name}: gamma_z does not match')


if __name__ == '__main__':
    unittest.main()
