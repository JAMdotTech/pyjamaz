from typing import Optional

from jamcodec.base import JamBytes

try:
    import rocksdict
except ImportError:
    rocksdict = None

class TransactionRolledBack(Exception):
    pass


class Transaction:

    def put(self, key: bytes, value: bytes):
        raise NotImplementedError()

    def delete(self, key: bytes):
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

    def dump_to_jam_bytes(self) -> JamBytes:
        raise NotImplementedError

    def as_list(self):
        raise NotImplementedError

    def as_dict(self) -> dict:
        raise NotImplementedError

    def close(self):
        raise NotImplementedError

    def destroy(self):
        raise NotImplementedError


class InMemoryTransaction(Transaction):
    def __init__(self, storage_engine: 'InMemoryStorage'):
        self.tx_storage = {}
        self.storage_engine = storage_engine

    def __enter__(self):
        self.tx_storage = {}
        return self

    def put(self, key: bytes, value: bytes):
        self.tx_storage[key] = value

    def delete(self, key: bytes):
        self.tx_storage[key] = None

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            # Commit changes
            for key, value in self.tx_storage.items():
                if value is None:
                    self.storage_engine.delete(key)
                else:
                    self.storage_engine.put(key, value)
        else:
            # Discard changes
            raise exc_val


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
        self.storage.pop(self.prefix + key, None)

    def transaction(self) -> InMemoryTransaction:
        return InMemoryTransaction(self)

    def namespace(self, prefix: bytes) -> 'InMemoryStorage':
        return InMemoryStorage(storage=self.storage, prefix=prefix + b'-')

    def as_list(self):
        return [(k[len(self.prefix):], v) for k, v in self.storage.items() if k.startswith(self.prefix)]

    def as_dict(self) -> dict:
        return {k[len(self.prefix):]: v for k, v in self.storage.items() if k.startswith(self.prefix)}

    def close(self):
        pass

    def destroy(self):
        self.storage = {}


class RocksDBTransaction(Transaction):
    def __init__(self, db, column_family):

        self.db = db
        self.column_family = column_family
        self.write_batch = None

    def __enter__(self):
        self.write_batch = rocksdict.WriteBatch(raw_mode=True)
        return self

    def put(self, key: bytes, value: bytes):
        self.write_batch.put(key, value, self.column_family)

    def delete(self, key: bytes):
        self.write_batch.delete(key, self.column_family)

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            self.db.write(self.write_batch)
        else:
            raise exc_val


class RocksDBStorage(StorageEngine):

    def __init__(self, db, db_path, namespace: Optional[str] = None):
        super().__init__()
        self.db = db
        self.db_path = db_path

        if namespace is not None:
            self.column_family = db.get_column_family_handle(namespace)
        else:
            self.column_family = None

    @classmethod
    def create_from_file(cls, db_path: str) -> 'RocksDBStorage':
        if rocksdict is None:
            raise ImportError('rocksdict not installed')

        opts = rocksdict.Options(raw_mode=True)
        opts.create_if_missing(True)
        opts.create_missing_column_families(True)

        db = rocksdict.Rdict(db_path, opts)

        return cls(db=db, db_path=db_path)

    def put(self, key: bytes, value: bytes):
        self.db[key] = value

    def get(self, key: bytes) -> bytes:
        return self.db.get(key)

    def delete(self, key: bytes):
        return self.db.delete(key)

    def close(self):
        self.db.close()

    def destroy(self):
        rocksdict.Rdict.destroy(self.db_path)

    def transaction(self) -> RocksDBTransaction:
        return RocksDBTransaction(self.db, self.column_family)

    def namespace(self, prefix: bytes) -> 'RocksDBStorage':
        # Create/open CFs for your namespaces
        prefix = prefix.decode('utf-8')
        try:
            cf_opts = rocksdict.Options(raw_mode=True)
            cf_opts.set_prefix_extractor(rocksdict.SliceTransform.create_fixed_prefix(3))
            self.db.create_column_family(prefix, cf_opts)
        except Exception:
            pass  # already exists

        return RocksDBStorage(self.db.get_column_family(prefix), self.db_path, namespace=prefix)

    def as_list(self):
        return self.as_dict().items()

    def as_dict(self):
        return dict(self.db)
