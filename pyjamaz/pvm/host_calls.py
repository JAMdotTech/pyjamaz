"""
@dataclass
class ServiceAccount:
  code: bytes
  storage: Dict[bytes, bytes]
  preimages: Dict[bytes, bytes]
  balance: int
  gas_limit: int
  min_transfer_gas: int

@dataclass
class WorkPayload:
  data: bytes
  service_index: int
  code_hash: bytes
  package_hash: bytes
  context: bytes
  authorizer_hash: bytes
  authorizer_output: bytes
  export_offset: int
  import_segments: List[bytes]
  extrinsic_data: List[bytes]

class RefineInvocation:
  def __init__(self, pvm, historical_state_lookup):
      self.pvm = pvm  # Reference to PVM implementation
      self.historical_lookup = historical_state_lookup
      self.MAX_EXPORT_SIZE = 90 * 1024  # 90kb max export size
      self.LOOKUP_WINDOW = 4800  # 8 hours worth of slots

  def host_call_handler(self, call_type: int, registers: List[int], memory: Dict, context: Any) -> Tuple:
      #Handle host calls from within PVM execution
      if call_type == "gas":
          # ΩG - Get remaining gas
          return self.handle_gas_query(registers, memory)
      elif call_type == "historical_lookup":
          # ΩH - Historical state lookup
          return self.handle_historical_lookup(registers, memory, context)
      elif call_type == "inner_pvm":
          # Handle inner PVM creation/management
          return self.handle_inner_pvm(registers, memory, context)
      elif call_type == "export":
          # Handle data export
          return self.handle_export(registers, memory, context)
      else:
          # Unknown host call
          registers[7] = 0xFFFFFFFFFFFFFFFF - 1  # WHAT error code
          return (True, registers, memory)

  def psi_r(self, payload: WorkPayload) -> Tuple[Optional[bytes], List[bytes]]:
      #Implementation of ΨR (Refine service-account invocation)
      #Returns (refinement_output, export_segments) or (None, []) on error
      try:
          # Initialize PVM with service code
          program_code = self.get_service_code(payload.code_hash)
          if not program_code:
              return None, []

          # Prepare initial PVM state
          initial_gas = self.calculate_initial_gas()
          initial_memory = self.setup_initial_memory(payload)

          # Create execution context for host calls
          context = {
              "export_segments": [],
              "export_offset": payload.export_offset,
              "inner_pvms": {},
              "service_index": payload.service_index
          }

          # Execute PVM
          result = self.pvm.execute(
              program_code,
              initial_gas,
              initial_memory,
              host_call_handler=lambda *args: self.host_call_handler(*args, context)
          )

          if result.exit_reason in ["panic", "out_of_gas"]:
              return None, []

          # Validate exports don't exceed size limit
          total_export_size = sum(len(seg) for seg in context["export_segments"])
          if total_export_size > self.MAX_EXPORT_SIZE:
              return None, []

          # Extract refinement output from PVM memory
          refinement_output = self.extract_refinement_output(result.memory, result.registers)

          return refinement_output, context["export_segments"]

      except Exception as e:
          print(f"Refine invocation failed: {e}")
          return None, []

  def handle_historical_lookup(self, registers: List[int], memory: Dict, context: Any) -> Tuple:
      #Handle historical state lookup host calls
      lookup_key = self.read_memory_string(memory, registers[8])
      lookup_slot = registers[9]

      # Verify lookup is within allowed window
      current_slot = self.get_current_slot()
      if current_slot - lookup_slot > self.LOOKUP_WINDOW:
          registers[7] = 0xFFFFFFFFFFFFFFFF - 1  # WHAT error code
          return True, registers, memory

      # Perform historical lookup
      value = self.historical_lookup(lookup_slot, lookup_key)
      if value is None:
          registers[7] = 0xFFFFFFFFFFFFFFFF - 1  # NONE error code
          return True, registers, memory

      # Write result to memory
      self.write_memory_bytes(memory, registers[10], value)
      registers[7] = 0  # OK
      return True, registers, memory

  def handle_export(self, registers: List[int], memory: Dict, context: Any) -> Tuple:
      #Handle export host calls
      data = self.read_memory_bytes(memory, registers[8], registers[9])

      # Validate export size
      total_size = sum(len(seg) for seg in context["export_segments"]) + len(data)
      if total_size > self.MAX_EXPORT_SIZE:
          registers[7] = 0xFFFFFFFFFFFFFFFF - 5  # FULL error code
          return True, registers, memory

      # Add to exports
      context["export_segments"].append(data)
      registers[7] = len(context["export_segments"]) - 1 + context["export_offset"]
      return True, registers, memory

  # Helper methods...
  def get_service_code(self, code_hash: bytes) -> Optional[bytes]:
      #Retrieve service code from code hash
      pass

  def calculate_initial_gas(self) -> int:
      #Calculate initial gas allocation
      pass

  def setup_initial_memory(self, payload: WorkPayload) -> Dict:
      #Setup initial PVM memory state
      pass

  def extract_refinement_output(self, memory: Dict, registers: List[int]) -> bytes:
      #Extract refinement output from final PVM state
      pass

"""
from pyjamaz.hashing import blake2b_256_hash
from pyjamaz.pvm.constants import HostCallGeneral, HostCallResult
from pyjamaz.pvm.exceptions import InvalidHostCall

#TODO: add typings
#TODO: retrieve db connection through event call?
def invoke_host_call_pvm(pvm, db, host_call, service_index=None):

    # GP_B.6 General Functions

    pvm.gas -= 10

    match host_call:

        case HostCallGeneral.gas.value:
            pvm.reg[7] = pvm.gas

        case HostCallGeneral.lookup.value:
            s = service_index                   #TODO: service_index waar komt deze vandaan in het geval van ecalli invocation?
            d = pvm.reg[7]                      #TODO: wat is d[w7] uit GP???
            a = s if s in (d, 2**64-1,) else d
            
            h_o = pvm.reg[8]
            b_o = pvm.reg[9]
            b_z = pvm.reg[10]
            
            # TODO: gebruik mem calls, check out of bounds
            preimage_hash = blake2b_256_hash(pvm.mem[h_o:h_o+32])
            preimage = db.get(b'preimage:' + int.to_bytes(a, byteorder='little', length=1) + preimage_hash)

            #TODO: check of memory wel te beschrijven is
            if preimage_hash is not None:
                if preimage is not None:
                    nr_bytes = min(b_z, len(preimage))
                    #TODO: append bytes?
                    pvm.mem[b_o:nr_bytes] = preimage
                    pvm.reg[7] = len(preimage)
                else:
                    pvm.reg[7] = HostCallResult.none.value
            else:
                pvm.reg[7] = HostCallResult.oob.value


        case HostCallGeneral.read.value:
            pass

        case HostCallGeneral.write.value:
            pass

        case HostCallGeneral.info.value:
            pass

        case _:
            raise InvalidHostCall(f"Invalid hostcall: {host_call}")

