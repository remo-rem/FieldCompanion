import asyncio
import logging
import os
import uuid
from collections.abc import AsyncIterator
from datetime import datetime, timezone
from typing import Any, Optional

from pymongo import AsyncMongoClient
from pymongo.errors import PyMongoError

from . import constants

log = logging.getLogger("field_companion.workspace")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


class Workspace:
    def __init__(
        self,
        mongo_uri: Optional[str] = None,
        db_name: Optional[str] = None,
    ) -> None:
        uri = mongo_uri or os.environ["MONGODB_URI"]
        name = db_name or os.environ.get("MONGODB_DB", constants.DB_NAME)
        self._client: AsyncMongoClient = AsyncMongoClient(uri)
        self._db = self._client[name]

    @property
    def db(self):
        return self._db

    async def emit(
        self,
        message_type: str,
        session_id: str,
        payload: dict[str, Any],
        hcp_id: Optional[str] = None,
    ) -> str:
        doc = {
            "_id": _new_id("ws"),
            "type": message_type,
            "session_id": session_id,
            "hcp_id": hcp_id,
            "payload": payload,
            "created_at": _now(),
            "consumed_at": None,
        }
        await self._db[constants.COLL_AGENT_WORKSPACE].insert_one(doc)
        log.info("emit %s for session=%s id=%s", message_type, session_id, doc["_id"])
        return doc["_id"]

    async def watch(
        self,
        message_type: str,
        session_id: Optional[str] = None,
    ) -> AsyncIterator[dict[str, Any]]:
        match: dict[str, Any] = {
            "operationType": "insert",
            "fullDocument.type": message_type,
        }
        if session_id is not None:
            match["fullDocument.session_id"] = session_id
        pipeline = [{"$match": match}]
        coll = self._db[constants.COLL_AGENT_WORKSPACE]

        while True:
            try:
                stream = await coll.watch(pipeline, full_document="updateLookup")
                async with stream:
                    log.info("watching %s session=%s", message_type, session_id)
                    async for change in stream:
                        doc = change.get("fullDocument")
                        if doc is None:
                            continue
                        log.info(
                            "received %s for session=%s id=%s",
                            message_type,
                            doc.get("session_id"),
                            doc.get("_id"),
                        )
                        yield doc
            except PyMongoError as exc:
                log.warning("change stream error, reconnecting in 1s: %s", exc)
                await asyncio.sleep(1)
            except asyncio.CancelledError:
                log.info("watch cancelled for %s", message_type)
                raise

    async def mark_consumed(self, message_id: str) -> None:
        await self._db[constants.COLL_AGENT_WORKSPACE].update_one(
            {"_id": message_id},
            {"$set": {"consumed_at": _now()}},
        )

    async def close(self) -> None:
        await self._client.close()
