import json
import os
import unittest
from os import path
from typing import List, Optional

from parameterized import parameterized

from pyjamaz.safrole import TicketBody, State, Output, OutputMarks, \
    CustomErrorCode, SafroleProtocol
from pyjamaz.safrole.types import SlotSealerSeries, ValidatorData, TicketEnvelope, Input, Testcase


# JSON conversion functions

def hex_to_bytes(hex_str: str) -> bytes:
    return bytes.fromhex(hex_str[2:])

def json_to_ticket_envelope(json_obj) -> 'TicketEnvelope':
    return TicketEnvelope(
        attempt=json_obj["attempt"],
        signature=hex_to_bytes(json_obj["signature"])
    )

def json_to_ticket_body(json_obj) -> 'TicketBody':
    return TicketBody(
        id=hex_to_bytes(json_obj["id"]),
        attempt=json_obj["attempt"]
    )

def json_to_validator_data(json_obj) -> 'ValidatorData':
    return ValidatorData(
        bandersnatch=hex_to_bytes(json_obj["bandersnatch"]),
        ed25519=hex_to_bytes(json_obj["ed25519"]),
        bls=hex_to_bytes(json_obj["bls"]),
        metadata=hex_to_bytes(json_obj["metadata"])
    )

def json_to_state(json_obj) -> 'State':
    return State(
        tau=json_obj["tau"],
        eta=[hex_to_bytes(e) for e in json_obj["eta"]],
        lambda_=[json_to_validator_data(v) for v in json_obj["lambda"]],
        kappa=[json_to_validator_data(v) for v in json_obj["kappa"]],
        gamma_k=[json_to_validator_data(v) for v in json_obj["gamma_k"]],
        iota=[json_to_validator_data(v) for v in json_obj["iota"]],
        gamma_a=[json_to_ticket_body(tb) for tb in json_obj["gamma_a"]],
        gamma_s=SlotSealerSeries(keys=[hex_to_bytes(k) for k in json_obj["gamma_s"]["keys"]]),
        gamma_z=hex_to_bytes(json_obj["gamma_z"])
    )

def json_to_input(json_obj) -> 'Input':
    return Input(
        slot=json_obj["slot"],
        entropy=hex_to_bytes(json_obj["entropy"]),
        extrinsic=[json_to_ticket_envelope(te) for te in json_obj["extrinsic"]]
    )

def json_to_output(json_obj) -> 'Output':
    return Output(
        ok=OutputMarks(epoch_mark=None, tickets_mark=None) if "ok" in json_obj else None,
        err=CustomErrorCode[json_obj["err"].upper()] if "err" in json_obj else None
    )

def json_to_testcase(json_obj) -> 'Testcase':
    return Testcase(
        input=json_to_input(json_obj["input"]),
        pre_state=json_to_state(json_obj["pre_state"]),
        output=json_to_output(json_obj["output"]),
        post_state=json_to_state(json_obj["post_state"])
    )


def get_test_vector_files(directories: list, file_filter: Optional[str] = None):
    test_vectors = []
    for directory in directories:
        abs_dir = path.join(path.dirname(path.abspath(__file__)), 'fixtures', 'safrole', directory)
        for filename in os.listdir(str(abs_dir)):
            if filename.endswith('.json'):
                if file_filter is None or file_filter in filename:
                    test_vectors.append((f'{directory}_{filename}', directory, filename))
    return test_vectors


class TestSafroleVector(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        # Set up ring data
        with open('../data/zcash-srs-2-11-uncompressed.bin', 'rb') as fp:
            cls.ring_data = fp.read()

    @staticmethod
    def load_test_vector_data(directory, test_vector_file):
        test_vector_file = path.join(
            path.dirname(path.abspath(__file__)), 'fixtures', 'safrole', directory, test_vector_file
            )
        with open(test_vector_file) as f:
            return json.load(f)

    @parameterized.expand(get_test_vector_files(['tiny'], file_filter=''))
    def test_vector(self, name, directory, test_file):
        test_vector = self.load_test_vector_data(directory, test_file)
        test_case = json_to_testcase(test_vector)

        if directory == 'tiny':
            validators_count = 6
            epoch_length = 12
        else:
            validators_count = 1023
            epoch_length = 600

        safrole = SafroleProtocol(self.ring_data, test_case.pre_state, validators_count, epoch_length)
        output = safrole.process_input(test_case.input)

        self.assertEqual(test_case.output, output, f'{name}: output does not match')
        self.assertEqual(test_case.post_state.tau, safrole.state.tau, f'{name}:tau does not match')
        self.assertEqual(test_case.post_state.eta, safrole.state.eta, f'{name}: eta does not match')
        self.assertEqual(test_case.post_state.lambda_, safrole.state.lambda_, f'{name}: lambda_ does not match')
        self.assertEqual(test_case.post_state.kappa, safrole.state.kappa, f'{name}: kappa does not match')
        self.assertEqual(test_case.post_state.gamma_k, safrole.state.gamma_k, f'{name}: gamma_k does not match')
        self.assertEqual(test_case.post_state.iota, safrole.state.iota, f'{name}: iota does not match')
        self.assertEqual(test_case.post_state.gamma_a, safrole.state.gamma_a, f'{name}: gamma_a does not match')
        self.assertEqual(test_case.post_state.gamma_s, safrole.state.gamma_s, f'{name}: gamma_s does not match')
        self.assertEqual(test_case.post_state.gamma_z, safrole.state.gamma_z, f'{name}: gamma_z does not match')


if __name__ == '__main__':
    unittest.main()
