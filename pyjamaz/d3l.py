from jamcodec.base import JamBytes
from pyjamaz.models.app import D3LEntry
from pyjamaz.storage import StorageEngine


class DataAvailabilityStore:

    def __init__(self, storage_engine: StorageEngine):
        self.storage_engine = storage_engine

    def retrieve_segments(self, segment_root: bytes) -> D3LEntry:
        data = self.storage_engine.get(segment_root)
        d3l_item = D3LEntry.from_jam_bytes(JamBytes(data))
        return d3l_item

    def store_segments(self, segments: D3LEntry):
        self.storage_engine.put(segments.segment_root, segments.to_jam_bytes().to_bytes())


