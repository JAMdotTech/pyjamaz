import unittest
from scalecodec.base import ScaleBytes
from models.block.block import Block
#from models.header import Header

class TestBlock(unittest.TestCase):
    def test_block_scale_encode(self):

        example_value = {
            'header': {
                'parent_hash': '0x0000000000000000000000000000000000000000000000000000000000000000',
                'prior_state_root': '0x0000000000000000000000000000000000000000000000000000000000000000',
                'extrinsic_hash': '0x0000000000000000000000000000000000000000000000000000000000000000',
                'timeslot': 1,
                'epoch': None,
                'winning_tickets': None,
                'judgements': [],
                'author_key_idx': 1,
                'vrf_signature': '0x00000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000',
                'block_seal': '0x00000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000'
            },
            'extrinsic': {
                'tickets': [],
                'judgements': [],
                'preimages': [],
                'assurances': [],
                'guarantees': []
            }
        }

        block = Block().new()
        block.deserialize(example_value)
        scale_data = block.encode()

        self.assertEqual(
            #TODO: Data klopt niet (meer)
            ScaleBytes(data="0x00000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000001000000000c0100020003000801000200"),
            scale_data
        )

    def test_block_scale_decode(self):
        # TODO: Data klopt niet (meer)
        scale_data = ScaleBytes(data="0x00000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000001000000000c0100020003000801000200")

        block = Block().new()
        block.decode(scale_data)

        example_value = {
            'header': {
                'parent_hash': '0x0000000000000000000000000000000000000000000000000000000000000000',
                'prior_state_root': '0x0000000000000000000000000000000000000000000000000000000000000000',
                'extrinsic_hash': '0x0000000000000000000000000000000000000000000000000000000000000000',
                'timeslot': 1,
                'epoch': None,
                'winning_tickets': None,
                'judgements': [],
                'author_key_idx': 1,
                'vrf_signature': '0x00000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000',
                'block_seal': '0x00000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000'
            },
            'extrinsic': {
                'tickets': [],
                'judgements': [],
                'preimages': [],
                'assurances': [],
                'guarantees': []
            }
        }

        self.assertDictEqual(example_value, block.value_serialized)


if __name__ == '__main__':
    unittest.main()
