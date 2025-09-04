import pyjamaz.graypaper_constants as gp_const



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
from pyjamaz.app import AppConfig
from pyjamaz.exceptions import StateTransitionError
from pyjamaz.settings import TEST_SUITE
from pyjamaz.models.context import AppContext, BlockContext
from pyjamaz.state.components import Safrole, Entropy, ValidatorPool, ValidatorArchive, Timeslot
from pyjamaz.storage import InMemoryStorage
from pyjamaz.models.common import ValidatorData, TicketBody
from pyjamaz.models.stf_output import SafroleErrorCode
from pyjamaz.models.block import Block, Header, Extrinsic, ExtrinsicDisputes, TicketEnvelope, EpochMark
from pyjamaz.models.state import JamState, TimeslotState, EntropyState, SafroleState, ValidatorQueueState, \
    ValidatorPoolState, ValidatorArchiveState, SlotSealerSeries


@dataclass
class SafroleTestState(Serializable):
    # Most recent block's timeslot.
    tau: int = field(metadata={'codec': U32})

    eta: List[bytes] = field(metadata={'codec': Array(H256, 4)})
    lambda_: List[ValidatorData] = field(
        metadata={'codec': Array(ValidatorData.to_codec_def(), gp_const.VALIDATOR_COUNT)}
        )  # Validator keys and metadata which were active in the prior epoch.
    kappa: List[ValidatorData] = field(
        metadata={'codec': Array(ValidatorData.to_codec_def(), gp_const.VALIDATOR_COUNT)}
        )  # Validator keys and metadata currently active.
    gamma_k: List[ValidatorData] = field(
        metadata={'codec': Array(ValidatorData.to_codec_def(), gp_const.VALIDATOR_COUNT)}
        )  # Validator keys for the following epoch.
    iota: List[ValidatorData] = field(
        metadata={'codec': Array(ValidatorData.to_codec_def(), gp_const.VALIDATOR_COUNT)}
        )  # Validator keys and metadata to be drawn from next.
    gamma_a: List[TicketBody] = field(
        metadata={'codec': Vec(TicketBody.to_codec_def())}
        )  # Sealing-key contest ticket accumulator.
    gamma_s: SlotSealerSeries = field(
        metadata={'codec': SlotSealerSeries.to_codec_def()})  # Sealing-key series of the current epoch.
    gamma_z: bytes = field(metadata={'codec': Array(U8, 144)})  # Bandersnatch ring commitment.
    post_offenders: List[bytes] = field(metadata={'codec': Vec(H256)})


