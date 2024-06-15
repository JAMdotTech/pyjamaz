import ed25519_zebra

from constants import TIMESLOT_LENGTH
from hashing import create_blake2b_hash
from models.block import Block
from models.header import Header
from models.extrinsic import Extrinsic


def main():
    block = Block()
    print(f'Timeslot {TIMESLOT_LENGTH}')

    # test hash
    blake2b_hash = create_blake2b_hash('0x0000000000000000000000000000000000000000000000000000000000000000')
    print(f'test hash: 0x{blake2b_hash.hex()}')

    # ed25519 test
    private_key = bytes.fromhex('da3cf5b1e9144931a0f0db65664aab662673b099415a7f8121b7245fb0be4143')
    public_key = bytes.fromhex('f90bc712b5f2864051353177a9d627605d4bf7ec36c7df568cfdcea9f237c185')
    data = bytes.fromhex('010203')
    signature = ed25519_zebra.ed_sign(private_key, data)

    print(f'signature: 0x{signature.hex()}')
    verified = ed25519_zebra.ed_verify(signature, data, public_key)
    print(f'verified: {verified}')


if __name__ == '__main__':
    main()
