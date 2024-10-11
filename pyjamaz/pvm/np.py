
def uint8(val):
    return val & 0xFF

def uint16(val):
    return val & 0xFFFF

def uint32(val):
    return val & 0xFFFFFF

def uint64(val):
    return int(val)

def int32(val):
    return int(val)

class Arrr(list):
    def tolist(self):
        return self

def array(data, dtype):
    return Arrr(data)

def zeros(size, dtype):
    return Arrr([0] * size)
