import json
import logging
import os
import unittest
from os import path
from typing import Optional

from parameterized import parameterized

from pyjamaz.logger import setup_logging
from pyjamaz.models.common import WorkReport
from pyjamaz.settings import TEST_SUITE
from pyjamaz.models.context import AppContext, BlockContext
from pyjamaz.state.storage import StateStorage
from pyjamaz.state.components import Services, AccumulationHistory, AccumulationQueue, Statistics
from pyjamaz.storage import InMemoryStorageEngine
from pyjamaz.models.block import Header
from pyjamaz.models.state import TimeslotState, ServicesState, AccumulationHistoryState, EntropyState, \
    AccumulationQueueState, PrivilegedServicesState, ValidatorQueueState, AuthorizerQueuesState, \
    AccumulationQueueWorkPackage, ServiceAccount, StatisticsState, ValidatorPoolState, PendingChanges


def get_test_vector_files(file_filter: Optional[str] = None):
    test_vectors = []

    abs_dir = path.join(path.dirname(path.abspath(__file__)), 'fixtures', 'accumulate', TEST_SUITE)
    for filename in os.listdir(str(abs_dir)):
        if filename.endswith('.json'):
            if file_filter is None or file_filter in filename:
                test_vectors.append((f'{filename}', filename))
    return test_vectors


def reformat_work_report(work_report_data: dict) -> dict:
    work_report_data["segment_root_lookup"] = {
        s["work_package_hash"]: s["segment_tree_root"] for s in work_report_data["segment_root_lookup"]
    }
    return work_report_data

