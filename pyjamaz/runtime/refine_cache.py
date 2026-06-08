from dataclasses import dataclass, field
from typing import Any

from pyjamaz.hashing import blake2b_256_hash
from pyjamaz.models.common import WorkPackage


@dataclass
class RefineExecutionCache:
    work_package_hash: bytes
    authorizer_hash: bytes
    payload_hashes: list[bytes]
    export_offsets: list[int]
    preimages: dict[tuple[int, int, bytes], Any] = field(default_factory=dict)
    fetch_blobs: dict[tuple[int, int | None, int, int, int], bytes | None] = field(default_factory=dict)

    @classmethod
    def create(cls, work_package: WorkPackage) -> "RefineExecutionCache":
        export_offsets = []
        offset = 0
        for item in work_package.items:
            export_offsets.append(offset)
            offset += item.export_count

        return cls(
            work_package_hash=work_package.hash(),
            authorizer_hash=work_package.authorizer_hash(),
            payload_hashes=[blake2b_256_hash(item.payload) for item in work_package.items],
            export_offsets=export_offsets,
        )
