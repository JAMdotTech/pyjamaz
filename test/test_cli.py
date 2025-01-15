import json
import os
import unittest
from os import path

from asyncclick.testing import CliRunner
from pyjamaz.cli import main


class TestCLI(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.runner = CliRunner()
        self.base_dir = path.join(path.dirname(path.abspath(__file__)), 'fixtures', 'cli')

    # TODO cover more CLI features
    async def test_generate_keys(self):

        result = await self.runner.invoke(main, [
            'keys', 'generate', '0x0000000000000000000000000000000000000000000000000000000000000000'
        ])

        self.assertIsNone(result.exception)
        self.assertEqual(0, result.exit_code)

        output = json.loads(result.output)
        self.assertEqual('0x3b6a27bcceb6a42d62a3a8d02a6f0d73653215771de243a63ac048a18b59da29', output['ed25519'])

    async def test_init(self):

        result = await self.runner.invoke(main, [
            'init', '--initial-state', path.join(path.dirname(path.abspath(__file__)), '..', 'pyjamaz', 'data', 'initial_state_template.json'), '--force-overwrite',
        ])

        self.assertIsNone(result.exception)
        self.assertEqual(0, result.exit_code)


if __name__ == '__main__':
    unittest.main()
