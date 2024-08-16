import json

import rocksdb3


class StorageInterface:
    def __init__(self):
        pass

    def store(self, key, value):
        raise NotImplementedError

    def retrieve(self, key):
        raise NotImplementedError

    def __enter__(self):
        pass

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass


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
            json.dump(serialized_storage, f, indent=2)

    def retrieve(self, key: bytes) -> bytes:
        return self.storage.get(key)


class RocksDBTransaction:
    def __init__(self, db):
        self.db = db
        self.write_batch = None

    def __enter__(self):
        self.write_batch = rocksdb3.WriterBatch()
        return self

    def store(self, key: bytes, value: bytes):
        self.write_batch.put(key, value)

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            self.db.write(self.write_batch)
            # raise TransactionRolledBack()


class RocksDBStorage(StorageInterface):

    def __init__(self, db_file: str):
        super().__init__()
        self.db = rocksdb3.open_default(db_file)

    def store(self, key: bytes, value: bytes):
        self.db.put(key, value)

    def retrieve(self, key: bytes) -> bytes:
        return self.db.get(key)

    def close(self):
        del self.db

    def transaction(self):
        return RocksDBTransaction(self.db)


# class InMemoryStorage(StorageInterface):
#
#     def __init__(self, state: 'JamState'):
#         super().__init__()
#         self.state = state
#
#     def store(self, key: bytes, value: bytes):
#         self.storage[key] = value
#         with open(self.json_file, 'w') as f:
#             serialized_storage = {f'0x{k.hex()}': f'0x{v.hex()}' for k, v in self.storage.items()}
#             json.dump(serialized_storage, f, indent=2)
#
#     def retrieve(self, key: bytes) -> bytes:
#         return self.storage[key]
