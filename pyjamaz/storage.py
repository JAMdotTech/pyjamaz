import json


class StorageInterface:
    def __init__(self):
        pass

    def store(self, key, value):
        raise NotImplementedError

    def retrieve(self, key):
        raise NotImplementedError


class JSONStorage(StorageInterface):

    def __init__(self, json_file: str):
        super().__init__()
        self.json_file = json_file
        with open(self.json_file, 'r') as f:
            storage = json.load(f)

            self.storage = {bytes.fromhex(k[2:]): bytes.fromhex(v[2:]) for k, v in storage.items()}

    def store(self, key: bytes, value: bytes):
        self.storage[key] = value
        with open(self.json_file, 'w') as f:
            serialized_storage = {f'0x{k.hex()}': f'0x{v.hex()}' for k, v in self.storage.items()}
            json.dump(serialized_storage, f)

    def retrieve(self, key: bytes) -> bytes:
        return self.storage[key]
