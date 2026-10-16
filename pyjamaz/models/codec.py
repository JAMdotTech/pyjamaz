"""Tagged codecs used by GP 0.8.0 protocol values."""

from jamcodec.mixins import Serializable
from jamcodec.types import Struct, U8


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
