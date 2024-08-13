import json
import unittest

from pyjamaz.merkle import merkle


# class TestMerkleTrie(unittest.TestCase):
#     def test_json_testvectors(self):
#         with open('./fixtures/trie.json') as f:
#             test_vector = json.load(f)
#
#         for item in test_vector:
#             output = merkle(item['input'])
#             self.assertEqual(item['output'], output.hex())


if __name__ == '__main__':
    unittest.main()
