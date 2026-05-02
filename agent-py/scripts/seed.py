import json
import logging
import os
import sys
from pathlib import Path
from typing import Any

import voyageai
from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.errors import PyMongoError

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("seed")

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "fixtures"
ENV_PATH = ROOT / "agent-py" / ".env.local"

VOYAGE_MODEL = "voyage-3"
EMBEDDING_DIMS = 1024

JUNK_COLLECTIONS = ("users", "sessions", "memories", "knowledge", "orders")


def load_env() -> None:
    if not ENV_PATH.exists():
        log.error("missing env file at %s", ENV_PATH)
        sys.exit(1)
    load_dotenv(ENV_PATH)
    for key in ("MONGODB_URI", "MONGODB_DB", "VOYAGE_API_KEY"):
        if not os.environ.get(key):
            log.error("missing env var: %s", key)
            sys.exit(1)


def load_fixture(name: str) -> list[dict[str, Any]]:
    path = FIXTURES / name
    if not path.exists():
        log.error("missing fixture: %s", path)
        sys.exit(1)
    with path.open() as f:
        return json.load(f)


def embed_call_history(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    client = voyageai.Client(api_key=os.environ["VOYAGE_API_KEY"])
    texts = [r["text"] for r in records]
    log.info("embedding %d call_history records via %s", len(texts), VOYAGE_MODEL)
    result = client.embed(texts, model=VOYAGE_MODEL, input_type="document")
    if len(result.embeddings) != len(records):
        raise RuntimeError(
            f"voyage returned {len(result.embeddings)} embeddings for {len(records)} records"
        )
    for record, vec in zip(records, result.embeddings, strict=True):
        if len(vec) != EMBEDDING_DIMS:
            raise RuntimeError(
                f"unexpected embedding dim {len(vec)} (expected {EMBEDDING_DIMS})"
            )
        record["embedding"] = vec
    return records


def reset_collection(db, name: str, docs: list[dict[str, Any]]) -> None:
    db.drop_collection(name)
    if docs:
        db[name].insert_many(docs)
    log.info("reset %s with %d docs", name, len(docs))


def drop_junk(db) -> None:
    existing = set(db.list_collection_names())
    for name in JUNK_COLLECTIONS:
        if name in existing:
            db.drop_collection(name)
            log.info("dropped junk collection: %s", name)


def main() -> None:
    load_env()

    hcp_profiles = load_fixture("hcp_profiles.json")
    product_authorisations = load_fixture("product_authorisations.json")
    call_history = load_fixture("call_history.json")

    call_history = embed_call_history(call_history)

    client: MongoClient = MongoClient(os.environ["MONGODB_URI"])
    db = client[os.environ["MONGODB_DB"]]

    try:
        drop_junk(db)
        reset_collection(db, "hcp_profiles", hcp_profiles)
        reset_collection(db, "product_authorisations", product_authorisations)
        reset_collection(db, "call_history", call_history)
        log.info("seed complete")
    except PyMongoError:
        log.exception("seed failed")
        sys.exit(1)
    finally:
        client.close()


if __name__ == "__main__":
    main()
