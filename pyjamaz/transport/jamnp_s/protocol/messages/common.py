from __future__ import annotations

from jamcodec.base import JamBytes, JamCodecType
from jamcodec.types import Vec

from pyjamaz.graypaper_constants import VALIDATOR_COUNT


class ImplicitVec(Vec):
    def encode(self, value: list) -> JamBytes:
        data = JamBytes(bytes())

        for idx, item in enumerate(value):
            if type(item) is JamBytes:
                data += item
            else:
                data += self.type_def.encode(item)
                if item and issubclass(item.__class__, JamCodecType):
                    value[idx] = item.serialize()

        return data

    def decode(self, data: JamBytes) -> list:
        value = []

        while True:
            obj = self.type_def.new()
            obj.decode(data)
            value.append(obj)

            if data.get_remaining_length() == 0:
                break

        return value


def calculate_r() -> int:
    return (VALIDATOR_COUNT // 3) + 1
