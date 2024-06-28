import unittest

from client.storage import JSONStorage
from constants import WELL_KNOWN_STORAGE_KEYS
from models.state.timeslot import Timeslot


class TestStorageValue(unittest.TestCase):
    def test_timeslot_value(self):

        timeslot = Timeslot().new()
        timeslot.deserialize({'timeslot': 4})

        data = timeslot.encode()

        self.assertEqual(bytearray(b'\x04\x00\x00\x00'), data.data)

        storage = JSONStorage('../data/storage.json')

        storage.store(WELL_KNOWN_STORAGE_KEYS[11], data.data)

        timeslot.storage_deserialize(data.data)

        self.assertEqual(timeslot.value['timeslot'], 4)






if __name__ == '__main__':
    unittest.main()
