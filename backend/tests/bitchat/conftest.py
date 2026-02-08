"""BitChat-specific fixtures."""

import pytest
from sqlalchemy import delete

from server.database import AsyncSessionLocal, engine
from server.models.database import Message, Peer


@pytest.fixture(autouse=True)
async def ensure_bitchat_tables():
    """
    Create only the tables needed by BitChat tests for sqlite compatibility.
    """
    async with engine.begin() as conn:
        await conn.run_sync(Peer.__table__.create, checkfirst=True)
        await conn.run_sync(Message.__table__.create, checkfirst=True)
    yield


@pytest.fixture(autouse=True)
async def isolate_bitchat_tables():
    """
    Keep BitChat tests deterministic by clearing peer/message state.
    """
    async with AsyncSessionLocal() as session:
        await session.execute(delete(Message))
        await session.execute(delete(Peer))
        await session.commit()
    yield
