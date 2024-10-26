import pvm


test_vector = {
  "name": "inst_load_u8",
  "initial-regs": [
    0,
    0,
    0,
    0,
    0,
    0,
    0,
    0,
    0,
    0,
    0,
    0,
    0
  ],
  "initial-pc": 0,
  "initial-page-map": [
    {
      "address": 131072,
      "length": 4096,
      "is-writable": True
    }
  ],
  "initial-memory": [
    {
      "address": 131072,
      "contents": [
        18,
        52,
        86,
        120
      ]
    }
  ],
  "initial-gas": 10000,
  "program": [
    0,
    0,
    5,
    60,
    7,
    0,
    0,
    2,
    1
  ],
  "expected-status": "trap",
  "expected-regs": [
    0,
    0,
    0,
    0,
    0,
    0,
    0,
    18,
    0,
    0,
    0,
    0,
    0
  ],
  "expected-pc": 5,
  "expected-memory": [
    {
      "address": 131072,
      "contents": [
        18,
        52,
        86,
        120
      ]
    }
  ],
  "expected-gas": 9998
}


mem_size = 0
mem_offset = 0
mem_size = len(test_vector["expected-memory"][0]["contents"])
mem_offset = test_vector["expected-memory"][0]["address"]

# pvm_data = PVMProgram.from_jam_bytes(
#     JamBytes(bytes(test_vector["program"]))
# )
class pvm_data:
  code = bytearray(b'<\x07\x00\x00\x02')
  code_length = 5
  jump_table = []
  jump_table_entry = 0
  jump_table_entry = 0
  opcode_bitmask = [True, False, False, False, False]

pvm = pvm.PVM(
    pvm_data,
    test_vector["initial-regs"],
    test_vector["initial-pc"],
    test_vector["initial-gas"],
    test_vector["initial-page-map"],
    test_vector["initial-memory"],
    mem_size=mem_size,
    mem_offset=mem_offset
)

print(pvm.pc)
print(pvm.gas)
