import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pymongo import AsyncMongoClient

from . import constants

ENV_PATH = Path(__file__).resolve().parents[3] / "agent-py" / ".env.local"
load_dotenv(ENV_PATH)

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("field_companion.api")

app = FastAPI(title="Field Companion API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_client = AsyncMongoClient(os.environ["MONGODB_URI"])
_db = _client[os.environ.get("MONGODB_DB", constants.DB_NAME)]


def _serialise(doc: Any) -> Any:
    if isinstance(doc, datetime):
        return doc.isoformat()
    if isinstance(doc, dict):
        return {k: _serialise(v) for k, v in doc.items()}
    if isinstance(doc, list):
        return [_serialise(item) for item in doc]
    return doc


@app.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/hcp/{hcp_id}")
async def get_hcp(hcp_id: str) -> dict[str, Any]:
    doc = await _db[constants.COLL_HCP_PROFILES].find_one({"_id": hcp_id})
    if doc is None:
        raise HTTPException(status_code=404, detail=f"hcp not found: {hcp_id}")
    return _serialise(doc)


@app.get("/api/flags/{session_id}")
async def get_flags(session_id: str) -> dict[str, Any]:
    safety = await _db[constants.COLL_SAFETY_REPORTS].find(
        {"session_id": session_id}
    ).sort("detected_at", 1).to_list(length=50)
    compliance = await _db[constants.COLL_COMPLIANCE_FLAGS].find(
        {"session_id": session_id}
    ).sort("detected_at", 1).to_list(length=50)
    return {
        "safety": [_serialise(s) for s in safety],
        "compliance": [_serialise(c) for c in compliance],
    }


@app.get("/api/brief/{session_id}")
async def get_brief(session_id: str) -> dict[str, Any]:
    doc = await _db[constants.COLL_AGENT_WORKSPACE].find_one(
        {"session_id": session_id, "type": constants.WS_BRIEF_RESULT},
        sort=[("created_at", -1)],
    )
    if doc is None:
        return {"status": "pending"}
    return {"status": "ready", "brief": _serialise(doc.get("payload", {}))}


@app.get("/api/wrap/{session_id}")
async def get_wrap(session_id: str) -> dict[str, Any]:
    note = await _db[constants.COLL_CRM_NOTES].find_one({"session_id": session_id})
    if note is None:
        return {"status": "pending"}
    flags = await get_flags(session_id)
    return {
        "status": "ready",
        "note": _serialise(note),
        "flags": flags,
    }


@app.get("/api/transcript/{session_id}")
async def get_transcript(session_id: str) -> dict[str, Any]:
    session = await _db[constants.COLL_CALL_SESSIONS].find_one({"_id": session_id})
    utterances = (session or {}).get("utterances", [])
    return {"utterances": _serialise(utterances)}
