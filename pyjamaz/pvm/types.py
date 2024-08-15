from dataclasses import dataclass, field
from typing import List, Union

from pyjamaz.mixins import SerializableMixin
from scalecodec.base import ScaleBytes
from scalecodec.types import U8, Array, SignedInteger, Vec, U32


@dataclass
class Program(SerializableMixin):
    jump_table: List[int]
    code: bytes
    checksum: int

    @classmethod
    def deserialize(cls, data: Union[bytes, list]) -> 'Program':
        if type(data) is list:
            data = bytes(data)

        return cls.from_scale_bytes(ScaleBytes(data))

    @classmethod
    def from_scale_bytes(cls, scale_bytes: ScaleBytes) -> 'Program':
        jump_table_entry_count = U8.decode(scale_bytes)  # TODO convert to varint
        jump_table_entry_size = U8.decode(scale_bytes)
        code_length = U8.decode(scale_bytes)  # TODO convert to varint
        jump_table = []
        if jump_table_entry_size > 0:
            jump_table = Array(
                SignedInteger(bits=jump_table_entry_size), jump_table_entry_count
            ).decode(scale_bytes)
        code = Array(U8, code_length).decode(scale_bytes)
        checksum = U8.decode(scale_bytes)

        return Program(
            jump_table=jump_table,
            code=code,
            checksum=checksum
        )

    def to_scale_bytes(self) -> ScaleBytes:
        data = U8.new().encode(len(self.jump_table))
        data += U8.new().encode(0)  # TODO Hard coded to U32
        data += U8.new().encode(len(self.code))  # TODO Hard coded to U32
        if len(self.jump_table) > 0:
            data += self.jump_table
        data += self.code
        data += U8.new().encode(self.checksum)

        return data

    def serialize(self) -> List[int]:
        return [b for b in self.to_scale_bytes().to_bytes()]
