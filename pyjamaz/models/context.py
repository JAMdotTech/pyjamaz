import logging
from dataclasses import dataclass
from typing import Optional, List, Dict

from pyjamaz.accumulation import edit_queue, work_report_dependencies, work_report_mapping, priority_queue
from pyjamaz.graypaper_constants import ROTATION_PERIOD_CORE, EPOCH_TIMESLOTS
from pyjamaz.models.block import GuarantorAssignment, Header, AccumulationStatistic, DeferredTransferStatistic
from pyjamaz.models.common import WorkReport
from pyjamaz.models.state import AccumulationQueueWorkPackage, BeefyCommitmentMap, EntropyState, TimeslotState, \
    ValidatorPoolState, ValidatorArchiveState, AccumulationHistoryState, AccumulationQueueState
from pyjamaz.state.storage import StateStorage

from pyjamaz.transport.pubsub import PubSub
from pyjamaz.utils import guarantor_permute, flatten_list


@dataclass
class AppContext:
    pubsub: Optional[PubSub] = None
    state_storage: Optional[StateStorage] = None

@dataclass
class BlockContext:
    """
    GP-0.7.1-section:I.4.1 | Block context terms.
    TODO parameter docstring
    """
    # M
    guarantor_assignments: Optional[List[GuarantorAssignment]] = None
    # M*
    prev_guarantor_assignments: Optional[List[GuarantorAssignment]] = None
    # H_A
    author_bandersnatch_key: Optional[bytes] = None
    # TODO GP ref?
    seal_vrf_output: bytes = bytes(32)

    # R
    available_work_reports: Optional[List[WorkReport]] = None
    # R!
    ready_work_reports: Optional[List[WorkReport]] = None
    # R^Q
    queued_work_reports: Optional[List[AccumulationQueueWorkPackage]] = None
    # R*
    accumulatable_work_reports: Optional[List[WorkReport]] = None
    # G (Reporters set, containing Ed25519 key of validator)
    reporters: Optional[List[bytes]] = None

    # M_o
    state_root: Optional[bytes] = None

    # C TODO: C no longer as used block context variable in 0.7.1, part of Beta state component, right?
    beefy_commitment_map: Optional[BeefyCommitmentMap] = None

    # S TODO: S has different meaning in 0.7.1? Is this still used?
    accumulated_services: Optional[List[int]] = None

    # S
    accumulation_statistics: Optional[Dict[int, AccumulationStatistic]] = None

    # X TODO: X no longer used as block context variable in 0.7.1
    deferred_transfer_statistics: Optional[Dict[int, DeferredTransferStatistic]] = None

    def reset(self):
        self.guarantor_assignments = None
        self.prev_guarantor_assignments = None
        # TODO refactor
        # self.seal_vrf_output = bytes(32)
        self.available_work_reports = None
        self.ready_work_reports = None
        self.queued_work_reports = None
        self.accumulatable_work_reports = None
        self.state_root = None
        self.beefy_commitment_map = None
        self.accumulated_services = None
        self.accumulation_statistics = None
        self.deferred_transfer_statistics = None

    def set_guarantor_assignments(self,
                       post_entropy: EntropyState,
                       post_timeslot: TimeslotState,
                       post_validator_pool: ValidatorPoolState
                       ):
        """
        GP-0.7.1-eq:11.21 (M) | Sets guarantor assignments for current rotation

        Parameters
        ----------
        post_entropy
        post_timeslot
        post_validator_pool

        Returns
        -------

        """
        assignments = guarantor_permute(post_entropy.entropy[2], post_timeslot.number)

        logging.debug(f"Guarantor assignments for {post_timeslot.number}: {assignments}")

        self.guarantor_assignments = [
            GuarantorAssignment(
                core_index=core_index,
                validator_ed25519=post_validator_pool.validators[validator_index].ed25519
            ) for validator_index, core_index in enumerate(assignments)
        ]

    def set_prev_guarantor_assignments(
            self,
            post_entropy: EntropyState,
            post_timeslot: TimeslotState,
            post_validator_pool: ValidatorPoolState,
            post_validator_archive: ValidatorArchiveState
    ):
        """
        GP-0.7.1-eq:11.22 (M*) | Sets guarantor assignments for previous rotation

        Parameters
        ----------
        post_entropy
        post_timeslot
        post_validator_pool
        post_validator_archive

        Returns
        -------

        """
        if (post_timeslot.number - ROTATION_PERIOD_CORE) // EPOCH_TIMESLOTS == post_timeslot.number // EPOCH_TIMESLOTS:
            entropy = post_entropy.entropy[2]
            validators = post_validator_pool.validators
        else:
            entropy = post_entropy.entropy[3]
            validators = post_validator_archive.validators

        assignments = guarantor_permute(entropy, post_timeslot.number - ROTATION_PERIOD_CORE)

        self.prev_guarantor_assignments = [
            GuarantorAssignment(
                core_index=core_index,
                validator_ed25519=validators[validator_index].ed25519
            ) for validator_index, core_index in enumerate(assignments)
        ]

    def set_ready_work_reports(self):
        """
        GP-0.7.1-eq:12.4 (R^!) | Calculates and sets ready work reports

        Returns
        -------

        """
        if self.available_work_reports is None:
            raise ValueError("No available work reports")

        self.ready_work_reports = [
            w for w in self.available_work_reports
            if len(w.context.prerequisites) == 0 and len(w.segment_root_lookup) == 0
        ]

    def set_queued_work_reports(self, accumulation_history: AccumulationHistoryState):
        """
        GP-0.7.1-eq:12.5 (R^Q) | Calculates and sets queued work reports

        Returns
        -------

        """
        if self.available_work_reports is None:
            raise ValueError("No available work reports")

        self.queued_work_reports = edit_queue([
            work_report_dependencies(w) for w in self.available_work_reports
            if len(w.context.prerequisites) > 0 or len(w.segment_root_lookup) > 0
        ], accumulated_packages=flatten_list(accumulation_history.accumulation_history))

    def set_accumulatable_work_reports(self, header: Header, accumulation_queue: AccumulationQueueState):
        """
        GP-0.7.1-eq:12.10-12.12 (R^*) | Sets accumulatable work reports

        Parameters
        ----------
        header
        accumulation_queue

        Returns
        -------

        """

        if self.ready_work_reports is None:
            raise ValueError("No ready reports set")

        if self.queued_work_reports is None:
            raise ValueError("No queued reports set")

        # GP-0.7.1-eq:12.10
        m = header.timeslot % EPOCH_TIMESLOTS

        # GP-0.7.1-eq:12.12
        q = edit_queue(
            work_report_queue=flatten_list(accumulation_queue.accumulation_queue[m:]) +
                              flatten_list(accumulation_queue.accumulation_queue[:m]) +
                              self.queued_work_reports,
            accumulated_packages=work_report_mapping(self.ready_work_reports)
        )
        # GP-0.7.1-eq:12.11
        self.accumulatable_work_reports = self.ready_work_reports + priority_queue(q)

    def set_accumulation_statistics(self, accumulation_gas_utilized: Dict[int, int], nr_work_results_accumulated: int):
        """
        GP-0.7.1-eq:12.26,12.27 | Compose accumulation statistics (S)
        """
        if self.accumulatable_work_reports is None:
            raise ValueError("No accumulatable reports set")
        self.accumulation_statistics = {}
        for w in self.accumulatable_work_reports[:nr_work_results_accumulated]:
            for r in w.results:
                if r.service_id not in self.accumulation_statistics:
                    self.accumulation_statistics[r.service_id] = AccumulationStatistic()
                self.accumulation_statistics[r.service_id].nr_work_reports_accumulated += 1

        for s, u in accumulation_gas_utilized.items():
            if s not in self.accumulation_statistics:
                self.accumulation_statistics[s] = AccumulationStatistic()
            self.accumulation_statistics[s].total_gas_utilized = u
