import json
import unittest
from os import path

from pyjamaz.merkle import PatriciaMerkleTrie, ConstantDepthMerkleTree


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


    def test_constant_depth_tree(self):
        data = [b'a', b'b', b'c',b'd', b'e']
        tree = ConstantDepthMerkleTree(data)

        self.assertEqual(tree.root().hex(), 'f0d68d620e98df5a75169db88d70c155aba4a9f5b9585933cbbb9e259aeaa642')

if __name__ == '__main__':
    unittest.main()
