"""Pinned JAMNP-S v1 framing and authenticated QUIC availability exchanges."""

import asyncio
import ipaddress
from dataclasses import replace
from types import SimpleNamespace

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from jamcodec.types import VarInt64
from pyjamaz.availability import (
    ImportedSegment, audit_shard_justification, build_availability_artifacts,
    segment_shard_justification,
)
from pyjamaz.exceptions import ProcessWorkpackageError
from pyjamaz.constants import MESSAGE_TYPES
from pyjamaz.merkle import ConstantDepthMerkleTree
from pyjamaz.models.common import ValidatorData
from pyjamaz.transport.cert import generate_cert, validate_peer_certificate
from pyjamaz.transport.jamnp_messages import (
    InvalidJAMNPSMessage, decode_import_proofs, decode_justification,
    decode_segment_indices, decode_segment_requests, encode_import_proofs,
    encode_justification, encode_segment_indices, encode_segment_request, frame,
)
from pyjamaz.transport.protocol_jamnp_s import (
    JAMNPS, MAX_PACKAGE_BYTES, StreamBuffer, wrap_protocol, ClientProtocol,
)
from pyjamaz.transport.pubsub import PubSub
from pyjamaz.utils import quic_peer_id
from test.test_runtime_refinement import package


def identity(tmp_path, name):
    private = Ed25519PrivateKey.generate()
    secret = private.private_bytes(serialization.Encoding.Raw, serialization.PrivateFormat.Raw,
                                   serialization.NoEncryption())
    public = private.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    keys = SimpleNamespace(ed25519=SimpleNamespace(private_key=secret))
    private_pem, cert_pem = generate_cert(keys, '127.0.0.1', quic_peer_id(public))
    cert, key = tmp_path / (name + '.crt'), tmp_path / (name + '.key')
    cert.write_bytes(cert_pem)
    key.write_bytes(private_pem)
    return public, str(cert), str(key)


def application(service):
    return SimpleNamespace(pubsub=PubSub(), runtime=SimpleNamespace(availability=service),
                           retrieve_block_hash=lambda slot: b'g' * 32,
                           retrieve_finalized_head=lambda: None,
                           retrieve_block_header=lambda h: None)


def peer(key, port):
    metadata = ipaddress.IPv6Address('::ffff:127.0.0.1').packed + port.to_bytes(2, 'little') + bytes(110)
    return ValidatorData(bytes(32), key, bytes(144), metadata)


class Service:
    def __init__(self):
        self.exports = [b'x' * 4104, b'y' * 4104]
        self.bundle = b'bundle' * 500
        self.artifacts = build_availability_artifacts(b'p' * 32, self.bundle, self.exports, 6)
        self.seen_peers = []
        self.authorized = []
        self.completed = []
        self.reject = False

    async def handle_request(self, peer_key, kind, messages):
        self.seen_peers.append(peer_key)
        request = messages[0]
        if kind in (137, 138):
            assert request[:32] == self.artifacts.spec.erasure_root
            shard = self.artifacts.shards[int.from_bytes(request[32:], 'little')]
            if kind == 137:
                return [shard.bundle_shard, b''.join(shard.segment_shards), encode_justification(shard.justification)]
            return [shard.bundle_shard, encode_justification(audit_shard_justification(shard))]
        if kind in (139, 140):
            groups = decode_segment_requests(request)
            result, proofs = [], []
            for root, index, indices in groups:
                assert root == self.artifacts.spec.erasure_root
                shard = self.artifacts.shards[index]
                for segment_index in indices:
                    result.append(shard.segment_shards[segment_index])
                    proofs.append(encode_justification(segment_shard_justification(shard, segment_index), 1368))
            return [b''.join(result)] + (proofs if kind == 140 else [])
        if kind == 148:
            result, proofs = [], []
            tree = ConstantDepthMerkleTree(self.exports)
            for root, indices in decode_segment_indices(request):
                assert root == tree.root()
                result.extend(self.exports[index] for index in indices)
                proofs.extend(tree.trace(index) for index in indices)
            return [b''.join(result), encode_import_proofs(proofs)]
        if kind == 147:
            return [self.bundle]
        raise ValueError('unsupported')

    async def authorize_submission(self, key, core, value, mappings):
        self.authorized.append((key, core, value, mappings))
        if self.reject:
            raise ValueError('authorization rejected')
        return 'authorized'

    async def complete_submission(self, context, kind, messages):
        assert context == 'authorized'
        self.completed.append((kind, messages))
        return []


