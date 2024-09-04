import json
import unittest
from os import path

from jamcodec.types import Vec

from pyjamaz.types.block import Header, OutputMarks, Extrinsic, Assurance, Disputes, RefinementContext, WorkReport, \
    WorkResult, Guarantee, Preimage, TicketEnvelope
from pyjamaz.types.safrole import SafroleOutput, SafroleErrorCode


class TestCodec(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.test_vector_dir = path.join(path.dirname(path.abspath(__file__)), 'fixtures', 'codec')

    def test_assurances_extrinsic(self):
        with open(path.join(self.test_vector_dir, f'assurances_extrinsic.json')) as f:
            test_vector = json.load(f)

        # Todo: Explain how to import a list of Assurance from JSON
        assurances = Vec(Assurance).from_json(test_vector)
        value = assurances.serialize()
        self.assertDictEqual(test_vector, value)

        with open(path.join(self.test_vector_dir, f'assurances_extrinsic.bin'), "rb") as f:
           jam_data = f.read()

        self.assertEqual(jam_data.hex(), assurances.to_jam_bytes().to_bytes().hex())

    def test_block(self):
        pass

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
        # test_vector['timeslot'] = test_vector.pop('slot')
        # test_vector['epoch_marker'] = test_vector.pop('epoch_mark')
        # test_vector['tickets_marker'] = test_vector.pop('tickets_mark')
        # test_vector['offenders_marker'] = test_vector.pop('offenders_mark')

        extrinsic = Extrinsic.from_json(test_vector)
        value = extrinsic.serialize()
        # self.assertDictEqual(test_vector, value)

        # with open(path.join(self.test_vector_dir, f'extrinsic.bin'), "rb") as f:
        #    jam_data = f.read()

        # self.assertEqual(jam_data.hex(), extrinsic.to_jam_bytes().to_bytes().hex())

    def test_guarantees_extrinsic(self):
        with open(path.join(self.test_vector_dir, f'guarantees_extrinsic.json')) as f:
            test_vector = json.load(f)

        # Todo: Explain how to import a list of Guarantee from JSON
        guarantees = Vec(Guarantee).from_json(test_vector)
        value = guarantees.serialize()
        self.assertDictEqual(test_vector, value)

        with open(path.join(self.test_vector_dir, f'guarantees_extrinsic.bin'), "rb") as f:
           jam_data = f.read()

        self.assertEqual(jam_data.hex(), guarantees.to_jam_bytes().to_bytes().hex())

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

        # Todo: Explain how to import a list of Preimage from JSON
        preimages = Vec(Preimage).from_json(test_vector)
        value = preimages.serialize()
        self.assertDictEqual(test_vector, value)

        with open(path.join(self.test_vector_dir, f'preimages_extrinsic.bin'), "rb") as f:
           jam_data = f.read()

        self.assertEqual(jam_data.hex(), preimages.to_jam_bytes().to_bytes().hex())

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

        # Todo: Explain how to import a list of TicketEnvelope from JSON
        tickets = Vec(TicketEnvelope).from_json(test_vector)
        value = tickets.serialize()
        self.assertDictEqual(test_vector, value)

        with open(path.join(self.test_vector_dir, f'tickets_extrinsic.bin'), "rb") as f:
           jam_data = f.read()

        self.assertEqual(jam_data.hex(), tickets.to_jam_bytes().to_bytes().hex())

    def test_work_item(self):
        # Todo: type definition
        pass

    def test_work_package(self):
        # Todo: type definition
        pass

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
