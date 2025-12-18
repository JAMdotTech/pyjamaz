import shutil
import unittest
from os import path, makedirs

from pyjamaz.models.state import TimeslotState
from pyjamaz.models.context import AppContext, BlockContext
from pyjamaz.state.components import Timeslot
from pyjamaz.state.storage import StateStorage
from pyjamaz.storage import RocksDBStorageEngine, InMemoryStorageEngine, TransactionRolledBack


class TestRocksDBStorage(unittest.IsolatedAsyncioTestCase):

    @classmethod
    def setUpClass(cls):
        db_path = path.join(path.dirname(path.abspath(__file__)), '..', 'data', 'testdb')
        makedirs(db_path, exist_ok=True)
        shutil.rmtree(db_path)  # Clear DB
        cls.storage = RocksDBStorageEngine.create_from_file(db_path)

    def setUp(self):
        # Flush DB
        for key, _ in self.storage.namespace(b'state').as_list():
            self.storage.delete(key)

        for key, _ in self.storage.namespace(b'block').as_list():
            self.storage.delete(key)

    async def test_state_storage(self):

        app_context = AppContext(state_storage=StateStorage(self.storage))

        timeslot = Timeslot(block_context=BlockContext(), app_context=app_context)

        timeslot_state = TimeslotState(number=4)

        await timeslot.store_state(timeslot_state)

        retrieved_state = timeslot.retrieve_state()

        self.assertEqual(timeslot_state, retrieved_state)

    def test_namespaces(self):
        state_db = self.storage.namespace(b'state')
        block_db = self.storage.namespace(b'block')

        state_db.put(b'test', b'state')
        block_db.put(b'test', b'block')

        self.assertEqual(b'state', state_db.get(b'test'))
        self.assertEqual(b'block', block_db.get(b'test'))

    def test_iter(self):
        state_db = self.storage.namespace(b'state')
        block_db = self.storage.namespace(b'block')

        state_db.put(b'test', b'state')
        state_db.put(b'test2', b'state2')
        state_db.put(b'test3', b'state3')
        block_db.put(b'test4', b'state4')

        all_items = state_db.as_list()

        self.assertEqual(len(all_items), 3)

    def test_transaction(self):
        tx_db = self.storage.namespace(b'tx')

        tx_db.put(b'test', b'initial')

        try:

            with tx_db.transaction() as tx:
                tx.put(b'test', b'changed')
                raise ValueError("Should rollback")
        except ValueError:
            pass

        self.assertEqual(b'initial', tx_db.get(b'test'))



class TestInMemoryStorage(TestRocksDBStorage):

    @classmethod
    def setUpClass(cls):
        cls.storage = InMemoryStorageEngine()


if __name__ == '__main__':
    unittest.main()
