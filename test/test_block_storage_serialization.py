import asyncio

from pyjamaz.app import PyjamazApp
from pyjamaz.models.block import Block, Extrinsic, Header
from pyjamaz.storage import InMemoryStorageEngine


def test_store_block_serializes_each_sibling_once_and_keeps_both_indexes(monkeypatch):
    app = PyjamazApp.__new__(PyjamazApp)
    app.block_db = InMemoryStorageEngine()
    first = Block(Header.default(), Extrinsic.default())
    second = Block(Header.default(), Extrinsic.default())
    second.header.author_index += 1
    expected = [block.to_jam_bytes().to_bytes() for block in (first, second)]
    serializations = []
    original = Block.to_jam_bytes

    def serialize(block):
        serializations.append(block)
        return original(block)

    monkeypatch.setattr(Block, "to_jam_bytes", serialize)

    async def store():
        await app.store_block(first)
        await app.store_block(second)

    asyncio.run(store())

    assert serializations == [first, second]
    for block, canonical in zip((first, second), expected):
        assert app.retrieve_block_by_hash(block.header.hash).to_jam_bytes().to_bytes() == canonical
    assert app.retrieve_block(second.header.timeslot).to_jam_bytes().to_bytes() == expected[1]
