from lpython import u32, i32, i64, f64, TypeVar, u8, jscall
from numpy import empty, array, uint32, int32
from math import sqrt

#n = TypeVar("n")
#T = TypeVar('T')

def wasm_test():
    print("WASM TEST WITHOUT ARGS")

def wasm_test2(nr:i32) -> i32:
    # print("WASM TEST ONE ARG: ")
    # res:i32 = nr + 1
    return nr

# def wasm_test3(a: i32[:], nr:i32) -> i32:
#     print("WASM TEST ARRAY ELEMENT: " + str(nr) + " + 1 = " + str(nr+1))
#     return a[nr]
#
# def wasm_test4(a: i32[:], nr:i32) ->  i32[:]:
#     print("WASM TEST ARRAY: ")
#     return a[0:nr]
#
@jscall
def js_test():
    pass
#
# @jscall
# def js_test2(idx:i32):
#     pass
#
# @jscall
# def js_test3(a: i32[:], idx: i32):
#    pass

#TODO: test json parsing / dict return type


arr: i32[5] = array([1,2,3,4,5])

print("WASM: wasm_test -> None")
wasm_test()

# print("WASM: wasm_test2(3) -> 4")
# wasm_test2(3)
#
# print("WASM: wasm_test3([1,2,3,4], 1) -> 3")
# wasm_test3(arr, 2)
#
# print("WASM: wasm_test4([1,2,3,4]) -> [0,1,2]")
# wasm_test4(arr, 2)

print("WASM: js_test")
js_test()
#
# print("WASM: js_test2(123)")
# js_test2(123)
#
# print("WASM: js_test3(123)")
# js_test3(arr, 3)
