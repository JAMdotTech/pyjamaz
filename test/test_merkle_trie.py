import json
import unittest

from pyjamaz.merkle import PatriciaMerkleTrie, ConstantDepthMerkleTree
try:
    from test.vector_fixtures import trie_vector_file
except ModuleNotFoundError:  # Direct script execution.
    from vector_fixtures import trie_vector_file


class TestMerkleTrie(unittest.TestCase):
    def test_json_testvectors(self):
        with trie_vector_file().open() as fixture:
            test_vectors = json.load(fixture)

        for index, item in enumerate(test_vectors):
            with self.subTest(vector=index, entries=len(item['input'])):
                data_tree = []
                for encoded_key, encoded_value in item['input'].items():
                    # Upstream emits 32-byte keys, then leaf() uses k[:-1]
                    # to obtain the 31-byte state key defined in Appendix D.
                    vector_key = bytes.fromhex(encoded_key)
                    self.assertEqual(len(vector_key), 32)
                    data_tree.append((vector_key[:-1], bytes.fromhex(encoded_value)))

                output = PatriciaMerkleTrie(data_tree).root()
                self.assertEqual(item['output'], output.hex())

    def test_constant_depth_tree(self):
        data = [b'a', b'b', b'c',b'd', b'e']
        tree = ConstantDepthMerkleTree(data)

        self.assertEqual(tree.root().hex(), 'f0d68d620e98df5a75169db88d70c155aba4a9f5b9585933cbbb9e259aeaa642')

if __name__ == '__main__':
    unittest.main()
