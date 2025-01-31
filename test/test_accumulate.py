import json
import os
import unittest
from os import path
from typing import Optional

from pyjamaz.exceptions import StateTransitionError
from parameterized import parameterized

from pyjamaz.models.common import WorkReport
from pyjamaz.settings import TEST_SUITE
from pyjamaz.state.base import AppContext
from pyjamaz.state.components import Assurances, Services, AccumulationHistory, AccumulationQueue
from pyjamaz.storage import InMemoryStorage
from pyjamaz.models.block import Header, Guarantee, BlockContext, Extrinsic, ExtrinsicDisputes
from pyjamaz.models.state import AssurancesState, ValidatorPoolState, ValidatorArchiveState, TimeslotState, \
    ServicesState, RecentHistoryState, AuthorizerPoolsState, AccumulationHistoryState, EntropyState, \
    AccumulationQueueState, PrivilegedServicesState, ValidatorQueueState, AuthorizerQueuesState


def get_test_vector_files(file_filter: Optional[str] = None):
    test_vectors = []

    abs_dir = path.join(path.dirname(path.abspath(__file__)), 'fixtures', 'accumulate', TEST_SUITE)
    for filename in os.listdir(str(abs_dir)):
        if filename.endswith('.json'):
            if file_filter is None or file_filter in filename:
                test_vectors.append((f'{filename}', filename))
    return test_vectors


class TestAccumulate(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.storage_engine = InMemoryStorage()
        cls.block_context = BlockContext()
        cls.app_context = AppContext()

    @staticmethod
    def load_test_vector_data(test_vector_file):
        test_vector_file = path.join(
            path.dirname(path.abspath(__file__)), 'fixtures', 'accumulate', TEST_SUITE, test_vector_file
        )
        with open(test_vector_file) as f:
            return json.load(f)

    @parameterized.expand(get_test_vector_files(file_filter=''))
    def test_vector(self, name, test_file):

        test_vector = self.load_test_vector_data(test_file)

        # Set up input
        header = Header.default()
        header.timeslot = test_vector["input"]["slot"]

        # Set up pre-state
        pre_state_timeslot = TimeslotState(number=test_vector["pre_state"]["slot"])
        pre_entropy = EntropyState.from_json({"entropy": [test_vector["pre_state"]["entropy"]] * 4})
        pre_accumulation_queue = AccumulationQueueState.from_json(
            {"accumulation_queue": test_vector["pre_state"]["ready_queue"]}
        )
        pre_accumulation_history = AccumulationHistoryState.from_json(
            {"accumulation_history": test_vector["pre_state"]["accumulated"]}
        )

        pre_services = ServicesState.from_json(
            {"services": {s["id"]: {
                "code_hash": bytes.fromhex(s["data"]["service"]["code_hash"][2:]),
                "balance": s["data"]["service"]["balance"],
                "gas_limit_accumulate": s["data"]["service"]["min_item_gas"],
                "gas_limit_on_transfer": s["data"]["service"]["min_memo_gas"],
                "footprint_storage_items": s["data"]["service"]["items"],
                "footprint_storage_bytes": s["data"]["service"]["bytes"],
                "threshold_balance": 0,
                "storage_items": {},
                "preimages": {},
                "preimage_availability": {}

            } for s in test_vector["pre_state"]["accounts"]}}
        )

        pre_privileged_services = PrivilegedServicesState(
            empower_service=test_vector["pre_state"]["privileges"]["bless"],
            assign_service=test_vector["pre_state"]["privileges"]["assign"],
            designate_service=test_vector["pre_state"]["privileges"]["designate"],
            auto_accumulate_services={} #test_vector["pre_state"]["privileges"]["always_acc"]
        )

        # Set up post-state
        post_entropy = EntropyState.from_json({"entropy": [test_vector["post_state"]["entropy"]] * 4})
        post_state_timeslot = TimeslotState(number=test_vector["post_state"]["slot"])
        post_accumulation_queue = AccumulationQueueState.from_json(
            {"accumulation_queue": test_vector["post_state"]["ready_queue"]}
        )
        post_accumulation_history = AccumulationHistoryState.from_json(
            {"accumulation_history": test_vector["post_state"]["accumulated"]}
        )

        post_services = ServicesState.from_json(
            {"services": {s["id"]: {
                "code_hash": bytes.fromhex(s["data"]["service"]["code_hash"][2:]),
                "balance": s["data"]["service"]["balance"],
                "gas_limit_accumulate": s["data"]["service"]["min_item_gas"],
                "gas_limit_on_transfer": s["data"]["service"]["min_memo_gas"],
                "footprint_storage_items": s["data"]["service"]["items"],
                "footprint_storage_bytes": s["data"]["service"]["bytes"],
                "threshold_balance": 0,
                "storage_items": {},
                "preimages": {},
                "preimage_availability": {}

            } for s in test_vector["post_state"]["accounts"]}}
        )

        # Prepare block context
        self.block_context.initialize()
        self.block_context.available_work_reports = [WorkReport.from_json(w) for w in test_vector["input"]["reports"]]

        self.block_context.set_ready_work_reports()
        self.block_context.set_queued_work_reports(pre_accumulation_history)

        self.block_context.set_accumulatable_work_reports(header=header, accumulation_queue=pre_accumulation_queue)

        # Run accumulation

        services = Services(self.storage_engine, self.block_context, self.app_context)

        accumulation_output = services.state_transition(
            accumulatable_work_reports=self.block_context.accumulatable_work_reports,
            pre_state_privileged_services=pre_privileged_services,
            post_state_timeslot=post_state_timeslot,
            pre_state_services=pre_services,
            pre_state_authorizer_queues=AuthorizerQueuesState(authorizer_queues=[]),
            pre_state_validator_queue=ValidatorQueueState(validators=[]),
        )

        accumulation_history = AccumulationHistory(self.storage_engine, self.block_context, self.app_context)
        history_output = accumulation_history.state_transition(
            accumulatable_work_reports=self.block_context.accumulatable_work_reports,
            pre_state_accumulation_history=pre_accumulation_history,
            nr_work_results_accumulated=accumulation_output.nr_work_results_accumulated
        )

        accumulation_queue = AccumulationQueue(self.storage_engine, self.block_context, self.app_context)
        queue_output = accumulation_queue.state_transition(
            accumulatable_work_reports=self.block_context.accumulatable_work_reports,
            pre_state_accumulation_queue=pre_accumulation_queue,
        )

        self.assertEqual(post_accumulation_history, history_output.post_state)
        self.assertEqual(post_accumulation_queue, queue_output.post_state)

        # services = Services(self.storage_engine, self.block_context, self.app_context)
        # try:
        #     output = services.accumulation_queueing()
        #
        #     output = services.accumulation_execution()
        #
        # except StateTransitionError as e:
        #     output = None

        # self.assertDictEqual(test_vector['output'], output)


if __name__ == '__main__':
    unittest.main()
