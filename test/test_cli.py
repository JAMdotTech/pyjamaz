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
            'keys', 'generate', '0x0000000000000000000000000000000000000000000000000000000000000000', '127.0.0.1', '9000'
        ])
        self.assertEqual(0, result.exit_code)

        output = json.loads(result.output)
        self.assertEqual('0x4418fb8c85bb3985394a8c2756d3643457ce614546202a2f50b093d762499ace', output['ed25519'])

    async def test_init(self):

        result = await self.runner.invoke(main, [
            'init', '--seed', '0x0000000000000000000000000000000000000000000000000000000000000000','--force-overwrite',
        ])

        self.assertIsNone(result.exception)
        self.assertEqual(0, result.exit_code)


if __name__ == '__main__':
    unittest.main()
