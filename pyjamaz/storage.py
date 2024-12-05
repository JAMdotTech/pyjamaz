import json
import os
from typing import Optional

try:
    import rocksdb3
except ImportError:
    rocksdb3 = None

try:
    import plyvel
except ImportError:
    plyvel = None


class TransactionRolledBack(Exception):
    pass


class Transaction:

    def put(self, key: bytes, value: bytes):
        raise NotImplementedError()

    def __enter__(self):
        pass

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass


class StorageEngine:
    def __init__(self):
        pass

    def put(self, key, value):
        raise NotImplementedError

    def get(self, key):
        raise NotImplementedError

    def delete(self, key):
        raise NotImplementedError

    def transaction(self):
        raise NotImplementedError

    def namespace(self, prefix: bytes) -> 'StorageEngine':
        raise NotImplementedError


class InMemoryTransaction(Transaction):
    def __init__(self, storage_engine: 'InMemoryStorage'):

        self.storage_engine = storage_engine

    def __enter__(self):
        return self

    def put(self, key: bytes, value: bytes):
        self.storage_engine.put(key, value)

    def __exit__(self, exc_type, exc_val, exc_tb):
        return


class InMemoryStorage(StorageEngine):

    def __init__(self, storage: Optional[dict] = None, prefix: Optional[bytes] = None):
        super().__init__()
        if storage is None:
            storage = {}
        if prefix is None:
            prefix = bytes()
        self.storage = storage
        self.prefix = prefix

    def put(self, key: bytes, value: bytes):
        self.storage[self.prefix + key] = value

    def get(self, key: bytes) -> bytes:
        return self.storage.get(self.prefix + key)

    def delete(self, key: bytes):
        del self.storage[self.prefix + key]

    def transaction(self) -> InMemoryTransaction:
        return InMemoryTransaction(self)

    def namespace(self, prefix: bytes) -> 'InMemoryStorage':
        return InMemoryStorage(storage=self.storage, prefix=prefix + b'-')


class JSONTransaction(Transaction):
    def __init__(self, json_storage: 'JSONStorage'):

        self.json_storage = json_storage

    def __enter__(self):
        return self

    def put(self, key: bytes, value: bytes):
        self.json_storage.put(key, value)

    def __exit__(self, exc_type, exc_val, exc_tb):
        return


class JSONStorage(StorageEngine):

    def __init__(self, json_file: str):
        super().__init__()
        self.json_file = json_file

        if not os.path.exists(self.json_file):
            # Create the file
            with open(self.json_file, 'w') as file:
                file.write("{}")

        with open(self.json_file, 'r') as f:
            storage = json.load(f)

            self.storage = {bytes.fromhex(k[2:]): bytes.fromhex(v[2:]) for k, v in storage.items()}

    def put(self, key: bytes, value: bytes):
        self.storage[key] = value
        with open(self.json_file, 'w') as f:
            serialized_storage = {f'0x{k.hex()}': f'0x{v.hex()}' for k, v in self.storage.items()}
            json.dump(serialized_storage, f, indent=2)

    def get(self, key: bytes) -> bytes:
        return self.storage.get(key)

    def delete(self, key: bytes):
        del self.storage[key]

    def transaction(self) -> JSONTransaction:
        return JSONTransaction(self)


class RocksDBTransaction(Transaction):
    def __init__(self, db):

        if rocksdb3 is None:
            raise ImportError('rocksdb3 not installed')

        self.db = db
        self.write_batch = None

    def __enter__(self):
        self.write_batch = rocksdb3.WriterBatch()
        return self

    def put(self, key: bytes, value: bytes):
        self.write_batch.put(key, value)

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            self.db.write(self.write_batch)
        else:
            raise TransactionRolledBack(exc_val)


class RocksDBStorage(StorageEngine):

    def __init__(self, db_file: str):
        if rocksdb3 is None:
            raise ImportError('rocksdb3 not installed')

        super().__init__()
        self.db = rocksdb3.open_default(db_file)

    def put(self, key: bytes, value: bytes):
        self.db.put(key, value)

    def get(self, key: bytes) -> bytes:
        return self.db.get(key)

    def delete(self, key: bytes):
        return self.db.delete(key)

    def close(self):
        del self.db

    def transaction(self) -> RocksDBTransaction:
        return RocksDBTransaction(self.db)


class LevelDBTransaction(Transaction):
    def __init__(self, db):

        if plyvel is None:
            raise ImportError('plyvel not installed')

        self.db = db
        self.write_batch = None

    def __enter__(self):
        self.write_batch = self.db.write_batch(transaction=True)
        return self

    def put(self, key: bytes, value: bytes):
        self.write_batch.put(key, value)

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            self.write_batch.write()
        else:
            raise TransactionRolledBack(exc_val)


class LevelDBStorage(StorageEngine):

    def __init__(self, db):
        super().__init__()
        self.db = db

    @classmethod
    def create_from_file(cls, db_file: str):
        if plyvel is None:
            raise ImportError('plyvel not installed')
        db = plyvel.DB(db_file, create_if_missing=True)
        return cls(db=db)

    def put(self, key: bytes, value: bytes):
        self.db.put(key, value)

    def get(self, key: bytes) -> bytes:
        return self.db.get(key)

    def delete(self, key: bytes):
        return self.db.delete(key)

    def close(self):
        self.db.close()

    def transaction(self) -> LevelDBTransaction:
        return LevelDBTransaction(self.db)

    def namespace(self, prefix: bytes) -> 'LevelDBStorage':
        return LevelDBStorage(db=self.db.prefixed_db(prefix + b'-'))