class TestAccumulate(unittest.TestCase):


    def setUp(self):
        storage_engine = InMemoryStorageEngine()
        self.block_context = BlockContext()

        self.app_context = AppContext(state_storage=StateStorage(storage_engine))

        log_level = logging.INFO
        log_package_overrides = {
            "numba": logging.WARNING,
            "numba.core": logging.WARNING
        }
        setup_logging(log_level, log_package_overrides)

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

        accumulation_queue = []

        for queue in test_vector["pre_state"]["ready_queue"]:
            accumulation_queue.append(
                [AccumulationQueueWorkPackage.from_json(
                    {"report": reformat_work_report(i["report"]), "dependencies": i["dependencies"]}
                ) for i in queue]
            )

        pre_accumulation_queue = AccumulationQueueState(accumulation_queue=accumulation_queue)

        pre_accumulation_history = AccumulationHistoryState.from_json(
            {"accumulation_history": test_vector["pre_state"]["accumulated"]}
        )

        pre_services = ServicesState()
        pre_services.set_state_storage(self.app_context.state_storage)
        pre_services.pending_changes = PendingChanges()

        for s in test_vector["pre_state"]["accounts"]:
            pre_services.store_service_account(
                s["id"], ServiceAccount.from_json(
                    {
                        "code_hash": bytes.fromhex(s["data"]["service"]["code_hash"][2:]),
                        "balance": s["data"]["service"]["balance"],
                        "gas_limit_accumulate": s["data"]["service"]["min_item_gas"],
                        "gas_limit_on_transfer": s["data"]["service"]["min_memo_gas"],
                        "footprint_storage_items": s["data"]["service"]["items"],
                        "footprint_storage_bytes": s["data"]["service"]["bytes"],
                        "deposit_offset": s["data"]["service"]["deposit_offset"],
                        "creation_slot": s["data"]["service"]["creation_slot"],
                        "last_accumulation_slot": s["data"]["service"]["last_accumulation_slot"],
                        "parent_service": s["data"]["service"]["parent_service"],
                        "storage_items": {},
                        "preimages": {},
                        "preimage_availability": {},  # Note: done as a post processing step
                        "threshold_balance": 0
                    }
                ))

            pre_services.store_service_account(s["id"], ServiceAccount.from_json({
                "code_hash": bytes.fromhex(s["data"]["service"]["code_hash"][2:]),
                "balance": s["data"]["service"]["balance"],
                "gas_limit_accumulate": s["data"]["service"]["min_item_gas"],
                "gas_limit_on_transfer": s["data"]["service"]["min_memo_gas"],
                "footprint_storage_items": s["data"]["service"]["items"],
                "footprint_storage_bytes": s["data"]["service"]["bytes"],
                "deposit_offset": s["data"]["service"]["deposit_offset"],
                "creation_slot": s["data"]["service"]["creation_slot"],
                "last_accumulation_slot": s["data"]["service"]["last_accumulation_slot"],
                "parent_service": s["data"]["service"]["parent_service"],
                "storage_items": {},
                "preimages": {},
                "preimage_availability": {}, #Note: done as a post processing step
                "threshold_balance": 0
            }), save_to_tx=True)

            for p in s['data']['storage']:
                pre_services.store_storage_item(s["id"], bytes.fromhex(p["key"][2:]), bytes.fromhex(p['value'][2:]))
                pre_services.store_storage_item(s["id"], bytes.fromhex(p["key"][2:]), bytes.fromhex(p['value'][2:]), save_to_tx=True)

            for p in s['data']['preimage_blobs']:
                pre_services.store_preimage(s["id"], bytes.fromhex(p['blob'][2:]))
                pre_services.store_preimage(s["id"], bytes.fromhex(p['blob'][2:]), save_to_tx=True)

            preimage_requests = s['data']['preimage_requests']
            for p in preimage_requests:
                si_key = bytes.fromhex(p['key']['hash'][2:])
                si_len = p['key']['length']

                pre_services.store_preimage_availability(s["id"], si_key, si_len, p["value"])
                pre_services.store_preimage_availability(s["id"], si_key, si_len, p["value"], save_to_tx=True)

        pre_services.add_pending_changes()

        pre_privileged_services = PrivilegedServicesState(
            manager=test_vector["pre_state"]["privileges"]["bless"],
            assigners=test_vector["pre_state"]["privileges"]["assign"],
            delegator=test_vector["pre_state"]["privileges"]["designate"],
            registrar=test_vector["pre_state"]["privileges"]["register"],
            always_accumulators={s: g for s, g in test_vector["pre_state"]["privileges"]["always_acc"]}
        )

        # Set up post-state
        post_entropy = EntropyState.from_json({"entropy": [test_vector["post_state"]["entropy"]] * 4})
        post_state_timeslot = TimeslotState(number=test_vector["post_state"]["slot"])

        accumulation_queue = []

        for queue in test_vector["post_state"]["ready_queue"]:
            accumulation_queue.append([AccumulationQueueWorkPackage.from_json(
                {"report": reformat_work_report(i["report"]), "dependencies": i["dependencies"]}
            ) for i in queue])

        post_accumulation_queue = AccumulationQueueState(accumulation_queue=accumulation_queue)

        post_accumulation_history = AccumulationHistoryState.from_json(
            {"accumulation_history": test_vector["post_state"]["accumulated"]}
        )

        post_services = ServicesState.from_json(
            {
                "services": {
                        s["id"]: {
                        "code_hash": bytes.fromhex(s["data"]["service"]["code_hash"][2:]),
                        "balance": s["data"]["service"]["balance"],
                        "gas_limit_accumulate": s["data"]["service"]["min_item_gas"],
                        "gas_limit_on_transfer": s["data"]["service"]["min_memo_gas"],
                        "footprint_storage_items": s["data"]["service"]["items"],
                        "footprint_storage_bytes": s["data"]["service"]["bytes"],
                        "threshold_balance": 0,
                        "storage_items": {p['key']:p['value'] for p in s['data']['storage']},
                        "preimages": {p['hash']:p['blob'] for p in s['data']['preimage_blobs']},
                        "preimage_availability": {},
                        "deposit_offset": s["data"]["service"]["deposit_offset"],
                        "creation_slot": s["data"]["service"]["creation_slot"],
                        "last_accumulation_slot": s["data"]["service"]["last_accumulation_slot"],
                        "parent_service": s["data"]["service"]["parent_service"],
                    } for s in test_vector["post_state"]["accounts"]
                }
            }
        )

        #TODO: make serializing preimage_status generic
        for s in test_vector["post_state"]["accounts"]:
            preimage_requests = s['data']['preimage_requests']
            for p in preimage_requests:
                si_key = bytes.fromhex(p['key']['hash'][2:])
                si_len = p['key']['length']
                post_services.services[s["id"]].preimage_availability[(si_key, si_len)] = p["value"]

        post_privileged_services = PrivilegedServicesState(
            manager=test_vector["post_state"]["privileges"]["bless"],
            assigners=test_vector["post_state"]["privileges"]["assign"],
            delegator=test_vector["post_state"]["privileges"]["designate"],
            registrar=test_vector["post_state"]["privileges"]["register"],
            always_accumulators={s: g for s, g in test_vector["post_state"]["privileges"]["always_acc"]}
        )

        # Prepare block context
        self.block_context.reset()

        self.block_context.available_work_reports = [
            WorkReport.from_json(reformat_work_report(w)) for w in test_vector["input"]["reports"]
        ]

        self.block_context.set_ready_work_reports()
        self.block_context.set_queued_work_reports(pre_accumulation_history)

        self.block_context.set_accumulatable_work_reports(header=header, accumulation_queue=pre_accumulation_queue)

        # Run accumulation

        services = Services(self.block_context, self.app_context)

        accumulation_output = services.state_transition_accumulation(
            accumulatable_work_reports=self.block_context.accumulatable_work_reports,
            pre_state_privileged_services=pre_privileged_services,
            post_state_timeslot=post_state_timeslot,
            pre_state_services=pre_services,
            pre_state_authorizer_queues=AuthorizerQueuesState(authorizer_queues=[]),
            pre_state_validator_queue=ValidatorQueueState(validators=[]),
            post_state_entropy=post_entropy,
        )

        accumulation_history = AccumulationHistory(self.block_context, self.app_context)
        history_output = accumulation_history.state_transition(
            accumulatable_work_reports=self.block_context.accumulatable_work_reports,
            pre_state_accumulation_history=pre_accumulation_history,
            nr_work_results_accumulated=accumulation_output.nr_work_results_accumulated
        )

        accumulation_queue = AccumulationQueue(self.block_context, self.app_context)
        queue_output = accumulation_queue.state_transition(
            queued_work_reports=self.block_context.queued_work_reports,
            pre_state_accumulation_queue=pre_accumulation_queue,
            post_state_accumulation_history=history_output.post_state,
            pre_state_timeslot=pre_state_timeslot,
            post_state_timeslot=post_state_timeslot
        )

        statistics = Statistics(self.block_context, self.app_context)
        self.block_context.reporters = []

        stats_output = statistics.state_transition(
            extrinsic_guarantees=[],
            extrinsic_preimages=[],
            extrinsic_assurances=[],
            extrinsic_tickets=[],
            pre_state_timeslot=pre_state_timeslot,
            post_state_timeslot=post_state_timeslot,
            post_state_validator_pool=ValidatorPoolState(validators=[]),
            pre_state_statistics=StatisticsState.default(),
            header=header
        )

        post_stats = [
            {"id": s_id, "record": s_record.to_json()} for s_id, s_record in stats_output.post_state.services.items()
        ]

        accumulation_output.intermediate_state_after_accumulation.add_pending_changes()

        self.assertEqual(post_accumulation_history, history_output.post_state)
        self.assertEqual(post_accumulation_queue, queue_output.post_state)
        self.assertEqual(post_services.services, accumulation_output.intermediate_state_after_accumulation.services)
        self.assertEqual(test_vector["post_state"]["statistics"], post_stats)
        self.assertEqual(post_privileged_services, accumulation_output.post_state_privileged_services)


if __name__ == '__main__':
    unittest.main()
