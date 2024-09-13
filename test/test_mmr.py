import json
import unittest

from pyjamaz.merkle import MerkleTree, MerkleMountainRange


class TestMerkleMountainRange(unittest.TestCase):

    def test_mmr(self):
        mmr = MerkleMountainRange([])

        # Create easier to evaluate output
        mmr.merge_peaks = lambda right, left: b'H(' + right + b',' + left + b')'

        mmr.insert(b'1')
        self.assertEqual([b'1'], mmr.peaks)

        mmr.insert(b'2')
        self.assertEqual([None, b'H(1,2)'], mmr.peaks)

        mmr.insert(b'3')
        self.assertEqual([b'3', b'H(1,2)'], mmr.peaks)

        mmr.insert(b'4')
        self.assertEqual([None, None, b'H(H(1,2),H(3,4))'], mmr.peaks)

        mmr.insert(b'5')
        self.assertEqual([b'5', None, b'H(H(1,2),H(3,4))'], mmr.peaks)

        mmr.insert(b'6')
        self.assertEqual([None, b'H(5,6)', b'H(H(1,2),H(3,4))'], mmr.peaks)

        mmr.insert(b'7')
        self.assertEqual([b'7', b'H(5,6)', b'H(H(1,2),H(3,4))'], mmr.peaks)

        mmr.insert(b'8')
        self.assertEqual([None, None, None, b'H(H(H(1,2),H(3,4)),H(H(5,6),H(7,8)))'], mmr.peaks)

        mmr.insert(b'9')
        self.assertEqual([b'9', None, None, b'H(H(H(1,2),H(3,4)),H(H(5,6),H(7,8)))'], mmr.peaks)

        mmr.insert(b'10')
        self.assertEqual([None, b'H(9,10)', None, b'H(H(H(1,2),H(3,4)),H(H(5,6),H(7,8)))'], mmr.peaks)

        mmr.insert(b'11')
        self.assertEqual([b'11', b'H(9,10)', None, b'H(H(H(1,2),H(3,4)),H(H(5,6),H(7,8)))'], mmr.peaks)

        mmr.insert(b'12')
        self.assertEqual([None, None, b'H(H(9,10),H(11,12))', b'H(H(H(1,2),H(3,4)),H(H(5,6),H(7,8)))'], mmr.peaks)

        mmr.insert(b'13')
        self.assertEqual([b'13', None, b'H(H(9,10),H(11,12))', b'H(H(H(1,2),H(3,4)),H(H(5,6),H(7,8)))'], mmr.peaks)

        mmr.insert(b'14')
        self.assertEqual(
        [None, b'H(13,14)', b'H(H(9,10),H(11,12))', b'H(H(H(1,2),H(3,4)),H(H(5,6),H(7,8)))'], mmr.peaks
        )

        mmr.insert(b'15')
        self.assertEqual(
        [b'15', b'H(13,14)', b'H(H(9,10),H(11,12))', b'H(H(H(1,2),H(3,4)),H(H(5,6),H(7,8)))'], mmr.peaks
        )

        mmr.insert(b'16')

        self.assertEqual(
            [None, None, None, None, b'H(H(H(H(1,2),H(3,4)),H(H(5,6),H(7,8))),H(H(H(9,10),H(11,12)),H(H(13,14),H(15,16))))'], mmr.peaks
        )


if __name__ == '__main__':
    unittest.main()
