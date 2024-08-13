import json
import unittest
from click.testing import CliRunner
from pyjamaz.cli import main


class TestCLI(unittest.TestCase):
    def setUp(self):
        self.runner = CliRunner()

    def test_import_blocks(self):
        result = self.runner.invoke(main, [
            'import-blocks', "./fixtures/cli/initial-state.json", "./fixtures/cli/block_data"
        ])
        self.assertEqual(result.exit_code, 0)
        state = json.loads(result.output)
        self.assertEqual(state["timeslot"]["number"], 2)


if __name__ == '__main__':
    unittest.main()