async def nodes(tmp_path):
    server_key, server_cert, server_private = identity(tmp_path, 'server')
    client_key, client_cert, client_private = identity(tmp_path, 'client')
    service = Service()
    server = JAMNPS('127.0.0.1', 0, server_cert, server_private, application(service))
    client = JAMNPS('127.0.0.1', 0, client_cert, client_private, application(Service()))
    await server.listen()
    port = server.server._transport.get_extra_info('sockname')[1]
    return server, client, service, peer(server_key, port), client_key


def test_certificate_identity_is_the_only_dns_san(tmp_path):
    public, certificate_path, _ = identity(tmp_path, 'node')
    certificate = x509.load_pem_x509_certificate(open(certificate_path, 'rb').read())
    assert validate_peer_certificate(certificate, public) == public
    names = list(certificate.extensions.get_extension_for_class(x509.SubjectAlternativeName).value)
    assert names == [x509.DNSName(quic_peer_id(public))]
    with pytest.raises(ValueError, match='expected validator'):
        validate_peer_certificate(certificate, bytes(32))


def test_independent_stream_readers_accept_fragmented_interleaved_frames():
    async def run():
        first, second = StreamBuffer(), StreamBuffer()
        first_result = asyncio.create_task(first.read_all())
        second_result = asyncio.create_task(second.read_all())
        a, b = frame(b'abc') + frame(b''), frame(b'xyz123')
        for i in range(max(len(a), len(b))):
            if i < len(a):
                first.feed(a[i:i+1], i == len(a)-1)
            if i < len(b):
                second.feed(b[i:i+1], i == len(b)-1)
            await asyncio.sleep(0)
        assert await first_result == [b'abc', b'']
        assert await second_result == [b'xyz123']
    asyncio.run(run())


@pytest.mark.parametrize('data', [b'\x01', b'\x01\x00\x00\x00', b'\x02\x00\x00\x00x'])
def test_fin_requires_complete_length_and_message(data):
    async def run():
        reader = StreamBuffer()
        reader.feed(data, True)
        with pytest.raises(InvalidJAMNPSMessage, match='truncated'):
            await reader.read_all()
    asyncio.run(run())


def test_limits_abort_and_cancellation():
    async def run():
        reader = StreamBuffer(8)
        reader.feed(b'x' * 9)
        with pytest.raises(InvalidJAMNPSMessage, match='byte limit'):
            await reader.read_message()
        reader = StreamBuffer()
        reader.feed((100).to_bytes(4, 'little'))
        with pytest.raises(InvalidJAMNPSMessage, match='byte limit'):
            await reader.read_message(maximum=10)
        reader = StreamBuffer()
        pending = asyncio.create_task(reader.read_message())
        await asyncio.sleep(0)
        reader.abort(ConnectionError('reset'))
        with pytest.raises(ConnectionError, match='reset'):
            await pending
    asyncio.run(run())


