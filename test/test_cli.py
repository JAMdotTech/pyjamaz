import json
import unittest
from os import path

from click.testing import CliRunner
from pyjamaz.cli import main


class TestCLI(unittest.TestCase):
    def setUp(self):
        self.runner = CliRunner()
        self.base_dir = path.join(path.dirname(path.abspath(__file__)), 'fixtures', 'cli')

    def test_import_blocks(self):
        result = self.runner.invoke(main, [
            'import-blocks', path.join(self.base_dir, "initial-state.json"), path.join(self.base_dir, "block_data")
        ])
        self.assertIsNone(result.exception)
        self.assertEqual(0, result.exit_code)


if __name__ == '__main__':
    unittest.main()
