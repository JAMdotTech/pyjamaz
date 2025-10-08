import asyncio
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
from pyjamaz.state.components import Services, AccumulationHistory, AccumulationQueue
from pyjamaz.storage import InMemoryStorageEngine
from pyjamaz.models.block import Header
from pyjamaz.models.state import TimeslotState, ServicesState, AccumulationHistoryState, EntropyState, \
    AccumulationQueueState, PrivilegedServicesState, ValidatorQueueState, AuthorizerQueuesState, \
    AccumulationQueueWorkPackage


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

    @parameterized.expand(get_test_vector_files(file_filter='transfer_for_ejected_service-1.json'))
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

        pre_services = ServicesState.from_json(
            {"services": {s["id"]: {
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
                "storage_items": {p['key']:p['value'] for p in s['data']['storage']},
                "preimages": {p['hash']:p['blob'] for p in s['data']['preimages_blob']},
                "preimage_availability": {}, #Note: done as a post processing step
                "threshold_balance": 0

            } for s in test_vector["pre_state"]["accounts"]}}
        )

        for s in test_vector["pre_state"]["accounts"]:
            preimages_status = s['data']['preimages_status']
            for p in preimages_status:
                si_key = bytes.fromhex(p['hash'][2:])
                if si_key in pre_services.services[s["id"]].preimages:
                    si_len = len(pre_services.services[s["id"]].preimages[si_key])
                    pre_services.services[s["id"]].preimage_availability[(si_key, si_len)] = p["status"]

        pre_services.set_state_storage(self.app_context.state_storage)

        pre_privileged_services = PrivilegedServicesState(
            manager=test_vector["pre_state"]["privileges"]["bless"],
            assigners=test_vector["pre_state"]["privileges"]["assign"],
            delegator=test_vector["pre_state"]["privileges"]["designate"],
            registrar=0, #test_vector["pre_state"]["privileges"]["registrar"],
            always_accumulators={} #test_vector["pre_state"]["privileges"]["always_acc"]
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
                        "preimages": {p['hash']:p['blob'] for p in s['data']['preimages_blob']},
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
            preimages_status = s['data']['preimages_status']
            for p in preimages_status:
                si_key = bytes.fromhex(p['hash'][2:])
                if si_key in post_services.services[s["id"]].preimages:
                    si_len = len(post_services.services[s["id"]].preimages[si_key])
                    post_services.services[s["id"]].preimage_availability[(si_key, si_len)] = p["status"]

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

        # Store our current state
        result = asyncio.run(services.store_state(accumulation_output.intermediate_state_after_accumulation))
        self.app_context.state_storage.commit()

        # Read back the state from the storage engine, this should be the final state as a result from the accumulation transition function
        new_service_state = ServicesState(services={})
        new_service_state.set_state_storage(self.app_context.state_storage)
        for service_id in accumulation_output.intermediate_state_after_accumulation.services:
            try:
                new_service = new_service_state.retrieve_service_account(service_id)
                new_service_state.services[service_id] = new_service
                new_service.storage_items = {}

                expected_storage_keys = set()
                if service_id in post_services.services:
                    expected_storage_keys = {
                        key for key, value in post_services.services[service_id].storage_items.items() if value is not None
                    }

                for storage_item_hash, x in accumulation_output.intermediate_state_after_accumulation.services[service_id].storage_items.items():
                    """
                    @Arjan:
                    Ik heb volgens mij een nasty bug gevonden;
                    De hc_write hostcall werkte met een deepcopy vd ServiceState in de invocation context (opzicht logisch); Deze werd weer geplaatst in invocation_context.context.state_context.services.services (Dict[int, ServiceAccount])
                    
                    Wanneer een hostcall een service_account update, muteerde het de dict (vervangt bv services[service_id] met een nieuwe ServiceAccount, met een nieuwe storage map, footprint etc). 
                    Maar deze mutaties kwamen nooit terecht in de accumulation_state.services.services (state_transition_accumulation).
                    
                    services: Union[Dict[int, ServiceAccount], ServiceAccountMap]
                    
                    elke accumulate invocation maakt een pre-state copy (AccumulateInvocationContext.create_from_accumulation_state(...)). 
                    De hostcalls muteren deze kopie (bv hc_write calls services.store_service_account(...)). 
                    pvm_invoke_accumulate maakte hiervan een resultaat: PvmAccumulateOutput(... state_context=marshalling_output.context.context.state_context, ...)
                    
                    accumulation_state.services.services.update(output.state_context.services.services)
                    dit creeerde de nieuwe service ids via dict.update, maar voor bestaande ids overschreef de oude item het nieuw gemuteerde, en "vergat" dus alle hostcall changes...
                    
                    De bug trad dus alleen op voor bestaande services waar de hostcall de ServiceAccount muteerde, en dit ServiceAccount dus weer overschreven werd door de deep copy voor de hostcall
                    
                    pyjamaz/accumulation.py:
                    accumulation_state.services.services.update(output.state_context.services.services)
                    
                    Nu dus gefixed door dict.update(...) te vervangen met:
                    
                      services_state = output.services or output.state_context.services
                      mutated_ids = output.mutated_services or {service_id}
                      for mutated_id in mutated_ids:
                          if mutated_id in services_state.services:
                              accumulation_state.services.services[mutated_id] = services_state.services[mutated_id]
                    
                    * output.services bevat nu post hostcall ServicesState met een lijstje van mutated_services, we overschrijven nu service ids die een gemuteerde ServiceAccount hebben.

                    Dit is de executive samevatting :)
                    Zie code wijzigingen voor meer detaisl!

                    
                    Verder is er nog 1 puzzel over!
                    Emiel en ik hebben accumulate tests aangepast om de state transitions echt door te drukken naar de storage engine en deze vervolgens terug te syncen, om een "schone" state te krijgen waarop we kunnen vergelijken
                    
                    Er is echter 1 testvector over (welke ook de oorzaak van het stukje hierboven was); testvector transfer_for_ejected_service-1.json
                    Volgens mij klapt deze testvector terecht, want er wordt een storage item aangemaakt via de hc_write
                    De testvector verwacht 3 storage items (preimage, preimage_availability en 1 (nieuw) storage item, deze properties voor service 0 kloppen verder nu ook allemaal, door de bovenstaande fix
                    Maar ik snap nog niet waarom de testvector vervolgens helemaal geen storage_items heeft opgenomen voor service 0, deze is immers aangemaakt en alle properties wijzen daar ook op (zie 1.txt)
                    In ons resultaat (zie 2.txt) staat deze wel opgenomen...
                    
                    Als je de if not expected_storage_keys or storage_item_hash not in expected_storage_keys: hieronder weer aanzet, zal die uiteraard wel slagen, maar dat is alleen omdat ik dan op props check die expected zijn, 
                    wat uiteraard niet de bedoeling is :) 
                    """

                    # if not expected_storage_keys or storage_item_hash not in expected_storage_keys:
                    #     continue
                    try:
                        si = new_service_state.retrieve_storage_item(service_id, storage_item_hash)
                        new_service.storage_items[storage_item_hash] = si
                    except:
                        # Ignore deleted / missing storage items
                        pass

                # Storage content lives in the backing engine; we only track footprint metadata here.

                for preimage_hash, x in accumulation_output.intermediate_state_after_accumulation.services[service_id].preimages.items():
                    try:
                        pi = new_service_state.retrieve_preimage(service_id, preimage_hash)
                        new_service.preimages[preimage_hash] = pi

                        try:
                            pa = new_service_state.retrieve_preimage_availability(service_id, preimage_hash, len(pi))
                            new_service.preimage_availability[(preimage_hash, len(pi))] = pa
                        except:
                            # Ignore deleted / missing preimage availability
                            pass

                    except:
                        # Ignore deleted / missing preimages
                        pass

            except:
                # Ignore deleted / missing services
                pass

        self.assertEqual(post_accumulation_history.to_json(), history_output.post_state.to_json())
        self.assertEqual(post_accumulation_queue.to_json(), queue_output.post_state.to_json())

        expected_services = post_services.to_json()['services']
        new_services = new_service_state.to_json()['services']

        #self.assertEqual(post_services.to_json()['services'], accumulation_output.intermediate_state_after_accumulation.to_json()['services'])
        self.assertEqual(expected_services, new_services)


if __name__ == '__main__':
    unittest.main()
