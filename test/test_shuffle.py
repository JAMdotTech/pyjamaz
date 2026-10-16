import json
import unittest

from pyjamaz.utils import entropy_shuffle
try:
    from test.vector_fixtures import shuffle_vector_file
except ModuleNotFoundError:  # Direct script execution.
    from vector_fixtures import shuffle_vector_file


class TestShuffle(unittest.TestCase):
    def test_json_testvectors(self):

        with shuffle_vector_file().open() as fixture:
            test_vector = json.load(fixture)

        for item in test_vector:
            output = entropy_shuffle(list(range(int(item["input"]))), bytes.fromhex(item["entropy"]))
            self.assertEqual(item['output'], output, f'{item["input"]} fails')


if __name__ == '__main__':
    unittest.main()