def test_wire_codecs_match_pinned_tagged_proofs_and_requests():
    proof = (b'h' * 32, b'p' * 64, b's' * 1368)
    wire = b'\0' + proof[0] + b'\1' + proof[1] + b'\2' + proof[2]
    assert encode_justification(proof, 1368) == wire
    assert decode_justification(wire, 1368) == proof
    with pytest.raises(InvalidJAMNPSMessage):
        decode_justification(wire[:-1], 1368)
    with pytest.raises(InvalidJAMNPSMessage):
        decode_justification(b'\x03')
    request = b'r' * 32 + b'\x05\x00\x02\x01\x00\x02\x00'
    assert encode_segment_request(b'r' * 32, 5, [1, 2]) == request
    assert decode_segment_requests(request) == [(b'r' * 32, 5, (1, 2))]
    assert decode_segment_indices(encode_segment_indices(b'r' * 32, [2, 1, 2])) == [(b'r' * 32, (2, 1, 2))]
    proofs = ((b'h' * 32,), (), (b'j' * 32, b'k' * 32))
    assert decode_import_proofs(encode_import_proofs(proofs), 3) == proofs
    with pytest.raises(InvalidJAMNPSMessage):
        decode_segment_requests(b'r' * 32 + b'\0\0' + VarInt64.encode(6145).to_bytes())
    with pytest.raises(InvalidJAMNPSMessage):
        decode_import_proofs(encode_import_proofs(proofs) + b'!', 3)


def test_real_quic_all_availability_streams_and_mutual_identity(tmp_path):
    async def run():
        server, client, service, target, client_key = await nodes(tmp_path)
        try:
            spec = service.artifacts.spec
            assert client.PROTOCOL_NAME == 'jamnp-s/1/67676767'
            actual = await client.request_validator_shard(target, spec, 5)
            assert actual == service.artifacts.shards[5]
            chunk, proof = await client.request_audit_shard(target, spec, 4)
            assert chunk == service.artifacts.shards[4].bundle_shard
            for proven in [False, True]:
                results = await client.request_segment_shards(target, spec, 3, [0, 2, 1], proven=proven)
                assert [entry[0] for entry in results] == [service.artifacts.shards[3].segment_shards[i] for i in [0, 2, 1]]
                assert all((entry[1] is not None) == proven for entry in results)
            imports = await client.request_segments(target, spec.exports_root, [1, 0, 1])
            assert [entry.segment for entry in imports] == [service.exports[i] for i in [1, 0, 1]]
            assert await client.request_bundle(target, spec) == service.bundle
            assert service.seen_peers and set(service.seen_peers) == {client_key}
        finally:
            server.server.close()
    asyncio.run(run())


def test_real_quic_refuses_wrong_expected_peer_identity(tmp_path):
    async def run():
        server, client, service, target, _ = await nodes(tmp_path)
        try:
            with pytest.raises(ConnectionError, match='expected validator'):
                await client.request_bundle(replace(target, ed25519=bytes(32)), service.artifacts.spec)
            assert not service.seen_peers
        finally:
            server.server.close()
    asyncio.run(run())


def test_real_quic_interleaved_requests_and_altered_proof(tmp_path):
    async def run():
        server, client, service, target, _ = await nodes(tmp_path)
        original = service.handle_request
        try:
            from aioquic.asyncio.client import connect
            async with connect('127.0.0.1', target.get_metadata_port(),
                               configuration=client._configuration(is_client=True),
                               create_protocol=wrap_protocol(client, ClientProtocol, target.ed25519)) as protocol:
                root = service.artifacts.spec.erasure_root
                responses = await asyncio.gather(*(protocol.request(137, [root + index.to_bytes(2, 'little')]) for index in range(6)))
                assert [response[0] for response in responses] == [row.bundle_shard for row in service.artifacts.shards]
            async def altered(*args):
                response = await original(*args)
                response[2] = response[2][:-1] + bytes([response[2][-1] ^ 1])
                return response
            service.handle_request = altered
            with pytest.raises(ProcessWorkpackageError):
                await client.request_validator_shard(target, service.artifacts.spec, 0)
        finally:
            server.server.close()
    asyncio.run(run())


