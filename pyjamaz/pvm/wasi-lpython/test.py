from lpython import u32, i32, i64, f64, TypeVar, u8
from numpy import empty, array, uint32, int32
from math import sqrt

#https://github.com/lcompilers/lpython/tree/f8fbd8d3393ca1fab40a0bfcd08250be03b40d4a/integration_tests

T = TypeVar('T')

# def f(lst: T[:], i: T) -> T:
#     lst[0] = i
#     return lst[0]

# def use_array():
#     array: i32[1]
#     array = empty(1, dtype=int32)
#     x: i32
#     x = 69
#     print(f(array, x))

# use_array()

# @jscall
# def wasm_test(lst: T[:]):
#     pass
#
# def f(lst: T[:], idx: i32, val: T):
#     lst[idx] = val
#
# l: i32
# l = 10
# array: i32[10]
# array = empty(10, dtype=int32)
# i: i32
# for i in range(l):
#     f(array, i, i+1)
#     print(i)
#     print(array[i])
#     #print(array[i])
#     #print("\n\r")

# print("\n\r")
# print(array)
# print("\n\r")



class coord:
    def __init__(self: "coord"):
        self.x: i32 = 3
        self.y: i32 = 4

    def calculate(self: "coord") -> i32:
        return self.x + self.y

    # @staticmethod
    # def test(self: "coord"):
    #     print("TESTER!!!")

p1: coord = coord()
#sq_dist : i32 = p1.x*p1.x + p1.y*p1.y
#dist : f64 = sqrt(f64(sq_dist))
print("Test = ", p1.calculate())


# n = TypeVar("n")
# T = TypeVar('T')
#
# def test(a: T[n]):
#     l: i32[:] = empty(nr, dtype=int32)
#     #l[0] = 10
#     return l
#
# t: i32[1] = test(1)
# print("AHA:")
# print(t)
# print("end\n\r")
#
# #@jscall
# #def show_result(arr: i32[:], idx: i32) -> i32:
# #    return arr[idx]
#
#
# #def test(nr: i32) -> i32[:]:
# #    l: i32[5] = array([123, 321, 113, 114, 115])
# #    return l
#
# #test_arr: i32[5] = array([1,2,3,4,5]) #test(5)
# test_arr: i32[7] = empty(7, dtype=int32)
# test_arr[0]=1
# test_arr[1]=2
# test_arr[2]=3
# test_arr[3]=4
# test_arr[4]=5
# test_arr[5]=6
# test_arr[6]=7
#
# #res:i32 = show_result(test_arr, 1)
# #res:i32 = test_arr[3]
# #res:i32 = test_arr[3]
#
# print(test_arr[0])
# print("\n\r")
# print(test_arr[1])
# print("\n\r")
# print(test_arr[2])
# print("\n\r")
# print(test_arr[3])
# print("\n\r")
# print(test_arr[4])
# print("\n\r")
# print(test_arr[5])
# print("\n\r")
# print(test_arr[6])
# print("\n\r")