import json
from typing import Type, TypeVar, Union

from scalecodec.base import ScaleTypeDef, ScaleType, ScaleBytes

T = TypeVar('T')


class Serializable:

    _scale_type_def: ScaleTypeDef

    @staticmethod
    def scale_type_def() -> ScaleTypeDef:
        return ScaleTypeDef()

    def serialize(self) -> Union[str, int, float, bool, dict, list]:
        scale_type = self.to_scale_type()
        return scale_type.serialize()

    @classmethod
    def deserialize(cls: Type[T], data: Union[str, int, float, bool, dict, list]) -> T:
        scale_type = cls._scale_type_def.new()
        scale_type.deserialize(data)
        return cls.from_scale_type(scale_type)

    def to_scale_type(self) -> ScaleType:
        raise NotImplementedError

    @classmethod
    def from_scale_type(cls: Type[T], scale_type: ScaleType) -> T:
        raise NotImplementedError

    def to_scale_bytes(self) -> ScaleBytes:
        scale_obj = self.to_scale_type()
        return scale_obj.encode()

    @classmethod
    def from_scale_bytes(cls: Type[T], scale_bytes: ScaleBytes) -> T:
        scale_obj = cls._scale_type_def.new()
        scale_obj.decode(scale_bytes)
        return cls.from_scale_type(scale_obj)

    def to_json(self) -> str:
        return json.dumps(self.serialize(), indent=4)

    @classmethod
    def from_json(cls: Type[T], json_data: str) -> T:
        data = json.loads(json_data)
        return cls.deserialize(data)
