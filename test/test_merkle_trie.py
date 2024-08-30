import json
import unittest

from pyjamaz.merkle import MerkleTree


class TestMerkleTrie(unittest.TestCase):
    def test_json_testvectors(self):
        with open('./fixtures/trie.json') as f:
            test_vector = json.load(f)

        for item in test_vector:
            data_tree = [(bytes.fromhex(k), bytes.fromhex(v)) for k, v in item['input'].items()]

            output = MerkleTree(data_tree).root()
            self.assertEqual(item['output'], output.hex())


if __name__ == '__main__':
    unittest.main()
