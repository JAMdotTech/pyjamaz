import json
import unittest
from os import path

from jamcodec.types import Vec

from pyjamaz.types.block import Header, OutputMarks, Extrinsic, Assurance, Disputes, RefinementContext, WorkReport, \
    WorkResult, Guarantee, Preimage, TicketEnvelope, Block, WorkItem, WorkPackage
from pyjamaz.types.safrole import SafroleOutput, SafroleErrorCode
from pyjamaz.types.state import DisputesState, AssurancesState, AuthorizerPoolsState, AuthorizerQueuesState, \
    EntropyState, PrivilegedServicesState, RecentHistoryState, SafroleState, StatisticsState, TimeslotState, \
    ValidatorArchiveState, ValidatorPoolState, ValidatorQueueState


class TestCodec(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.test_vector_dir = path.join(path.dirname(path.abspath(__file__)), 'fixtures', 'codec')
        cls.test_vector_custom_dir = path.join(path.dirname(path.abspath(__file__)), 'fixtures', 'codec', 'custom')

    def test_jdt_state_assurances(self):
        with open(path.join(self.test_vector_custom_dir, f'state_assurances.json')) as f:
            test_vector = json.load(f)

        state = AssurancesState.from_json(test_vector)
        value = state.serialize()
        self.assertDictEqual(test_vector, value)

        #with open(path.join(self.test_vector_custom_dir, f'state_assurances.bin'), "rb") as f:
        #   jam_data = f.read()
        # Todo: jambytes opslaan (bin or hex)
        # self.assertEqual(jam_data, state.to_jam_bytes().data.hex())

    def test_jdt_state_authorizer_pools(self):
        with open(path.join(self.test_vector_custom_dir, f'state_authorizer_pools.json')) as f:
            test_vector = json.load(f)

        state = AuthorizerPoolsState.from_json(test_vector)
        value = state.serialize()
        self.assertDictEqual(test_vector, value)

        #with open(path.join(self.test_vector_custom_dir, f'state_authorizer_pools.bin'), "rb") as f:
        #   jam_data = f.read()
        # Todo: jambytes opslaan (bin or hex)
        # self.assertEqual(jam_data, state.to_jam_bytes().data.hex())

    def test_jdt_state_authorizer_queues(self):
        with open(path.join(self.test_vector_custom_dir, f'state_authorizer_queues.json')) as f:
            test_vector = json.load(f)

        state = AuthorizerQueuesState.from_json(test_vector)
        value = state.serialize()
        self.assertDictEqual(test_vector, value)

        #with open(path.join(self.test_vector_custom_dir, f'state_authorizer_queues.bin'), "rb") as f:
        #   jam_data = f.read()
        # Todo: jambytes opslaan (bin or hex)
        # self.assertEqual(jam_data, state.to_jam_bytes().data.hex())

    def test_jdt_state_disputes(self):
        with open(path.join(self.test_vector_custom_dir, f'state_disputes.json')) as f:
            test_vector = json.load(f)

        state = DisputesState.from_json(test_vector)
        value = state.serialize()
        self.assertDictEqual(test_vector, value)

        #with open(path.join(self.test_vector_custom_dir, f'state_disputes.bin'), "rb") as f:
        #   jam_data = f.read()
        # Todo: jambytes opslaan (bin or hex)
        # self.assertEqual(jam_data, state.to_jam_bytes().data.hex())

    def test_jdt_state_entropy(self):
        with open(path.join(self.test_vector_custom_dir, f'state_entropy.json')) as f:
            test_vector = json.load(f)

        state = EntropyState.from_json(test_vector)
        value = state.serialize()
        self.assertDictEqual(test_vector, value)

        #with open(path.join(self.test_vector_custom_dir, f'state_entropy.bin'), "rb") as f:
        #   jam_data = f.read()
        # Todo: jambytes opslaan (bin or hex)
        # self.assertEqual(jam_data, state.to_jam_bytes().data.hex())

    def test_jdt_state_privileged_services(self):
        with open(path.join(self.test_vector_custom_dir, f'state_privileged_services.json')) as f:
            test_vector = json.load(f)

        state = PrivilegedServicesState.from_json(test_vector)
        value = state.serialize()
        self.assertDictEqual(test_vector, value)

        #with open(path.join(self.test_vector_custom_dir, f'state_privileged_services.bin'), "rb") as f:
        #   jam_data = f.read()
        # Todo: jambytes opslaan (bin or hex)
        # self.assertEqual(jam_data, state.to_jam_bytes().data.hex())

    def test_jdt_state_recent_history(self):
        with open(path.join(self.test_vector_custom_dir, f'state_recent_history.json')) as f:
            test_vector = json.load(f)

        state = RecentHistoryState.from_json(test_vector)
        value = state.serialize()
        self.assertDictEqual(test_vector, value)

        #with open(path.join(self.test_vector_custom_dir, f'state_recent_history.bin'), "rb") as f:
        #   jam_data = f.read()
        # Todo: jambytes opslaan (bin or hex)
        # self.assertEqual(jam_data, state.to_jam_bytes().data.hex())

    def test_jdt_state_safrole(self):
        with open(path.join(self.test_vector_custom_dir, f'state_safrole.json')) as f:
            test_vector = json.load(f)

        state = SafroleState.from_json(test_vector)
        value = state.serialize()
        self.assertDictEqual(test_vector, value)

        #with open(path.join(self.test_vector_custom_dir, f'state_safrole.bin'), "rb") as f:
        #   jam_data = f.read()
        # Todo: jambytes opslaan (bin or hex)
        # self.assertEqual(jam_data, state.to_jam_bytes().data.hex())

    def test_jdt_state_services(self):
        pass

    def test_jdt_state_statistics(self):
        with open(path.join(self.test_vector_custom_dir, f'state_statistics.json')) as f:
            test_vector = json.load(f)

        state = StatisticsState.from_json(test_vector)
        value = state.serialize()
        self.assertDictEqual(test_vector, value)

        #with open(path.join(self.test_vector_custom_dir, f'state_statistics.bin'), "rb") as f:
        #   jam_data = f.read()
        # Todo: jambytes opslaan (bin or hex)
        # self.assertEqual(jam_data, state.to_jam_bytes().data.hex())

    def test_jdt_state_timeslot(self):
        with open(path.join(self.test_vector_custom_dir, f'state_timeslot.json')) as f:
            test_vector = json.load(f)

        state = TimeslotState.from_json(test_vector)
        value = state.serialize()
        self.assertDictEqual(test_vector, value)

        #with open(path.join(self.test_vector_custom_dir, f'state_timeslot.bin'), "rb") as f:
        #   jam_data = f.read()
        # Todo: jambytes opslaan (bin or hex)
        # self.assertEqual(jam_data, state.to_jam_bytes().data.hex())

    def test_jdt_state_validator_archive(self):
        with open(path.join(self.test_vector_custom_dir, f'state_validator_archive.json')) as f:
            test_vector = json.load(f)

        state = ValidatorArchiveState.from_json(test_vector)
        value = state.serialize()
        self.assertDictEqual(test_vector, value)

        #with open(path.join(self.test_vector_custom_dir, f'state_validator_archive.bin'), "rb") as f:
        #   jam_data = f.read()
        # Todo: jambytes opslaan (bin or hex)
        # self.assertEqual(jam_data, state.to_jam_bytes().data.hex())

    def test_jdt_state_validator_pool(self):
        with open(path.join(self.test_vector_custom_dir, f'state_validator_pool.json')) as f:
            test_vector = json.load(f)

        state = ValidatorPoolState.from_json(test_vector)
        value = state.serialize()
        self.assertDictEqual(test_vector, value)

        #with open(path.join(self.test_vector_custom_dir, f'state_validator_pool.bin'), "rb") as f:
        #   jam_data = f.read()
        # Todo: jambytes opslaan (bin or hex)
        # self.assertEqual(jam_data, state.to_jam_bytes().data.hex())

    def test_jdt_state_validator_queue(self):
        with open(path.join(self.test_vector_custom_dir, f'state_validator_queue.json')) as f:
            test_vector = json.load(f)

        state = ValidatorQueueState.from_json(test_vector)
        value = state.serialize()
        self.assertDictEqual(test_vector, value)

        #with open(path.join(self.test_vector_custom_dir, f'state_validator_queue.bin'), "rb") as f:
        #   jam_data = f.read()
        # Todo: jambytes opslaan (bin or hex)
        # self.assertEqual(jam_data, state.to_jam_bytes().data.hex())

    def test_w3f_extrinsic_assurances(self):
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

    def test_w3f_block(self):
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


    def test_w3f_extrinsic_disputes(self):
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

    def test_w3f_extrinsic(self):

        with open(path.join(self.test_vector_dir, f'extrinsic.json')) as f:
            test_vector = json.load(f)

        # translate fields

        extrinsic = Extrinsic.from_json(test_vector)
        value = extrinsic.serialize()
        self.assertDictEqual(test_vector, value)

        with open(path.join(self.test_vector_dir, f'extrinsic.bin'), "rb") as f:
           jam_data = f.read()

        self.assertEqual(jam_data.hex(), extrinsic.to_jam_bytes().to_bytes().hex())

    def test_w3f_extrinsic_guarantees(self):
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


    def test_w3f_header(self):
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

    def test_w3f_extrinsic_preimages(self):
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

    def test_w3f_refine_context(self):
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

    def test_w3f_extrinsic_tickets(self):
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

    def test_w3f_work_item(self):
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

    def test_w3f_work_package(self):
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

    def test_w3f_work_report(self):
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

    def test_w3f_work_result(self):
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