def test_real_quic_staged_submission_authorizes_once_before_body(tmp_path):
    async def run():
        server, client, service, target, client_key = await nodes(tmp_path)
        try:
            value = package()
            encoded = value.to_jam_bytes().to_bytes()
            assert await client.request(target, 133, [b'\x01\0' + encoded, b'extrinsics']) == []
            assert service.authorized == [(client_key, 1, value, {})]
            assert service.completed == [(133, [b'extrinsics'])]
            mappings = {b'p' * 32: b'r' * 32}
            header = b'\x00\0\x01' + b'p' * 32 + b'r' * 32
            assert await client.request(target, 146, [header, encoded, b'e', b's', b'j']) == []
            assert service.authorized[-1] == (client_key, 0, value, mappings)
            assert service.completed[-1] == (146, [b'e', b's', b'j'])
            service.reject = True
            with pytest.raises(ConnectionError):
                await client.request(target, 133, [b'\0\0' + encoded, b'x' * (1024 * 1024)])
            assert len(service.completed) == 2
        finally:
            server.server.close()
    asyncio.run(run())


def test_staged_quic_flow_credit_is_bounded_until_authorization(tmp_path):
    async def run():
        from aioquic.asyncio.client import connect
        server, client, service, target, _ = await nodes(tmp_path)
        authorization_started, authorize = asyncio.Event(), asyncio.Event()
        original = service.authorize_submission
        async def gated(*args):
            authorization_started.set()
            await authorize.wait()
            return await original(*args)
        service.authorize_submission = gated
        try:
            async with connect('127.0.0.1', target.get_metadata_port(),
                               configuration=client._configuration(is_client=True),
                               create_protocol=wrap_protocol(client, ClientProtocol, target.ed25519)) as protocol:
                value = package().to_jam_bytes().to_bytes()
                body = b'x' * (2 * 1024 * 1024)
                request = asyncio.create_task(protocol.request(133, [b'\0\0' + value, body]))
                await asyncio.wait_for(authorization_started.wait(), 1)
                await asyncio.sleep(0.05)
                remote = next(iter(server.conn_in.values()))
                reader = next(iter(remote.streams.values()))
                assert reader.received <= MAX_PACKAGE_BYTES + 1024
                assert not service.completed
                authorize.set()
                assert await request == []
                assert service.completed == [(133, [body])]
        finally:
            authorize.set()
            server.server.close()
    asyncio.run(run())


def test_real_quic_timeout_and_cancellation_reset_only_their_stream(tmp_path):
    async def run():
        from aioquic.asyncio.client import connect
        server, client, service, target, _ = await nodes(tmp_path)
        entered, cancelled = asyncio.Event(), asyncio.Event()
        original = service.handle_request
        async def slow(peer_key, kind, messages):
            if kind == 147:
                entered.set()
                try:
                    await asyncio.Event().wait()
                finally:
                    cancelled.set()
            return await original(peer_key, kind, messages)
        service.handle_request = slow
        try:
            async with connect('127.0.0.1', target.get_metadata_port(),
                               configuration=client._configuration(is_client=True),
                               create_protocol=wrap_protocol(client, ClientProtocol, target.ed25519)) as protocol:
                root = service.artifacts.spec.erasure_root
                with pytest.raises(TimeoutError):
                    await protocol.request(147, [root], timeout=0.05)
                await asyncio.wait_for(cancelled.wait(), 1)
                entered.clear()
                cancelled.clear()
                pending = asyncio.create_task(protocol.request(147, [root]))
                await asyncio.wait_for(entered.wait(), 1)
                pending.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await pending
                await asyncio.wait_for(cancelled.wait(), 1)
                # The same authenticated connection remains usable.
                response = await protocol.request(137, [root + b'\0\0'])
                assert response[0] == service.artifacts.shards[0].bundle_shard
        finally:
            server.server.close()
    asyncio.run(run())


def test_real_quic_rejects_another_genesis_alpn(tmp_path):
    async def run():
        server, client, service, target, _ = await nodes(tmp_path)
        _, cert, key = identity(tmp_path, 'otherchain')
        other = JAMNPS('127.0.0.1', 0, cert, key, application(Service()), genesis_hash=b'z' * 32)
        try:
            with pytest.raises(ConnectionError):
                await other.request_bundle(target, service.artifacts.spec)
            assert not service.seen_peers
        finally:
            server.server.close()
    asyncio.run(run())


