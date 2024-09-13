from dataclasses import dataclass, field
from typing import List, Union

#from scalecodec.base import ScaleBytes
#from scalecodec.types import U8, Array, SignedInteger, Vec, U32

from pyjamaz.serialization import VarInt64, Serializable


@dataclass
class PVMProgram(Serializable):
    jump_table_entry_count: int = field(metadata={'length': 'varint'})
    jump_table_entry_size: int = field(metadata={'length': 1})
    code_length: int = field(metadata={'length': 'varint'})
    jump_table: List[int] = field(metadata={'size': jump_table_entry_count, 'length': jump_table_entry_size})
    code: bytes = field(metadata={'length': code_length})
    bitmask: bytes = field(metadata={'length': 'remaining'})

#TODO: scalecodec / serializers strictly typed & performant maken met numpy: https://stackoverflow.com/a/38155077
# @dataclass
# class PVMProgram(Serializable):
#     jump_table: List[int]
#     code: bytes
#     checksum: int
#
#     @classmethod
#     def deserialize(cls, data: Union[bytes, list]) -> 'PVMProgram':
#         if type(data) is list:
#             data = bytes(data)
#
#         return cls.from_scale_bytes(ScaleBytes(data))
#
#     @classmethod
#     def from_scale_bytes(cls, scale_bytes: ScaleBytes) -> 'PVMProgram':
#         jump_table_entry_count = VarInt64.from_scale_bytes(scale_bytes)
#         jump_table_entry_size = U8.decode(scale_bytes)
#         code_length = VarInt64.from_scale_bytes(scale_bytes)
#         jump_table = []
#         if jump_table_entry_size > 0:
#             jump_table = Array(
#                 SignedInteger(bits=jump_table_entry_size), jump_table_entry_count
#             ).decode(scale_bytes)
#         code = Array(U8, code_length).decode(scale_bytes)
#         checksum = U8.decode(scale_bytes) #TODO: is dit altijd een u8? of varint?
#
#         return PVMProgram(
#             jump_table=jump_table,
#             code=code,
#             checksum=checksum
#         )
#
#     def to_scale_bytes(self) -> ScaleBytes:
#         data = VarInt64().new().encode(len(self.jump_table))
#         data += U8.new().encode(0)  # TODO Hard coded to U32
#         data += VarInt64().new().encode(len(self.code))  # TODO Hard coded to U32
#         if len(self.jump_table) > 0:
#             data += self.jump_table
#         data += self.code
#         data += U8.new().encode(self.checksum)
#
#         return data
#
#     def serialize(self) -> List[int]:
#         return [b for b in self.to_scale_bytes().to_bytes()]
