"""Bounded canonical sequences used by GP 0.8.0 protocol values."""

from jamcodec.mixins import Serializable
from jamcodec.types import Struct, U8, Vec, VarInt64


class TaggedStruct(Struct):
    """A fixed discriminator followed by a struct's canonical fields."""

    def __init__(self, tag: int, **fields):
        super().__init__(**fields)
        self.tag = tag

    def decode(self, data):
        if U8.decode(data) != self.tag:
            raise ValueError("invalid struct discriminator")
        return super().decode(data)

    def encode(self, value):
        return U8.encode(self.tag) + super().encode(value)


class TaggedSerializable(Serializable):
    """Expose both the tagged value and its payload for an enclosing enum."""

    @classmethod
    def to_payload_codec_def(cls):
        return super().to_codec_def()

    @classmethod
    def to_codec_def(cls):
        codec = cls.__dict__.get('_tagged_codec_def')
        if codec is None:
            codec = TaggedStruct(cls._codec_tag, **cls.to_payload_codec_def().arguments)
            codec._deserialize_type = cls
            cls._tagged_codec_def = codec
        return codec


class BoundedVec(Vec):
    """Check peer-controlled cardinality before decoding any element."""

    def __init__(self, type_def, maximum: int, minimum: int = 0, multiple: int = 1):
        super().__init__(type_def)
        self.maximum = maximum
        self.minimum = minimum
        self.multiple = multiple

    def _check_count(self, count: int) -> None:
        if not self.minimum <= count <= self.maximum or count % self.multiple:
            raise ValueError(
                f"invalid sequence length {count}: expected {self.minimum}.."
                f"{self.maximum} in multiples of {self.multiple}"
            )

    def decode(self, data):
        start = data.offset
        count = VarInt64.decode(data)
        if bytes(data.data[start:data.offset]) != bytes(VarInt64.encode(count)):
            raise ValueError("non-canonical sequence length")
        self._check_count(count)
        values = []
        for _ in range(count):
            item = self.type_def.new()
            item.decode(data)
            values.append(item)
        return values

    def encode(self, value):
        self._check_count(len(value))
        return super().encode(value)

    def deserialize(self, value):
        self._check_count(len(value))
        return super().deserialize(value)