def test_real_runtime_persisted_historical_sources_recover_import_over_quic(tmp_path):
    """Six authenticated historical endpoints, real storage and H.6 recovery."""
    async def run():
        from pyjamaz.d3l import AvailabilitySource, DataAvailabilityStore
        from pyjamaz.models.common import WorkReport
        from pyjamaz.runtime.availability import AvailabilityRuntime
        from pyjamaz.storage import FileStorageEngine

        nodes, peers, runtimes, apps = [], [], [], []
        registered = b'b' * 32
        exports = [(index + 1).to_bytes(4, 'little') * 1026 for index in range(65)]
        bundle = b'original complete bundle'
        artifacts = build_availability_artifacts(b'p' * 32, bundle, exports, 6)
        report = WorkReport(artifacts.spec, package().context, 1, bytes(32), 0, b'', {}, [])
        try:
            for index in range(6):
                public, cert, private = identity(tmp_path, 'historical' + str(index))
                directory = tmp_path / ('data' + str(index))
                directory.mkdir()
                app = application(None)
                app.d3l_store = DataAvailabilityStore(FileStorageEngine(str(directory)))
                app.state_storage = SimpleNamespace(block_hash=registered, parents={registered: None},
                                                    finalized_block_hash=None)
                # The current set deliberately excludes every source participant.
                app.working_state = SimpleNamespace(validator_pool=SimpleNamespace(validators=[]))
                app.config = SimpleNamespace(keys=SimpleNamespace(ed25519=SimpleNamespace(public_key=public)))
                runtime = AvailabilityRuntime(app)
                app.runtime.availability = runtime
                protocol = JAMNPS('127.0.0.1', 0, cert, private, app)
                app.protocol = protocol
                await protocol.listen()
                port = protocol.server._transport.get_extra_info('sockname')[1]
                nodes.append(protocol)
                peers.append(peer(public, port))
                runtimes.append(runtime)
                apps.append(app)
            source = AvailabilitySource(report, peers, [peers[1]], registered, 1)
            for index, app in enumerate(apps):
                if index:
                    app.d3l_store.store_work_report(report, bundle, exports, artifacts=artifacts)
                app.d3l_store.register_source(source)
                # Reopen persisted records before any network request.
                app.d3l_store = DataAvailabilityStore(FileStorageEngine(str(tmp_path / ('data' + str(index)))))
            client, target, spec = nodes[0], peers[1], artifacts.spec
            assert await client.request_validator_shard(target, spec, 2) == artifacts.shards[2]
            audit, _ = await client.request_audit_shard(target, spec, 3)
            assert audit == artifacts.shards[3].bundle_shard
            chunks = await client.request_segment_shards(target, spec, 4, [64, 66], proven=True)
            assert [chunk for chunk, _ in chunks] == [artifacts.shards[4].segment_shards[i] for i in [64, 66]]
            await runtimes[1].handle_request(peers[0].ed25519, 148, [encode_segment_indices(spec.exports_root, [64])])
            assert (await client.request_segments(target, spec.exports_root, [64]))[0].segment == exports[64]
            assert await client.request_bundle(target, spec) == bundle
            await runtimes[0].acquire_assigned(source)
            assert runtimes[0].assigned_ready(source)
            assigned = runtimes[0].assigned_index(source)
            assert apps[0].d3l_store.retrieve_validator_shard(spec, assigned) == artifacts.shards[assigned]

            calls = []
            for runtime in runtimes:
                runtime.store.storage_engine.delete(spec.exports_root)
                original = runtime.handle_request
                async def alter_ordinary(key, kind, messages, handler=original):
                    calls.append((key, kind))
                    response = await handler(key, kind, messages)
                    if kind == 139:
                        response[0] = bytes([response[0][0] ^ 1]) + response[0][1:]
                    return response
                runtime.handle_request = alter_ordinary
            imported = await runtimes[0].acquire_import(spec.exports_root, 64)
            assert imported.segment == exports[64]
            assert runtimes[0].store.retrieve_import(spec.exports_root, 64) == imported
            assert {139, 140}.issubset({kind for _, kind in calls})
            assert {key for key, _ in calls} == {peers[0].ed25519}
            assert all(not app.working_state.validator_pool.validators for app in apps)
            for selector in (5, 6):
                for index in (0, 1, 2, 64):
                    runtimes[0].store.storage_engine.delete(runtimes[0].store._import_key(spec.exports_root, index))
                await assert_quic_imports_reach_pvm(runtimes[0], client, source, exports, selector)
        finally:
            for node in nodes:
                node.server.close()
    asyncio.run(run())


