import dataclasses
import enum
import json
import math
from dataclasses import is_dataclass
from typing import Type, TypeVar, Union
import typing


T = TypeVar('T')


class NoMoreBytesAvailable(Exception):
    pass


class SerializationException(Exception):
    pass


class JamBytes:
    """
    Representation of SCALE encoded Bytes.
    """

    def __init__(self, data: Union[str, bytes, bytearray, int]):
        """
        Constructs a SCALE bytes-stream with provided `data`

        Parameters
        ----------
        data
        """
        self.offset = 0

        if type(data) is bytearray:
            self.data = data
        elif type(data) is bytes:
            self.data = bytearray(data)
        elif type(data) is str and data[0:2] == '0x':
            self.data = bytearray.fromhex(data[2:])
        else:
            raise ValueError("Provided data is not in supported format: provided '{}'".format(type(data)))

        self.length = len(self.data)

    def get_next_bytes(self, length: int) -> bytearray:
        """
        Retrieve `length` amount of bytes of the stream

        Parameters
        ----------
        length: amount of requested bytes

        Returns
        -------
        bytearray
        """
        if self.offset + length > self.length:
            raise NoMoreBytesAvailable(
                f'No more bytes available (needed: {self.offset + length} / total: {self.length})'
            )

        data = self.data[self.offset:self.offset + length]
        self.offset += length
        return data

    def get_remaining_bytes(self) -> bytearray:
        """
        Retrieves all remaining bytes from the stream

        Returns
        -------
        bytearray
        """

        data = self.data[self.offset:]
        self.offset = self.length
        return data

    def get_remaining_length(self) -> int:
        """
        Returns how many bytes are left in the stream

        Returns
        -------
        int
        """
        return self.length - self.offset

    def reset(self):
        """
        Resets the pointer of the stream to the beginning

        Returns
        -------

        """
        self.offset = 0

    def copy(self):
        return JamBytes(self.data)

    def __str__(self):
        return "0x{}".format(self.data.hex())

    def __eq__(self, other):
        if not hasattr(other, 'data'):
            return False
        return self.data == other.data

    def __len__(self):
        return len(self.data)

    def __repr__(self, context=10):
        start = max(0, self.offset - context)
        end = min(len(self.data), self.offset + context + 1)
        left = self.data[start:self.offset].hex()
        right = self.data[self.offset:end].hex()
        return f"<{self.__class__.__name__}(data={left}[{self.offset}]->{right}[{end}])>"

    def __add__(self, data):

        if type(data) is JamBytes:
            return JamBytes(self.data + data.data)

        if type(data) is bytes:
            data = bytearray(data)
        elif type(data) is str and data[0:2] == '0x':
            data = bytearray.fromhex(data[2:])

        if type(data) is bytearray:
            return JamBytes(self.data + data)

    def __bytes__(self):
        return self.to_bytes()

    def to_bytes(self):
        return bytes(self.data)

    def to_hex(self) -> str:
        """
        Return a hex-string (e.g. "0x00") representation of the byte-stream

        Returns
        -------
        str
        """
        return f'0x{self.data.hex()}'


class UInt:
    """
    Implementation of fixed size integer encoding as specified in GP-0.3.6-ref:271
    """

    @classmethod
    def from_scale_bytes(cls, scale_bytes: JamBytes, length: int) -> int:
        return int.from_bytes(scale_bytes.get_next_bytes(length), byteorder='little', signed=False)

    @classmethod
    def to_scale_bytes(cls, value: int, length: int) -> JamBytes:
        return JamBytes(int(value).to_bytes(length=length, byteorder='little'))


