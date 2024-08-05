import json
import os
import unittest
from copy import deepcopy
from dataclasses import dataclass
from os import path
from typing import List, Optional

from parameterized import parameterized

from pyjamaz.mixins import SerializableMixin
from pyjamaz.safrole import SafroleProtocol
from pyjamaz.safrole.types import (State, Output, Input)


@dataclass
class Testcase(SerializableMixin):
    input: Input  # Input.
    pre_state: State  # Pre-execution state.
    output: Output  # Output.
    post_state: State  # Post-execution state.


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
        data_dir = path.join(path.dirname(path.abspath(__file__)), '..', 'data')
        with open(path.join(data_dir, 'zcash-srs-2-11-uncompressed.bin'), 'rb') as fp:
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
        test_case = Testcase.deserialize(test_vector)

        if directory == 'tiny':
            validators_count = 6
            epoch_length = 12
        else:
            validators_count = 1023
            epoch_length = 600

        safrole = SafroleProtocol(self.ring_data, deepcopy(test_case.pre_state), validators_count, epoch_length)
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
