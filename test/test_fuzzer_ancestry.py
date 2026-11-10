import asyncio
from types import SimpleNamespace

import pytest

from pyjamaz.app import PyjamazApp
from pyjamaz.exceptions import StateTransitionError
from pyjamaz.fuzzer.v1.target import FuzzerTarget
from pyjamaz.fuzzer.v1.types import AncestryItem, FuzzerMessage, InitializeMessage
from pyjamaz.models.block import Block, Extrinsic, Header
from pyjamaz.models.context import AppContext
from pyjamaz.state.storage import StateStorage
from pyjamaz.storage import InMemoryStorageEngine


COUNTER = bytes([1]) * 31
REMOVED = bytes([2]) * 31
@pytest.fixture
def target(tmp_path):
    # Exercise the real application import/rollback boundary with a small
    # deterministic STF, without signatures, PVM execution, or a disk database.
    engine = InMemoryStorageEngine()
    app = PyjamazApp.__new__(PyjamazApp)
    app.state_db = engine.namespace(b"state")
    app.block_db = engine.namespace(b"block")
    app.state_storage = StateStorage(app.state_db)
    app.app_context = AppContext(state_storage=app.state_storage)
    app.pubsub = None
    app.working_state = None
    app.retrieve_jam_state = lambda: SimpleNamespace(state_root=app.state_storage.state_root())
    app.import_block = app._import_block

    async def transition(block, produce=False):
        await app.initialize(block.header)
        value = int.from_bytes(app.state_storage.get(COUNTER), "little")
        value += block.header.author_index
        app.state_storage.put(COUNTER, value.to_bytes(4, "little"))
        app.state_storage.commit()
        app.working_state = app.retrieve_jam_state()

    app.state_transition = transition
    return FuzzerTarget(str(tmp_path / "target.sock"), app)


async def initialize(target, *, header=None, ancestry=None):
    header = header or Header.default()
    response = await target.msg_initialize(FuzzerMessage(initialize=InitializeMessage(
        header=header,
        state=[(COUNTER, (10).to_bytes(4, "little")), (REMOVED, b"old")],
        ancestry=ancestry or [],
    )))
    assert response.error is None
    assert response.state_root == target.app.state_storage.state_root()
    return header


def child(parent, slot, increment=1):
    header = Header.default()
    header.parent = parent.hash
    header.timeslot = slot
    header.author_index = increment
    return Block(header=header, extrinsic=Extrinsic.default())


def test_initialize_preserves_real_header_when_ancestry_includes_it(target):
    async def run():
        header = Header.default()
        header.timeslot = 22
        header.parent = bytes([17]) * 32
        header.parent_state_root = bytes([31]) * 32
        await initialize(target, header=header, ancestry=[
            AncestryItem(slot=22, header_hash=header.hash),
            AncestryItem(slot=17, header_hash=header.parent),
        ])
        retained = target.app.state_storage.ancestors[header.hash]
        assert retained is header
        assert retained.parent_state_root == bytes([31]) * 32
        assert retained.parent == header.parent

    asyncio.run(run())


def test_initialize_rejects_conflicting_slot_for_its_header(target):
    async def run():
        header = Header.default()
        with pytest.raises(ValueError, match="ancestry slot mismatch"):
            await initialize(target, header=header, ancestry=[
                AncestryItem(slot=1, header_hash=header.hash),
            ])

    asyncio.run(run())


@pytest.mark.parametrize("local_ancestry", [False, True])
@pytest.mark.parametrize("peer_ancestry", [False, True])
def test_import_uses_negotiated_session_ancestry(target, monkeypatch, local_ancestry, peer_ancestry):
    async def run():
        genesis = await initialize(target)
        block = child(genesis, 1)
        ordinary_transition = target.app.state_transition
        seen = []

        async def transition(block, produce=False):
            seen.append(target.app.app_context.skip_lookup_anchor_ancestry.get())
            await ordinary_transition(block, produce)

        target.app.state_transition = transition
        ordinary_handshake = target.msg_handshake

        def handshake():
            message = ordinary_handshake()
            message.peer_info.features.block_ancestry = local_ancestry
            return message

        monkeypatch.setattr(target, 'msg_handshake', handshake)
        peer = ordinary_handshake()
        peer.peer_info.features.block_ancestry = peer_ancestry
        reader = asyncio.StreamReader()
        reader.feed_data(peer.fuzzer_encode())
        reader.feed_data(FuzzerMessage(import_block=block).fuzzer_encode())
        reader.feed_eof()

        class Writer:
            closed = False

            def get_extra_info(self, name):
                return 'test peer'

            def write(self, data):
                pass

            async def drain(self):
                pass

            def close(self):
                self.closed = True

            async def wait_closed(self):
                pass

        writer = Writer()
        await target._handle_client(reader, writer)
        assert seen == [not (local_ancestry and peer_ancestry)]
        assert not target.app.app_context.skip_lookup_anchor_ancestry.get()
        assert writer.closed

    asyncio.run(run())


@pytest.mark.parametrize("error_type", [StateTransitionError, RuntimeError, asyncio.CancelledError])
def test_failed_import_restores_strict_ancestry_policy(target, error_type):
    async def run():
        genesis = await initialize(target)

        async def reject(block):
            assert target.app.app_context.skip_lookup_anchor_ancestry.get()
            raise error_type('rejected candidate')

        target.app.import_block = reject
        request = FuzzerMessage(import_block=child(genesis, 1))
        if error_type is StateTransitionError:
            response = await target.msg_import_block(request, ancestry_enabled=False)
            assert 'rejected candidate' in response.error
        else:
            with pytest.raises(error_type):
                await target.msg_import_block(request, ancestry_enabled=False)
        assert not target.app.app_context.skip_lookup_anchor_ancestry.get()

    asyncio.run(run())


def test_fuzzer_ancestry_override_is_local_to_import_task(target):
    async def run():
        genesis = await initialize(target)
        entered, resume = asyncio.Event(), asyncio.Event()

        async def importing(block):
            assert target.app.app_context.skip_lookup_anchor_ancestry.get()
            entered.set()
            await resume.wait()
            assert target.app.app_context.skip_lookup_anchor_ancestry.get()

        target.app.import_block = importing
        task = asyncio.create_task(target.msg_import_block(
            FuzzerMessage(import_block=child(genesis, 1)), ancestry_enabled=False,
        ))
        await entered.wait()
        assert not target.app.app_context.skip_lookup_anchor_ancestry.get()
        assert not AppContext().skip_lookup_anchor_ancestry.get()
        resume.set()
        response = await task
        assert response.error is None

    asyncio.run(run())