async def assert_quic_imports_reach_pvm(availability, protocol, source, exports, selector):
    """Use real Psi_R/fetch, then compare Xi and B with a complete-export store."""
    from jamcodec.types import U32, Vec
    from pyjamaz.d3l import DataAvailabilityStore
    from pyjamaz.hashing import blake2b_256_hash
    from pyjamaz.models.app import D3LEntry
    from pyjamaz.models.common import ImportSegment, WorkItem, WorkPackage
    from pyjamaz.models.state import PendingChanges, ServicesState
    from pyjamaz.pvm.constants import Opcode
    from pyjamaz.state.base import state_key_constructor_preimage, state_key_constructor_preimage_availability
    from pyjamaz.state.storage import StateStorage
    from pyjamaz.storage import InMemoryStorageEngine
    from test.test_recovered_import_refine import load, pipeline, program_preimage

    source_hash, root = source.spec.hash, source.spec.exports_root
    output_address = 2 * 2**16
    refine_code = program_preimage([
        load(7, output_address), load(8, 0), load(9, 4104),
        load(10, selector), load(11, 1), load(12, 1),
        bytes((Opcode.ecalli.value, 2)),
        load(7, output_address), load(8, 4104), bytes((Opcode.jump_ind.value, 0)),
    ], heap_pages=2)
    auth_code = program_preimage([load(8, 0), bytes((Opcode.jump_ind.value, 0))])
    auth_hash, refine_hash = map(blake2b_256_hash, (auth_code, refine_code))
    state_engine = InMemoryStorageEngine()
    for code_hash, preimage in ((auth_hash, auth_code), (refine_hash, refine_code)):
        state_engine.put(state_key_constructor_preimage(0, code_hash), preimage)
        state_engine.put(state_key_constructor_preimage_availability(0, code_hash, len(preimage)),
                         Vec(U32).encode([0]).to_bytes())
    services = ServicesState()
    services.set_state_storage(StateStorage(state_engine))
    services.pending_changes = PendingChanges()
    initial_state = state_engine.as_dict()
    value = WorkPackage(0, auth_hash, source.report.context, b'', b'', [
        WorkItem(0, refine_hash, 1000, 1000, 0, b'', [
            ImportSegment.from_segment_root(root, 0),
            ImportSegment.from_work_package_hash(source_hash, 1),
        ], []),
        WorkItem(0, refine_hash, 1000, 1000, 0, b'', [
            ImportSegment.from_segment_root(root, 2),
            ImportSegment.from_work_package_hash(source_hash, 64),
        ], []),
    ])
    complete_store = DataAvailabilityStore(InMemoryStorageEngine())
    complete_store.store_segments(D3LEntry(root, exports))
    original_app = availability.app

    async def run(store, network=False):
        execution = pipeline(services, store, source_hash, root)
        if network:
            execution.app.protocol = protocol
            execution.app.state_storage = original_app.state_storage
            execution.app.retrieve_block_header = original_app.retrieve_block_header
            execution.app.runtime = SimpleNamespace(availability=availability)
            availability.app = execution.app
        execution.add_work_package(value, [])
        item = execution._pending_work_packages[value.hash()]
        await execution._refine_work_package(item)
        assert item.status.Reported
        assert [result.result.ok for result in item.work_report.results] == [
            exports[64] if selector == 5 else exports[1], exports[64],
        ]
        return item.work_report.to_jam_bytes().to_bytes(), store.storage_engine.get(b'bundle:' + value.hash())

    try:
        actual = await run(original_app.d3l_store, network=True)
        assert actual == await run(complete_store)
        assert state_engine.as_dict() == initial_state
        assert services.state_storage.transaction == {}
    finally:
        availability.app = original_app


