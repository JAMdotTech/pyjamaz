import unittest

from pyjamaz.state.storage import StateStorage
from pyjamaz.storage import InMemoryStorageEngine, RocksDBStorageEngine


class TestForks(unittest.TestCase):


    def tearDown(self):
        self.storage.close()
        self.storage.destroy()

    def setUp(self):
        self.storage = InMemoryStorageEngine()
        # self.storage = RocksDBStorage.create_from_file('/tmp/forks_db')

        self.state = StateStorage(self.storage)
        self.state.put(b'timeslot', b'0')
        self.state.put(b'nochange', b'test')
        self.state.set_finalized_block_hash(b'\x00' * 32)



    def test_no_change_set(self):
        self.state.set_block_hash(b'\x01' * 32, b'\x00' * 32)
        self.assertEqual(self.state.get(b'timeslot'), b'0')

        self.state.set_block_hash(b'\x02' * 32, b'\x01' * 32)

        self.assertEqual(self.state.get(b'timeslot'), b'0')

    def test_in_change_set(self):

        self.state.set_block_hash(b'\x01' * 32, b'\x00' * 32)
        self.assertEqual(self.state.get(b'timeslot'), b'0')

        self.state.set_block_hash(b'\x02' * 32, b'\x01' * 32)

        self.state.put(b'timeslot', b'1')
        self.state.commit()

        self.assertEqual(self.state.get(b'timeslot'), b'1')
        self.assertEqual(self.state.get(b'nochange'), b'test')

        self.state.set_block_hash(b'\x03' * 32, b'\x02' * 32)

        self.assertEqual(self.state.get(b'timeslot'), b'1')
        self.assertEqual(self.state.get(b'nochange'), b'test')



    def test_simple_fork(self):
        """
        timeslot

        1 (1) -> 2 (2)
        1 (1) -> 3 (3)

        balance

        1 (100) -> 2 (200)
        1 (100) -> 3 No change -> 4 (delete)


        """
        self.state.set_block_hash(b'\x01' * 32, b'\x00' * 32)
        self.state.put(b'timeslot', b'1')
        self.state.put(b'balance', b'100')
        self.state.commit()

        # Update from 1
        self.state.set_block_hash(b'\x02' * 32, b'\x01' * 32)
        self.state.put(b'timeslot', b'2')
        self.state.put(b'balance', b'200')

        self.assertEqual(self.state.get(b'timeslot'), b'2')
        self.assertEqual(self.state.get(b'balance'), b'200')
        self.assertEqual(self.state.get(b'nochange'), b'test')
        self.state.commit()

        self.state.set_block_hash(b'\x03' * 32, b'\x01' * 32)
        self.state.put(b'timeslot', b'3')
        self.state.commit()

        self.assertEqual(self.state.get(b'timeslot'), b'3')
        self.assertEqual(self.state.get(b'balance'), b'100')
        self.assertEqual(self.state.get(b'nochange'), b'test')

        # Delete item

        self.state.set_block_hash(b'\x04' * 32, b'\x03' * 32)
        self.state.delete(b'balance')
        self.state.commit()
        self.assertEqual(self.state.get(b'balance'), None)

        # Rollback
        self.state.set_block_hash(b'\x03' * 32, b'\x01' * 32)
        self.assertEqual(self.state.get(b'balance'), b'100')

    def test_state_retrieval(self):
        # initial state
        self.assertEqual([(b'nochange', b'test'), (b'timeslot', b'0')], self.state.as_list())

        self.state.set_block_hash(b'\x01' * 32, b'\x00' * 32)

        self.assertEqual([(b'nochange', b'test'), (b'timeslot', b'0')], self.state.as_list())

        self.state.put(b'timeslot', b'1')
        self.state.put(b'balance', b'100')
        self.state.put(b'added', b'new')
        self.state.commit()

        self.assertListEqual([
            (b'added', b'new'), (b'balance', b'100'), (b'nochange', b'test'), (b'timeslot', b'1')
        ], self.state.as_list())

        self.state.set_block_hash(b'\x04' * 32, b'\x01' * 32)

        self.state.put(b'timeslot', b'4')
        self.state.delete(b'balance')
        self.state.put(b'added_by_4', b'new')
        self.state.commit()

        self.assertListEqual(
            [
                (b'added', b'new'), (b'added_by_4', b'new'), (b'nochange', b'test'), (b'timeslot', b'4')
            ], self.state.as_list()
        )

    def test_state_root(self):
        self.assertEqual(
            '7dba3b398d4997c87bb4dca4f1582c0002be813792015fffab08c2dbfa7abcef', self.state.state_root().hex()
        )
        self.state.set_block_hash(b'\x01' * 32, b'\x00' * 32)

        self.assertEqual(
            '7dba3b398d4997c87bb4dca4f1582c0002be813792015fffab08c2dbfa7abcef', self.state.state_root().hex()
        )

        self.state.set_block_hash(b'\x02' * 32, b'\x01' * 32)

        self.state.put(b'timeslot', b'2')
        self.state.delete(b'nochange')
        self.state.commit()

        self.assertEqual(
            '6c5e9a10ce89ff0a991b4e3b866de303d3e244e329270c5bd4f0942ec8880966', self.state.state_root().hex()
        )

        self.state.set_block_hash(b'\x03' * 32, b'\x01' * 32)

        self.assertEqual(
            '7dba3b398d4997c87bb4dca4f1582c0002be813792015fffab08c2dbfa7abcef', self.state.state_root().hex()
        )

        self.state.set_block_hash(b'\x04' * 32, b'\x02' * 32)

        self.assertEqual(
            '6c5e9a10ce89ff0a991b4e3b866de303d3e244e329270c5bd4f0942ec8880966', self.state.state_root().hex()
        )

        self.state.put(b'timeslot', b'0')
        self.state.put(b'nochange', b'test')
        self.state.commit()

        self.assertEqual(
            '7dba3b398d4997c87bb4dca4f1582c0002be813792015fffab08c2dbfa7abcef', self.state.state_root().hex()
        )

    def test_finalize(self):

        self.state.set_block_hash(b'\x01' * 32, b'\x00' * 32)
        self.state.put(b'timeslot', b'1')
        self.state.commit()

        self.assertEqual(self.state.get(b'timeslot'), b'1')

        self.assertEqual(self.state.get_finalized(b'timeslot'), b'0')

        self.state.set_block_hash(b'\x02' * 32, b'\x01' * 32)

        self.state.put(b'timeslot', b'2')
        self.state.delete(b'nochange')
        self.state.commit()

        self.state.finalize(b'\x01' * 32)

        self.assertEqual(self.state.get(b'timeslot'), b'2')
        self.assertEqual(self.state.get(b'nochange'), None)

        self.assertEqual(self.state.get_finalized(b'timeslot'), b'1')
        self.assertEqual(self.state.get_finalized(b'nochange'), b'test')

        self.state.set_block_hash(b'\x03' * 32, b'\x02' * 32)
        self.state.put(b'nochange', b'3')
        self.state.commit()
        self.state.set_block_hash(b'\x04' * 32, b'\x03' * 32)
        self.state.put(b'nochange', b'4')
        self.state.commit()

        self.state.finalize(b'\x02' * 32)

        self.assertEqual(self.state.get(b'nochange'), b'4')

        self.assertEqual(self.state.get_finalized(b'timeslot'), b'2')
        self.assertEqual(self.state.get_finalized(b'nochange'), None)

        self.state.finalize(b'\x04' * 32)

        self.assertEqual(self.state.get_finalized(b'nochange'), b'4')

    def test_invalid_finalize(self):
        self.state.set_block_hash(b'\x01' * 32, b'\x00' * 32)
        self.state.set_block_hash(b'\x02' * 32, b'\x01' * 32)
        self.state.put(b'timeslot', b'1')
        self.state.commit()

        self.state.set_block_hash(b'\x03' * 32, b'\x01' * 32)
        self.state.put(b'timeslot', b'1')
        self.state.commit()

        self.state.finalize(b'\x02' * 32)

        with self.assertRaises(ValueError):
            self.state.set_block_hash(b'\x04' * 32, b'\x01' * 32)

    def test_rollback(self):
        self.state.set_block_hash(b'\x01' * 32, b'\x00' * 32)

        self.state.set_block_hash(b'\x01' * 32, b'\x00' * 32)
        self.state.put(b'timeslot', b'1')
        self.assertEqual(b'1', self.state.get(b'timeslot'))

        self.state.rollback()
        self.assertEqual(b'0', self.state.get(b'timeslot'))


if __name__ == '__main__':
    unittest.main()
