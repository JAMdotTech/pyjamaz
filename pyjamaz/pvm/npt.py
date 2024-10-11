# from typing import TypeAlias
#
# from typing import (
#     Any,
#     Generic,
#     TypeVar,
# )
#
# #NDArray: TypeAlias = Array[Any, int]
# #_DType = TypeVar("_DType", bound=dtype[Any])
# #_DType_co = TypeVar("_DType_co", covariant=True, bound=Generic[_DTypeScalar_co][Any])
# _DType_co = TypeVar("_DType_co", covariant=True, bound=Generic[Any][Any])
# _ShapeType_co = TypeVar("_ShapeType_co", covariant=True, bound=tuple[int, ...])
#
# #NDArray: TypeAlias = ndarray[Any, dtype[_ScalarType_co]]
# #NDArray: TypeAlias = Generic[_ShapeType_co, _DType_co]
# #NDArray: TypeAlias = Generic[_ShapeType_co]
# NDArray: TypeAlias = Generic[_ShapeType_co, _DType_co]