@dataclass
# Todo: (Re)move, annotate, reference-GP
class SafroleOutputMarks(Serializable):
    epoch_mark: Optional[EpochMark] = field(default=None, metadata={'codec': Option(EpochMark.to_codec_def())})   # New epoch signal. OPTIONAL
    tickets_mark: Optional[List[TicketBody]] = field(default=None, metadata={'codec': Option(Array(TicketBody.to_codec_def(), gp_const.EPOCH_TIMESLOTS))})  # Tickets signal. OPTIONAL


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

    @parameterized.expand(get_test_vector_files([TEST_SUITE], file_filter=''))
    async def test_vector(self, name, directory, test_file):

        test_vector = self.load_test_vector_data(directory, test_file)

        test_vector['pre_state']['lambda_'] = test_vector['pre_state'].pop('lambda')
        test_vector['post_state']['lambda_'] = test_vector['post_state'].pop('lambda')

        test_case = Testcase.from_json(test_vector)

        # Build initial state
        pre_state = JamState.create_genesis_state()

        pre_state.timeslot = TimeslotState(
            number=test_case.pre_state.tau
        )
        pre_state.entropy = EntropyState(
            entropy=test_case.pre_state.eta
        )
        pre_state.safrole = SafroleState(
            ticket_accumulator=test_case.pre_state.gamma_a,
            validators=test_case.pre_state.gamma_k,
            slot_sealer_series=test_case.pre_state.gamma_s,
            ring_commitment=test_case.pre_state.gamma_z,
        )
        pre_state.validator_queue = ValidatorQueueState(
            validators=test_case.pre_state.iota
        )
        pre_state.validator_pool = ValidatorPoolState(
            validators=test_case.pre_state.kappa
        )
        pre_state.validator_archive = ValidatorArchiveState(
            validators=test_case.pre_state.lambda_
        )
        pre_state.disputes.offenders = test_case.pre_state.post_offenders

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
                entropy_source=test_case_input.entropy,
                seal=bytes(96)
            ),
            extrinsic=extrinsic
        )

        # Process block
        try:

            # Timeslot
            timeslot = Timeslot(InMemoryStorage(), BlockContext(), AppContext())
            timeslot_output = await timeslot.state_transition(header=block.header)
            post_state_timeslot = timeslot_output.post_state

            # Entropy
            entropy = Entropy(InMemoryStorage(), BlockContext(), AppContext())
            entropy_output = await entropy.state_transition(
                header=block.header,
                pre_state_timeslot=pre_state.timeslot,
                pre_state_entropy=pre_state.entropy
            )
            post_state_entropy = entropy_output.post_state

            # Validator Pool
            validator_pool = ValidatorPool(InMemoryStorage(), BlockContext(), AppContext())
            validator_pool_output = await validator_pool.state_transition(
                header=block.header,
                pre_state_timeslot=pre_state.timeslot,
                pre_state_validator_pool=pre_state.validator_pool,
                pre_state_safrole=pre_state.safrole
            )
            post_state_validator_pool = validator_pool_output.post_state

            # Validator Archive
            validator_archive = ValidatorArchive(InMemoryStorage(), BlockContext(), AppContext())
            validator_archive_output = await validator_archive.state_transition(
                header=block.header,
                pre_state_timeslot=pre_state.timeslot,
                pre_state_validator_pool=pre_state.validator_pool,
                pre_state_validator_archive=pre_state.validator_archive
            )
            post_state_validator_archive = validator_archive_output.post_state

            # Safrole
            safrole = Safrole(InMemoryStorage(), BlockContext(), AppContext(), self.config.ring_data)
            output = await safrole.state_transition(
                header=block.header,
                extrinsic_tickets=block.extrinsic.tickets,
                pre_state_timeslot=pre_state.timeslot,
                pre_state_safrole=pre_state.safrole,
                pre_state_validator_queue=pre_state.validator_queue,
                post_state_entropy=entropy_output.post_state,
                post_state_validator_pool=validator_pool_output.post_state,
                post_state_disputes=pre_state.disputes
            )

            post_state_safrole = output.post_state

            output = SafroleTestOutput(
                ok=SafroleOutputMarks(
                    epoch_mark=output.epoch_mark, tickets_mark=output.tickets_mark
                )
            )
        except StateTransitionError as e:
            output = SafroleTestOutput(err=e.custom_error_code)
            post_state_safrole = pre_state.safrole
            post_state_timeslot = pre_state.timeslot
            post_state_entropy = pre_state.entropy
            post_state_validator_pool = pre_state.validator_pool
            post_state_validator_archive = pre_state.validator_archive

        self.assertEqual(test_case.output, output, f'{name}: output does not match')
        self.assertEqual(test_case.post_state.tau, post_state_timeslot.number, f'{name}:tau does not match')
        self.assertEqual(test_case.post_state.eta, post_state_entropy.entropy, f'{name}: eta does not match')
        self.assertEqual(test_case.post_state.lambda_, post_state_validator_archive.validators, f'{name}: lambda_ does not match')
        self.assertEqual(test_case.post_state.kappa, post_state_validator_pool.validators, f'{name}: kappa does not match')
        self.assertEqual(test_case.post_state.gamma_k, post_state_safrole.validators, f'{name}: gamma_k does not match')
        self.assertEqual(test_case.post_state.gamma_a, post_state_safrole.ticket_accumulator, f'{name}: gamma_a does not match')
        self.assertEqual(test_case.post_state.gamma_s, post_state_safrole.slot_sealer_series, f'{name}: gamma_s does not match')
        self.assertEqual(test_case.post_state.gamma_z, post_state_safrole.ring_commitment, f'{name}: gamma_z does not match')

if __name__ == '__main__':
    unittest.main()
