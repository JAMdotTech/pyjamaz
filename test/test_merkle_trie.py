import json
import unittest
from os import path

from pyjamaz.merkle import PatriciaMerkleTrie


class TestMerkleTrie(unittest.TestCase):
    def test_json_testvectors(self):
        # TODO waiting for updated testvectors
        pass
        # with open(path.join(path.dirname(path.abspath(__file__)), 'fixtures', 'trie.json')) as f:
        #     test_vector = json.load(f)
        #
        # for item in test_vector:
        #     data_tree = [(bytes.fromhex(k), bytes.fromhex(v)) for k, v in item['input'].items()]
        #
        #     output = PatriciaMerkleTrie(data_tree).root()
        #     self.assertEqual(item['output'], output.hex())


if __name__ == '__main__':
    unittest.main()
