from scalecodec.types import Struct, Vec, Bytes, U32, H256, U64, I64


class ServiceAccount(Struct):
    #GP-equation: 87 | SCALETYPE-DEFINITION: "SERVICE_ACCOUNT"->"()" | "SERVICE_ACCOUNT refer to class ServiceAccount for details.
    #TODO Uitleg Arjan SCALE: hoe definiteren VEC/list van precies aantal elementen? Let op niet van toepassing op dit object. Algemene vraag.
    #TODO: INDEX OF STORAGE DICTIONARY: storage_dictionary[HASH] = storage_item for storage_hash HASH
    #TODO: INDEX OF PREIMAGE DICTIONARY: preimage_dictionary[HASH] = preimage for storage_hash HASH
    #TODO: INDEX OF STATUS DICTIONARY: status_dictionary[HASH][LENGTH] = status for storage_hash HASH

    arguments = {
        'storage_dictionary': Bytes,
        'preimage_dictionary': Bytes,
        'status_dictionary': Vec(U32),
        'code_hash': H256,
        'balance': U64,
        'gaslimit_accumulate': I64,
        'gaslimit_on_transfer': I64
    }

    #[TODO: input 1: ServiceAccount.code_hash (H256)]
    def get_storage(self):
        #[TODO: output 1: ServiceAccount.storage_item]
        pass

    #[TODO: input 1: ServiceAccount.preimage_hash (H256)]
    def get_preimage(self):
        #[TODO: output 1: ServiceAccount.preimage]
        pass

    #[TODO: input 1: ServiceAccount.data_hash (H256)]
    #[TODO: input 2: ServiceAccount.data_length (U32)]
    def get_status(self):
        #[TODO: output 1: ServiceAccount.status]
        pass
