from scalecodec.base import ScaleType
from scalecodec.types import Struct

from models.block import Block
from models.state.assurances import Assurances
from models.state.authorizer_pool import AuthorizerPool
from models.state.authorizer_queue import AuthorizerQueue
from models.state.disputes import Disputes
from models.state.entropy import Entropy
from models.state.privileged_services import PrivilegedServices
from models.state.recent_blocks import RecentBlocks
from models.state.safrole import Safrole
from models.state.services import Services
from models.state.timeslot import Timeslot
from models.state.validator_archive import ValidatorArchive
from models.state.validator_pool import ValidatorPool
from models.state.validator_queue import ValidatorQueue


class StateObject(ScaleType):
    """
    Creates a new `State` object.
    GP-ref: 16
    """
    #GP-ref:16
    def state_transition(self, block: Block):
        # TODO: sequence of siloed state transitions based on dependencies
        # TODO: input 1: Current state (self)
        # TODO: input 2: Block
        # TODO: output 1: transitioned state
        pass


class State(Struct):
    # GP-ref:SIGMA,15
    scale_type_cls = StateObject
    arguments = {
        'authorizer_pool': AuthorizerPool(),
        'recent_blocks': RecentBlocks(),
        'safrole': Safrole(),
        'services': Services(),
        'entropy': Entropy(),
        'validator_queue': ValidatorQueue(),
        'validator_pool': ValidatorPool(),
        'validator_archive': ValidatorArchive(),
        'assurances': Assurances(),
        'timeslot': Timeslot(),
        'authorizer_queue': AuthorizerQueue(),
        'privileged_services': PrivilegedServices(),
        'disputes': Disputes()
    }
