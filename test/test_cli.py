import unittest
from click.testing import CliRunner
from pyjamaz.cli import main


class TestCLI(unittest.TestCase):
    def setUp(self):
        self.runner = CliRunner()

    def test_import_block_cmd(self):
        result = self.runner.invoke(main, ['import-block-cmd', '{"block": "data"}'])
        self.assertIn("Block imported successfully.", result.output)

    def test_init_state(self):
        result = self.runner.invoke(main, ['init-state'])
        self.assertIn("State initialized.", result.output)

    def test_transition(self):
        result = self.runner.invoke(main, ['transition', '{"block": "data"}'])
        self.assertIn("State transitioned successfully.", result.output)


if __name__ == '__main__':
    unittest.main()
