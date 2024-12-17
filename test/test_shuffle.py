import json
import unittest
from os import path

from pyjamaz.merkle import PatriciaMerkleTrie
from pyjamaz.utils import entropy_shuffle


class TestShuffle(unittest.TestCase):
    def test_json_testvectors(self):

        with open(path.join(path.dirname(path.abspath(__file__)), 'fixtures', 'shuffle_tests.json')) as f:
            test_vector = json.load(f)

        for item in test_vector:
            output = entropy_shuffle(list(range(int(item["input"]))), bytes.fromhex(item["entropy"]))
            self.assertEqual(item['output'], output, f'{item['input']} fails')


if __name__ == '__main__':
    unittest.main()
