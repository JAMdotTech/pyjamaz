import json
import os

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

    def store(self, key: bytes, value: bytes):
        raise NotImplementedError()

    def __enter__(self):
        pass

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass


class StorageInterface:
    def __init__(self):
        pass

    def store(self, key, value):
        raise NotImplementedError

    def retrieve(self, key):
        raise NotImplementedError

    def transaction(self):
        raise NotImplementedError


class InMemoryTransaction(Transaction):
    def __init__(self, storage_engine: 'InMemoryStorage'):

        self.storage_engine = storage_engine

    def __enter__(self):
        return self

    def store(self, key: bytes, value: bytes):
        self.storage_engine.store(key, value)

    def __exit__(self, exc_type, exc_val, exc_tb):
        return


class InMemoryStorage(StorageInterface):

    def __init__(self):
        super().__init__()
        self.storage = {}

    def store(self, key: bytes, value: bytes):
        self.storage[key] = value

    def retrieve(self, key: bytes) -> bytes:
        return self.storage.get(key)

    def transaction(self) -> InMemoryTransaction:
        return InMemoryTransaction(self)


class JSONTransaction(Transaction):
    def __init__(self, json_storage: 'JSONStorage'):

        self.json_storage = json_storage

    def __enter__(self):
        return self

    def store(self, key: bytes, value: bytes):
        self.json_storage.store(key, value)

    def __exit__(self, exc_type, exc_val, exc_tb):
        return


class JSONStorage(StorageInterface):

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

    def store(self, key: bytes, value: bytes):
        self.storage[key] = value
        with open(self.json_file, 'w') as f:
            serialized_storage = {f'0x{k.hex()}': f'0x{v.hex()}' for k, v in self.storage.items()}
            json.dump(serialized_storage, f, indent=2)

    def retrieve(self, key: bytes) -> bytes:
        return self.storage.get(key)

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

    def store(self, key: bytes, value: bytes):
        self.write_batch.put(key, value)

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            self.db.write(self.write_batch)
        else:
            raise TransactionRolledBack(exc_val)


class RocksDBStorage(StorageInterface):

    def __init__(self, db_file: str):
        if rocksdb3 is None:
            raise ImportError('rocksdb3 not installed')

        super().__init__()
        self.db = rocksdb3.open_default(db_file)

    def store(self, key: bytes, value: bytes):
        self.db.put(key, value)

    def retrieve(self, key: bytes) -> bytes:
        return self.db.get(key)

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

    def store(self, key: bytes, value: bytes):
        self.write_batch.put(key, value)

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            self.write_batch.write()
        else:
            raise TransactionRolledBack(exc_val)


class LevelDBStorage(StorageInterface):

    def __init__(self, db_file: str):
        if plyvel is None:
            raise ImportError('plyvel not installed')

        super().__init__()
        self.db = plyvel.DB(db_file, create_if_missing=True)

    def store(self, key: bytes, value: bytes):
        self.db.put(key, value)

    def retrieve(self, key: bytes) -> bytes:
        return self.db.get(key)

    def close(self):
        self.db.close()

    def transaction(self) -> LevelDBTransaction:
        return LevelDBTransaction(self.db)
