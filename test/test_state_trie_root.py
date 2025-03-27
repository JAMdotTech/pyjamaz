import unittest
from os import path

from jamcodec.base import JamBytes
from jamcodec.types import Vec, Tuple, H256, Bytes

from pyjamaz.app import PyjamazApp, AppConfig
from pyjamaz.graypaper_constants import COMMON_ERA

from pyjamaz.storage import InMemoryStorage


class TestStateRoot(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        # Set up ring data
        data_dir = path.join(path.dirname(path.abspath(__file__)), '..', 'pyjamaz', 'data')
        with open(path.join(data_dir, 'zcash-srs-2-11-uncompressed.bin'), 'rb') as fp:
            ring_data = fp.read()

        self.config = AppConfig(
            ring_data=ring_data,
            storage_engine=InMemoryStorage(),
            common_era=COMMON_ERA
        )

    async def test_state_trie_root(self):
        # Initialize app
        app = PyjamazApp(config=self.config)

        # Write initial state to DB
        with open(path.join(path.dirname(path.abspath(__file__)), 'fixtures', 'state_trie', 'genesis.bin'), 'rb') as fp:
            data = fp.read()
            genesis_data = Vec(Tuple(H256, Bytes)).new(scale=JamBytes(data))
            for k, v in genesis_data:
                app.state_db.put(bytes(k.value_object), bytes(v.value_object))

        # Calculate state trie
        await app.update_state_trie()

        self.assertEqual(
            "798dcc9482ea19920f2586a2e72324a1af2891460bbde74f163f7c0ee62bf96b", app.state_trie_root.hex()
        )


if __name__ == '__main__':
    unittest.main()
