import json
import unittest
from os import path

from jamcodec.types import Vec

from pyjamaz.types.block import Header, OutputMarks, Extrinsic, Assurance, Disputes, RefinementContext, WorkReport, \
    WorkResult, Guarantee, Preimage, TicketEnvelope, Block, WorkItem, WorkPackage
from pyjamaz.types.safrole import SafroleOutput, SafroleErrorCode


class TestCodec(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.test_vector_dir = path.join(path.dirname(path.abspath(__file__)), 'fixtures', 'codec')

    def test_assurances_extrinsic(self):
        with open(path.join(self.test_vector_dir, f'assurances_extrinsic.json')) as f:
            test_vector = json.load(f)

        assurances = [Assurance.from_json(item) for item in test_vector]
        value = [assurance.serialize() for assurance in assurances]
        self.assertListEqual(test_vector, value)

        with open(path.join(self.test_vector_dir, f'assurances_extrinsic.bin'), "rb") as f:
           jam_data = f.read()

        assurances_obj = Vec(Assurance.to_codec_def()).new()
        data = assurances_obj.encode([a.serialize() for a in assurances])
        self.assertEqual(jam_data.hex(), data.to_bytes().hex())

    def test_block(self):
        with open(path.join(self.test_vector_dir, f'block.json')) as f:
            test_vector = json.load(f)

        # translate fields
        test_vector['header']['timeslot'] = test_vector['header'].pop('slot')
        test_vector['header']['epoch_marker'] = test_vector['header'].pop('epoch_mark')
        test_vector['header']['tickets_marker'] = test_vector['header'].pop('tickets_mark')
        test_vector['header']['offenders_marker'] = test_vector['header'].pop('offenders_mark')

        block = Block.from_json(test_vector)
        value = block.serialize()
        self.assertDictEqual(test_vector, value)

        with open(path.join(self.test_vector_dir, f'block.bin'), "rb") as f:
           jam_data = f.read()

        self.assertEqual(jam_data.hex(), block.to_jam_bytes().to_bytes().hex())


    def test_disputes_extrinsic(self):
        with open(path.join(self.test_vector_dir, f'disputes_extrinsic.json')) as f:
            test_vector = json.load(f)

        # translate fields
        # None

        disputes_extrinsic = Disputes.from_json(test_vector)
        value = disputes_extrinsic.serialize()
        self.assertDictEqual(test_vector, value)

        with open(path.join(self.test_vector_dir, f'disputes_extrinsic.bin'), "rb") as f:
           jam_data = f.read()

        self.assertEqual(jam_data.hex(), disputes_extrinsic.to_jam_bytes().to_bytes().hex())

    def test_extrinsic(self):

        with open(path.join(self.test_vector_dir, f'extrinsic.json')) as f:
            test_vector = json.load(f)

        # translate fields

        extrinsic = Extrinsic.from_json(test_vector)
        value = extrinsic.serialize()
        self.assertDictEqual(test_vector, value)

        with open(path.join(self.test_vector_dir, f'extrinsic.bin'), "rb") as f:
           jam_data = f.read()

        self.assertEqual(jam_data.hex(), extrinsic.to_jam_bytes().to_bytes().hex())

    def test_guarantees_extrinsic(self):
        with open(path.join(self.test_vector_dir, f'guarantees_extrinsic.json')) as f:
            test_vector = json.load(f)

        guarantees = [Guarantee.from_json(item) for item in test_vector]
        value = [guarantee.serialize() for guarantee in guarantees]
        self.assertListEqual(test_vector, value)

        with open(path.join(self.test_vector_dir, f'guarantees_extrinsic.bin'), "rb") as f:
           jam_data = f.read()

        guarantees_obj = Vec(Guarantee.to_codec_def()).new()
        data = guarantees_obj.encode([g.serialize() for g in guarantees])
        self.assertEqual(jam_data.hex(), data.to_bytes().hex())


    def test_header(self):
        for n in [0, 1]:
            with open(path.join(self.test_vector_dir, f'header_{n}.json')) as f:
                test_vector = json.load(f)

            # translate fields
            test_vector['timeslot'] = test_vector.pop('slot')
            test_vector['epoch_marker'] = test_vector.pop('epoch_mark')
            test_vector['tickets_marker'] = test_vector.pop('tickets_mark')
            test_vector['offenders_marker'] = test_vector.pop('offenders_mark')

            header = Header.from_json(test_vector)
            value = header.serialize()
            self.assertDictEqual(test_vector, value)

            with open(path.join(self.test_vector_dir, f'header_{n}.bin'), "rb") as f:
                jam_data = f.read()

            self.assertEqual(jam_data.hex(), header.to_jam_bytes().to_bytes().hex())

    def test_preimages_extrinsic(self):
        with open(path.join(self.test_vector_dir, f'preimages_extrinsic.json')) as f:
            test_vector = json.load(f)

        preimages = [Preimage.from_json(item) for item in test_vector]
        value = [preimage.serialize() for preimage in preimages]
        self.assertListEqual(test_vector, value)

        with open(path.join(self.test_vector_dir, f'preimages_extrinsic.bin'), "rb") as f:
           jam_data = f.read()

        preimages_obj = Vec(Preimage.to_codec_def()).new()
        data = preimages_obj.encode([p.serialize() for p in preimages])
        self.assertEqual(jam_data.hex(), data.to_bytes().hex())

    def test_refine_context(self):
        with open(path.join(self.test_vector_dir, f'refine_context.json')) as f:
            test_vector = json.load(f)

        # translate fields
        # None

        refine_context = RefinementContext.from_json(test_vector)
        value = refine_context.serialize()
        self.assertDictEqual(test_vector, value)

        with open(path.join(self.test_vector_dir, f'refine_context.bin'), "rb") as f:
           jam_data = f.read()

        self.assertEqual(jam_data.hex(), refine_context.to_jam_bytes().to_bytes().hex())

    def test_tickets_extrinsic(self):
        with open(path.join(self.test_vector_dir, f'tickets_extrinsic.json')) as f:
            test_vector = json.load(f)

        tickets = [TicketEnvelope.from_json(item) for item in test_vector]
        value = [ticket.serialize() for ticket in tickets]
        self.assertListEqual(test_vector, value)

        with open(path.join(self.test_vector_dir, f'tickets_extrinsic.bin'), "rb") as f:
           jam_data = f.read()

        tickets_obj = Vec(TicketEnvelope.to_codec_def()).new()
        data = tickets_obj.encode([t.serialize() for t in tickets])
        self.assertEqual(jam_data.hex(), data.to_bytes().hex())

    def test_work_item(self):
        with open(path.join(self.test_vector_dir, f'work_item.json')) as f:
            test_vector = json.load(f)

        # translate fields
        # None

        work_item = WorkItem.from_json(test_vector)
        value = work_item.serialize()
        self.assertDictEqual(test_vector, value)

        with open(path.join(self.test_vector_dir, f'work_item.bin'), "rb") as f:
           jam_data = f.read()

        self.assertEqual(jam_data.hex(), work_item.to_jam_bytes().to_bytes().hex())

    def test_work_package(self):
        with open(path.join(self.test_vector_dir, f'work_package.json')) as f:
            test_vector = json.load(f)

        # translate fields
        # None

        work_package = WorkPackage.from_json(test_vector)
        value = work_package.serialize()
        self.assertDictEqual(test_vector, value)

        with open(path.join(self.test_vector_dir, f'work_package.bin'), "rb") as f:
           jam_data = f.read()

        self.assertEqual(jam_data.hex(), work_package.to_jam_bytes().to_bytes().hex())

    def test_work_report(self):
        with open(path.join(self.test_vector_dir, f'work_report.json')) as f:
            test_vector = json.load(f)

        # translate fields
        # None

        work_report = WorkReport.from_json(test_vector)
        value = work_report.serialize()
        self.assertDictEqual(test_vector, value)

        with open(path.join(self.test_vector_dir, f'work_report.bin'), "rb") as f:
           jam_data = f.read()

        self.assertEqual(jam_data.hex(), work_report.to_jam_bytes().to_bytes().hex())

    def test_work_result(self):
        for n in [0, 1]:
            with open(path.join(self.test_vector_dir, f'work_result_{n}.json')) as f:
                test_vector = json.load(f)

            # translate fields
            # None

            work_result = WorkResult.from_json(test_vector)
            value = work_result.serialize()
            self.assertDictEqual(test_vector, value)

            with open(path.join(self.test_vector_dir, f'work_result_{n}.bin'), "rb") as f:
                jam_data = f.read()

            self.assertEqual(jam_data.hex(), work_result.to_jam_bytes().to_bytes().hex())

    def test_enum(self):
        value = SafroleErrorCode.duplicate_ticket.serialize()
        self.assertEqual('duplicate_ticket', value)

        enum_obj = SafroleErrorCode.deserialize('duplicate_ticket')
        self.assertEqual(SafroleErrorCode.duplicate_ticket, enum_obj)

    def test_dataclass_enum(self):

        output = SafroleOutput(ok=OutputMarks(epoch_mark=None, tickets_mark=None))
        value = output.serialize()
        self.assertEqual({'ok': {'epoch_mark': None, 'tickets_mark': None}}, value)

        output = SafroleOutput(err=SafroleErrorCode.duplicate_ticket)
        value = output.serialize()

        self.assertEqual({'err': 'duplicate_ticket'}, value)

        data = output.to_jam_bytes()
        self.assertEqual('0x0106', data.to_hex())


if __name__ == '__main__':
    unittest.main()
