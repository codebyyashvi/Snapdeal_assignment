import logging

from pymongo import AsyncMongoClient

from . import config

log = logging.getLogger("kam.db")

_client: AsyncMongoClient | None = None
_db = None


async def connect() -> None:
    global _client, _db
    if not config.MONGO_URI:
        return
    try:
        _client = AsyncMongoClient(config.MONGO_URI, serverSelectionTimeoutMS=6000)
        await _client.admin.command("ping")
        _db = _client[config.MONGO_DB]
        log.info("MongoDB connected")
    except Exception as e:  # noqa: BLE001 - app still works without persistence
        log.warning("MongoDB unavailable, running in-memory only: %s", e)
        _db = None


def enabled() -> bool:
    return _db is not None


async def save_session(session: dict) -> None:
    if _db is None:
        return
    try:
        await _db.sessions.replace_one({"_id": session["id"]}, {**session, "_id": session["id"]}, upsert=True)
    except Exception as e:  # noqa: BLE001
        log.warning("save_session failed: %s", e)


async def last_completed_session(seller_id: str) -> dict | None:
    if _db is None:
        return None
    try:
        return await _db.sessions.find_one(
            {"seller_id": seller_id, "summary": {"$ne": None}}, sort=[("ended_at", -1)]
        )
    except Exception as e:  # noqa: BLE001
        log.warning("last_completed_session failed: %s", e)
        return None


async def clear_sessions(seller_id: str) -> int:
    if _db is None:
        return 0
    result = await _db.sessions.delete_many({"seller_id": seller_id})
    return result.deleted_count


async def list_sessions(seller_id: str, limit: int = 10) -> list[dict]:
    if _db is None:
        return []
    cursor = _db.sessions.find(
        {"seller_id": seller_id, "summary": {"$ne": None}},
        {"transcript": 0},
        sort=[("ended_at", -1)],
        limit=limit,
    )
    return [doc async for doc in cursor]
