import unittest
from os import path

from pyjamaz.models.state import TimeslotState
from pyjamaz.state.components import Timeslot
from pyjamaz.storage import LevelDBStorage, InMemoryStorage


class TestLevelDBStorage(unittest.TestCase):

    def setUp(self):
        data_dir = path.join(path.dirname(path.abspath(__file__)), '..', 'data')
        db_path = path.join(data_dir, 'db')

        self.storage = LevelDBStorage.create_from_file(db_path)

    def test_state_storage(self):

        timeslot = Timeslot(storage_engine=self.storage)

        timeslot_state = TimeslotState(number=4)

        timeslot.store_state(timeslot_state)

        retrieved_state = timeslot.retrieve_state()

        self.assertEqual(timeslot_state, retrieved_state)

    def test_namespaces(self):
        state_db = self.storage.namespace(b'state')
        block_db = self.storage.namespace(b'block')

        state_db.put(b'test', b'state')
        block_db.put(b'test', b'block')

        self.assertEqual(b'state', state_db.get(b'test'))
        self.assertEqual(b'block', block_db.get(b'test'))


class TestInMemoryStorage(TestLevelDBStorage):

    def setUp(self):
        self.storage = InMemoryStorage()


if __name__ == '__main__':
    unittest.main()