def test_canonical_bundle_client_uses_ce133_or_ce146_and_builder_alpn(tmp_path):
    async def run():
        from pyjamaz.bundle import encode_bundle
        from test.test_bundle_submission import bundle_case
        server, client, service, target, _ = await nodes(tmp_path)
        try:
            value = package()
            await client.submit_work_package_bundle(target, 1, encode_bundle(value, [], [], []))
            assert service.authorized[-1][1:3] == (1, value)
            assert service.completed[-1] == (133, [b''])
            value, imports, proofs = bundle_case()
            bundle = encode_bundle(value, [b'abc'], imports, proofs)
            await client.submit_work_package_bundle(target, 0, bundle, {b'p' * 32: b'r' * 32})
            assert service.authorized[-1][1:] == (0, value, {b'p' * 32: b'r' * 32})
            assert service.completed[-1] == (146, [b'abc', b''.join(imports), encode_import_proofs(proofs)])
        finally:
            server.server.close()
    asyncio.run(run())


def test_up0_header_announcements_and_ce128_keep_existing_block_subscriber(tmp_path):
    async def run():
        from aioquic.asyncio.client import connect
        from jamcodec.base import JamBytes
        from jamcodec.decoding import decode_to_object
        from jamcodec.types import Vec
        from pyjamaz.models.block import Block, Extrinsic, Header
        server, client, _, target, _ = await nodes(tmp_path)
        blocks = [Block(Header.default(), Extrinsic.default()) for _ in range(3)]
        for index, block in enumerate(blocks):
            block.header.timeslot = index
            if index:
                block.header.parent = blocks[index - 1].header.hash
        by_hash = {block.header.hash: block for block in blocks}
        app = server.app
        app.working_state = SimpleNamespace(timeslot=SimpleNamespace(number=2))
        app.retrieve_block_hash = lambda slot: blocks[slot].header.hash if 0 <= slot <= 2 else None
        app.retrieve_block_by_hash = by_hash.get
        app.retrieve_block_header = lambda block_hash: by_hash[block_hash].header if block_hash in by_hash else None
        app.retrieve_finalized_head = lambda: blocks[0].header.hash
        try:
            async with connect('127.0.0.1', target.get_metadata_port(),
                               configuration=client._configuration(is_client=True),
                               create_protocol=wrap_protocol(client, ClientProtocol, target.ed25519)) as protocol:
                await protocol.open_stream_up_0()
                descending = await client.fetch_blocks(protocol, blocks[2].header.hash, 1, 2)
                assert descending == [blocks[2], blocks[1]]
                signal = await asyncio.wait_for(client.broadcaster.receive_stream.receive(), 1)
                decoded = decode_to_object(Vec(Block.to_codec_def()), JamBytes(signal.data))
                assert decoded == descending
                ascending = await client.fetch_blocks(protocol, blocks[0].header.hash, 0, 2)
                assert ascending == blocks[1:]
                await asyncio.wait_for(client.broadcaster.receive_stream.receive(), 1)
                await server.broadcast_block(blocks[2])
                signal = await asyncio.wait_for(client.broadcaster.receive_stream.receive(), 1)
                assert signal.topic == MESSAGE_TYPES.REQUESTED_BLOCKS
        finally:
            server.server.close()
    asyncio.run(run())