class VarInt64:
    """
    Implementation of variable size 64bit integer encoding as specified in GP-0.3.6-ref:272
    """

    @classmethod
    def from_scale_bytes(cls, data: JamBytes) -> int:

        prefix = int.from_bytes(data.get_next_bytes(1), byteorder='little')

        if prefix < 128:
            return prefix

        if 0x80 <= prefix < 0xc0:
            length = 1
        elif 0xc0 <= prefix < 0xe0:
            length = 2
        elif 0xe0 <= prefix < 0xf0:
            length = 3
        elif 0xf0 <= prefix < 0xf8:
            length = 4
        elif 0xf8 <= prefix < 0xfc:
            length = 5
        elif 0xfc <= prefix < 0xfe:
            length = 6
        elif 0xfe <= prefix < 0xff:
            length = 7
        else:
            length = 8

        if 1 <= length < 8:  # Handles case for `2**7 <= value < 2**21`
            value_part = prefix - (2 ** 8 - 2 ** (8 - length))
            value = (value_part * 2 ** (8 * length)) + int.from_bytes(data.get_next_bytes(length), byteorder='little')
        elif length == 8:  # Handles case for `2**21 <= value < 2**64`
            # value_part = prefix - (2 ** 8 - 1)
            value = int.from_bytes(data.get_next_bytes(8), byteorder='little')
        else:
            raise SerializationException("Unsupported length")

        return value

    @classmethod
    def to_scale_bytes(cls, value: int) -> JamBytes:
        """
        Serializes a natural number x using a variable-length prefix with up to 4 bytes.

        Parameters
        ----------
        value

        Returns
        -------

        """
        if value < 0:
            raise SerializationException("Cannot encode negative value")

        if value < 2**7:
            return JamBytes(bytes([value]))

        length = math.ceil(value.bit_length() / 7) - 1

        if 2 ** 7 <= value < 2 ** 56:
            prefix = (2 ** 8 - 2 ** (8 - length)) + (value // 2 ** (8 * length))
            remainder = (value % 2 ** (8 * length)).to_bytes(length, byteorder='little')

        elif 2**56 <= value < 2**64:
            prefix = 2**8 - 1
            remainder = value.to_bytes(8, byteorder='little')

        else:
            raise SerializationException("Number too large for 64-bit variable-length encoding")

        return JamBytes(bytes([prefix]) + remainder)


class Serializable:

    @classmethod
    def from_json(cls: Type[T], data: Union[dict, str]) -> T:
        field_values = {}

        def convert_field(field_type, value):
            if value is None:
                return None
            if field_type in [str, int, float, bool]:
                return value
            elif field_type is bytes:
                return bytes.fromhex(value[2:])
            elif issubclass(field_type, enum.Enum):
                return field_type[value]
            elif is_dataclass(field_type):
                return field_type.from_json(value)

        if not is_dataclass(cls):
            raise NotImplementedError("Can only be used on dataclasses")
        if not isinstance(data, dict):
            data = json.loads(data)

        for field in dataclasses.fields(cls):

            data_field_name = field.metadata.get('name') or field.name
            actual_type = field.type

            if data.get(data_field_name) is not None:

                if typing.get_origin(actual_type) is typing.Union:
                    # Extract the arguments of the Union type
                    args = typing.get_args(actual_type)
                    if type(None) in args:
                        actual_type = [arg for arg in args if arg is not type(None)][0]

                if typing.get_origin(actual_type) is list:
                    field_values[field.name] = []
                    for item in data[data_field_name]:
                        field_values[field.name].append(convert_field(typing.get_args(actual_type)[0], item))
                else:
                    field_values[field.name] = convert_field(actual_type, data[data_field_name])
            else:
                field_values[field.name] = None

        return cls(**field_values)

    @classmethod
    def from_scale_bytes(cls: Type[T], scale_bytes: JamBytes) -> T:
        field_values = {}

        def extract_field(orig_field, field_type):
            if field_type is str:
                return scale_bytes.get_next_bytes(orig_field.metadata.get('length'))
            elif field_type is int:
                length = orig_field.metadata.get('length')
                if not length:
                    raise ValueError('length metadata is required for int fields')

                if type(length) is dataclasses.Field:
                    length = field_values[length.name]

                if length == 'varint':
                    return VarInt64.from_scale_bytes(scale_bytes)
                else:
                    return UInt.from_scale_bytes(scale_bytes, length)

            elif field_type is bytes:
                length = orig_field.metadata.get('length')
                if type(length) is dataclasses.Field:
                    length = field_values[length.name]
                return scale_bytes.get_next_bytes(length)
            elif is_dataclass(field_type):
                return field_type.from_scale_bytes(scale_bytes)
            elif field_type is type(None):
                return None
            else:
                raise NotImplementedError("unsupported type")

        if not is_dataclass(cls):
            raise NotImplementedError("Can only be used on dataclasses")

        for field in dataclasses.fields(cls):

            actual_type = field.type

            if typing.get_origin(actual_type) is typing.Union:
                # Extract the arguments of the Union type
                args = typing.get_args(actual_type)
                if type(None) in args:
                    # Check if Option is None
                    option_byte = scale_bytes.get_next_bytes(1)
                    if option_byte == b'\x00':
                        field_values[field.name] = None
                        continue
                    actual_type = [arg for arg in args if arg is not type(None)][0]

            if typing.get_origin(actual_type) is list:
                field_values[field.name] = []

                if field.metadata.get('size') is None:
                    raise ValueError(f"Missing 'size' metadata for {field.name}")

                item_count = field.metadata.get('size')
                if type(item_count) is dataclasses.Field:
                    item_count = field_values[item_count.name]
                elif type(item_count) is str:
                    # Obtain Vec length
                    item_count = VarInt64.from_scale_bytes(scale_bytes)

                for _ in range(0, item_count):
                    field_values[field.name].append(extract_field(field, typing.get_args(actual_type)[0]))
            else:
                field_values[field.name] = extract_field(field, actual_type)

        return cls(**field_values)

    def to_scale_bytes(self) -> JamBytes:
        def convert_field(orig_field, field_type, value) -> JamBytes:
            if field_type is str:
                return value.encode('utf-8')
            elif field_type is int:
                length = orig_field.metadata.get('length')
                if not length:
                    raise ValueError("length metadata is required for int fields")

                if type(length) is dataclasses.Field:
                    length = getattr(self, length.name)

                if length == 'varint':
                    return VarInt64.to_scale_bytes(value)
                else:
                    return UInt.to_scale_bytes(value, length)

            elif field_type is bytes:
                return JamBytes(value)
            elif is_dataclass(field_type) or issubclass(field_type, enum.Enum):
                return value.to_scale_bytes()
            elif field_type is type(None):
                return JamBytes(bytes())
            else:
                raise NotImplementedError("unsupported type")

        if issubclass(self.__class__, enum.Enum):
            return JamBytes(bytes([self.value]))
        elif is_dataclass(self):

            data = JamBytes(bytearray())
            for field in dataclasses.fields(self):

                actual_type = field.type
                field_value = getattr(self, field.name)

                # if field_value is None and field.metadata.get('default') is not None:
                #     field_value = field.metadata.get('default')

                if typing.get_origin(actual_type) is typing.Union:
                    # Extract the arguments of the Union type
                    args = typing.get_args(actual_type)
                    if type(None) in args:
                        actual_type = [arg for arg in args if arg is not type(None)][0]
                        if field_value is None:
                            data += JamBytes(bytes([0]))
                            continue
                        else:
                            data += JamBytes(bytes([1]))

                if typing.get_origin(actual_type) is list:
                    if type(field.metadata.get('size')) is str:
                        # Add Vec length data
                        data += VarInt64.to_scale_bytes(len(field_value))

                    for item in field_value:
                        try:
                            data += convert_field(field, typing.get_args(actual_type)[0], item)
                        except IndexError as e:
                            print(e)
                else:
                    data += convert_field(field, actual_type, field_value)

            return data
        else:
            raise NotImplementedError(f"Cannot serialize type '{self.__class__}'")

    def to_json(self) -> dict:
        def convert_field(orig_field, field_type, value):
            if value is None:
                return None
            if field_type in [str, int, float, bool]:
                return value
            elif field_type is bytes:
                return f'0x{value.hex()}'
            elif type(field_type) is enum.EnumType:
                return field_type[value]
            elif is_dataclass(field_type):
                return field_type.to_json(value)
            else:
                raise NotImplementedError(f"unsupported type '{field_type}'")

        if issubclass(self.__class__, enum.Enum):
            return self.name
        elif is_dataclass(self):

            data = {}

            for field in dataclasses.fields(self):

                actual_type = field.type
                field_value = getattr(self, field.name)
                field_name = field.metadata.get('name') or field.name

                if typing.get_origin(actual_type) is typing.Union:
                    # Extract the arguments of the Union type
                    args = typing.get_args(actual_type)
                    if type(None) in args:
                        actual_type = [arg for arg in args if arg is not type(None)][0]
                        if field_value is None:
                            data[field_name] = None
                            continue

                if typing.get_origin(actual_type) is list:
                    data[field_name] = [
                        convert_field(field, typing.get_args(actual_type)[0], item) for item in field_value
                    ]
                else:
                    data[field_name] = convert_field(field, actual_type, field_value)

            return data
        else:
            raise NotImplementedError(f"Cannot serialize type '{type(self)}'")
