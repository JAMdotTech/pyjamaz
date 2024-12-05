import json
import os
import unittest
from os import path

from jamcodec.base import JamBytes

from parameterized import parameterized

from pyjamaz.hashing import blake2b_256_hash
from pyjamaz.hostcalls import HostCalls
from pyjamaz.pvm import PVM
from pyjamaz.pvm.codec import PVMProgram
from pyjamaz.storage import InMemoryStorage
from pyjamaz.types import AppType


def load_test_vectors(directory):
    directory = path.join(path.dirname(path.abspath(__file__)), directory)
    test_vectors = []
    if directory.endswith('.json'):
        with open(directory) as f:
            test_vector = json.load(f)
            test_vectors = [(directory, test_vector)]
    else:
        for filename in os.listdir(directory):
            if filename.endswith('.json'):
                with open(os.path.join(directory, filename)) as f:
                    test_vector = json.load(f)
                    test_vectors.append((filename, test_vector))

    return test_vectors

class MockedPyjamazApp(AppType):
    def __init__(self, service_db):
        self.service_db = service_db
        self.hostcalls = HostCalls(self)

    def get_service_db(self):
        return self.service_db

class TestHostcalls(unittest.TestCase):

    def setUp(self):
        self.db = InMemoryStorage()
        self.service_db = self.db.namespace(b'service')
        self.app = MockedPyjamazApp(self.service_db)

    @parameterized.expand(load_test_vectors('fixtures/hostcalls/general_gas.json'))
    def test_gas(self, name, test_vector):
        mem_size = 0
        mem_offset = 0
        pvm_data = PVMProgram.from_jam_bytes(
            JamBytes(bytes(test_vector["program"]))
        )
        pvm = PVM(self.app)
        pvm.invoke(
            pvm_data,
            test_vector["initial-regs"],
            test_vector["initial-pc"],
            test_vector["initial-gas"],
            test_vector["initial-page-map"],
            test_vector["initial-memory"],
            mem_size=mem_size,
            mem_offset=mem_offset
        )

        #self.assertEqual(b'SERVICE-123-TEST-DATA', service_db.get(int.to_bytes(123, byteorder='little', length=1) + preimage_hash))
        #self.assertEqual(test_vector["expected-status"], ExitConditionMap[pvm.status], f"{name}:\n Expected status: {test_vector['expected-status']}, but got: {pvm.status}")
        self.assertEqual(test_vector["expected-regs"], pvm.reg.tolist(), f"{name}:\n Expected registers: {test_vector['expected-regs']}, but got: {pvm.reg.tolist()}")
        self.assertEqual(test_vector["expected-pc"], pvm.pc, f"{name}:\n Expected PC: {test_vector['expected-pc']}, but got: {pvm.pc}")
        self.assertEqual(test_vector["expected-gas"], pvm.gas, f"{name}:\n Expected gas: {test_vector['expected-gas']}, but got: {pvm.gas}")
        self.assertEqual(test_vector["expected-memory"], pvm.mem.tolist(), f"{name}:\n Expected mem: {test_vector['expected-memory']}, but got: {pvm.mem.tolist()}")


    @parameterized.expand(load_test_vectors('fixtures/hostcalls/general_lookup.json'))
    def test_lookup(self, name, test_vector):
        for service_idx, hash in test_vector["preimages"].items():
            preimage_hash = blake2b_256_hash(bytes(hash))
            self.service_db.put(int.to_bytes(int(service_idx), byteorder='little', length=1) + preimage_hash, b'SERVICE-123-TEST-DATA')

        mem_size = 4096
        mem_offset = 0
        pvm_data = PVMProgram.from_jam_bytes(
            JamBytes(bytes(test_vector["program"]))
        )
        pvm = PVM(self.app)
        pvm.invoke(
            pvm_data,
            test_vector["initial-regs"],
            test_vector["initial-pc"],
            test_vector["initial-gas"],
            test_vector["initial-page-map"],
            test_vector["initial-memory"],
            mem_size=mem_size,
            mem_offset=mem_offset
        )

        #self.assertEqual(b'SERVICE-123-TEST-DATA', service_db.get(b'preimage:'+ int.to_bytes(123, byteorder='little', length=1) + preimage_hash))
        #self.assertEqual(test_vector["expected-status"], ExitConditionMap[pvm.status], f"{name}:\n Expected status: {test_vector['expected-status']}, but got: {pvm.status}")
        self.assertEqual(test_vector["expected-regs"], pvm.reg.tolist(), f"{name}:\n Expected registers: {test_vector['expected-regs']}, but got: {pvm.reg.tolist()}")
        self.assertEqual(test_vector["expected-pc"], pvm.pc, f"{name}:\n Expected PC: {test_vector['expected-pc']}, but got: {pvm.pc}")
        self.assertEqual(test_vector["expected-gas"], pvm.gas, f"{name}:\n Expected gas: {test_vector['expected-gas']}, but got: {pvm.gas}")
        self.assertEqual(test_vector["expected-memory"], pvm.mem.tolist(), f"{name}:\n Expected mem: {test_vector['expected-memory']}, but got: {pvm.mem.tolist()}")

    @parameterized.expand(load_test_vectors('fixtures/hostcalls/general_read.json'))
    def test_read(self, name, test_vector):
        for service_idx, hash in test_vector["preimages"].items():
            preimage_hash = blake2b_256_hash(bytes(hash))
            self.service_db.put(int.to_bytes(int(service_idx), byteorder='little', length=1) + preimage_hash, b'SERVICE-123-TEST-DATA')

        mem_size = 27
        mem_offset = 0
        pvm_data = PVMProgram.from_jam_bytes(
            JamBytes(bytes(test_vector["program"]))
        )
        pvm = PVM(self.app)
        pvm.invoke(
            pvm_data,
            test_vector["initial-regs"],
            test_vector["initial-pc"],
            test_vector["initial-gas"],
            test_vector["initial-page-map"],
            test_vector["initial-memory"],
            mem_size=mem_size,
            mem_offset=mem_offset
        )

        #self.assertEqual(b'SERVICE-123-TEST-DATA', service_db.get(int.to_bytes(123, byteorder='little', length=1) + preimage_hash))
        #self.assertEqual(test_vector["expected-status"], ExitConditionMap[pvm.status], f"{name}:\n Expected status: {test_vector['expected-status']}, but got: {pvm.status}")
        self.assertEqual(test_vector["expected-regs"], pvm.reg.tolist(), f"{name}:\n Expected registers: {test_vector['expected-regs']}, but got: {pvm.reg.tolist()}")
        self.assertEqual(test_vector["expected-pc"], pvm.pc, f"{name}:\n Expected PC: {test_vector['expected-pc']}, but got: {pvm.pc}")
        self.assertEqual(test_vector["expected-gas"], pvm.gas, f"{name}:\n Expected gas: {test_vector['expected-gas']}, but got: {pvm.gas}")
        self.assertEqual(test_vector["expected-memory"], pvm.mem.tolist(), f"{name}:\n Expected mem: {test_vector['expected-memory']}, but got: {pvm.mem.tolist()}")

    @parameterized.expand(load_test_vectors('fixtures/hostcalls/general_write_delete.json'))
    def test_write_delete(self, name, test_vector):
        for service_idx, hash in test_vector["preimages"].items():
            preimage_hash = blake2b_256_hash(bytes(hash))
            #self.service_db.put(int.to_bytes(int(service_idx), byteorder='little', length=1) + preimage_hash, b'SERVICE-123-TEST-DATA')
            self.service_db.put(preimage_hash, b'SERVICE-123-TEST-DATA')

        mem_size = 33
        mem_offset = 0
        pvm_data = PVMProgram.from_jam_bytes(
            JamBytes(bytes(test_vector["program"]))
        )
        pvm = PVM(self.app)
        pvm.invoke(
            pvm_data,
            test_vector["initial-regs"],
            test_vector["initial-pc"],
            test_vector["initial-gas"],
            test_vector["initial-page-map"],
            test_vector["initial-memory"],
            mem_size=mem_size,
            mem_offset=mem_offset
        )

        #self.assertEqual(b'SERVICE-123-TEST-DATA', service_db.get(int.to_bytes(123, byteorder='little', length=1) + preimage_hash))
        #self.assertEqual(test_vector["expected-status"], ExitConditionMap[pvm.status], f"{name}:\n Expected status: {test_vector['expected-status']}, but got: {pvm.status}")
        self.assertEqual(test_vector["expected-regs"], pvm.reg.tolist(), f"{name}:\n Expected registers: {test_vector['expected-regs']}, but got: {pvm.reg.tolist()}")
        self.assertEqual(test_vector["expected-pc"], pvm.pc, f"{name}:\n Expected PC: {test_vector['expected-pc']}, but got: {pvm.pc}")
        self.assertEqual(test_vector["expected-gas"], pvm.gas, f"{name}:\n Expected gas: {test_vector['expected-gas']}, but got: {pvm.gas}")
        self.assertEqual(test_vector["expected-memory"], pvm.mem.tolist(), f"{name}:\n Expected mem: {test_vector['expected-memory']}, but got: {pvm.mem.tolist()}")



if __name__ == '__main__':
    unittest.main()
