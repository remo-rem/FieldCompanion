import asyncio
import json
import logging
import os
from pathlib import Path
from typing import Any, Optional

import anthropic
import voyageai

from . import constants
from .workspace import Workspace

log = logging.getLogger("field_companion.briefing")

BRIEF_SYSTEM_PROMPT = """You are a UK pharma medical affairs writer composing a 30-second pre-call brief for a sales rep. The rep is about to walk into a face-to-face call with an oncologist.

You will receive:
1. A structured profile of the HCP (qualifications, communication style, prescribing patterns, key concerns).
2. The medicine in scope and its licensed indication.
3. A short list of memorable points retrieved from past calls with this HCP, ranked by semantic relevance.

Your output is a single JSON object with these fields:
- "headline": one sentence summarising who the HCP is and the meeting focus. Max 25 words.
- "last_interaction_summary": one or two sentences describing what happened last time, drawing from the retrieved past points. Max 40 words.
- "recommended_opener": one sentence the rep can say to start the call, grounded in something specific from the retrieved past points. Max 25 words.
- "key_concerns": a list of 2-3 short phrases (max 6 words each) capturing what the HCP is likely to push on.

Do not invent facts. Do not promote off-label use. Stay within the licensed indication. Plain prose only — no markdown, no emojis, no lists inside string values. Return ONLY the JSON, no preamble.
"""


def _voyage_client() -> voyageai.Client:
    return voyageai.Client(api_key=os.environ["VOYAGE_API_KEY"])


def _anthropic_client() -> anthropic.AsyncAnthropic:
    return anthropic.AsyncAnthropic(api_key=os.environ["ANTHROPIC_API_KEY"])


async def _embed_query(text: str) -> list[float]:
    def _sync_embed() -> list[float]:
        client = _voyage_client()
        result = client.embed([text], model=constants.VOYAGE_MODEL, input_type="query")
        return result.embeddings[0]

    return await asyncio.to_thread(_sync_embed)


class BriefingAgent:
    def __init__(self, workspace: Optional[Workspace] = None) -> None:
        self._workspace = workspace or Workspace()
        self._llm = _anthropic_client()

    async def _retrieve_history(self, hcp_id: str, query: str, limit: int = 3) -> list[dict[str, Any]]:
        query_vec = await _embed_query(query)
        pipeline = [
            {
                "$vectorSearch": {
                    "index": constants.VECTOR_INDEX_CALL_HISTORY,
                    "path": "embedding",
                    "queryVector": query_vec,
                    "numCandidates": 50,
                    "limit": limit,
                    "filter": {"hcp_id": hcp_id},
                }
            },
            {
                "$project": {
                    "_id": 1,
                    "topic": 1,
                    "interaction_date": 1,
                    "text": 1,
                    "score": {"$meta": "vectorSearchScore"},
                }
            },
        ]
        coll = self._workspace.db[constants.COLL_CALL_HISTORY]
        cursor = await coll.aggregate(pipeline)
        return await cursor.to_list(length=limit)

    async def _compose_brief(
        self,
        hcp_profile: dict[str, Any],
        product: dict[str, Any],
        history: list[dict[str, Any]],
    ) -> dict[str, Any]:
        history_lines = "\n".join(
            f"- ({item.get('topic', 'general')}, {item.get('interaction_date', '?')[:10]}) {item.get('text', '')}"
            for item in history
        )
        user_message = (
            f"HCP profile:\n{json.dumps(hcp_profile, default=str)[:3500]}\n\n"
            f"Medicine in scope:\n{json.dumps(product, default=str)[:2000]}\n\n"
            f"Retrieved past memorable points:\n{history_lines or 'None on file.'}\n\n"
            "Compose the brief now."
        )

        response = await self._llm.messages.create(
            model=constants.ANTHROPIC_MODEL,
            max_tokens=600,
            system=BRIEF_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
        )

        text = response.content[0].text if response.content else "{}"
        text = text.strip()
        if text.startswith("```"):
            text = text.split("```", 2)[1]
            if text.startswith("json"):
                text = text[4:]
            text = text.strip()
        return json.loads(text)

    async def handle_request(self, request: dict[str, Any]) -> Optional[str]:
        session_id = request.get("session_id")
        payload = request.get("payload", {})
        hcp_id = payload.get("hcp_id") or request.get("hcp_id")

        if not session_id or not hcp_id:
            log.warning("brief_request missing session_id or hcp_id: %s", request)
            return None

        log.info("processing brief_request session=%s hcp=%s", session_id, hcp_id)

        hcp_profile = await self._workspace.db[constants.COLL_HCP_PROFILES].find_one({"_id": hcp_id})
        if not hcp_profile:
            log.error("hcp not found: %s", hcp_id)
            return None

        product = await self._workspace.db[constants.COLL_PRODUCT_AUTHORISATIONS].find_one(
            {"_id": "prod_lymvora"}
        ) or {}

        topic = hcp_profile.get("next_call", {}).get("topic", "")
        retrieval_query = (
            f"{hcp_profile.get('full_name', '')} concerns about "
            f"{product.get('brand_name', 'the medicine')}: {topic}"
        )
        history = await self._retrieve_history(hcp_id, retrieval_query)

        try:
            brief = await self._compose_brief(hcp_profile, product, history)
        except Exception:
            log.exception("brief composition failed; returning fallback")
            brief = {
                "headline": f"{hcp_profile.get('full_name', 'HCP')} — {topic or 'next call'}.",
                "last_interaction_summary": (
                    history[0].get("text", "") if history else "No prior interactions logged."
                ),
                "recommended_opener": "Thanks for making time today. Where would you like to start?",
                "key_concerns": hcp_profile.get("key_concerns", [])[:3],
            }

        brief["retrieved_history_ids"] = [h.get("_id") for h in history if h.get("_id")]

        msg_id = await self._workspace.emit(
            constants.WS_BRIEF_RESULT,
            session_id,
            brief,
            hcp_id=hcp_id,
        )
        log.info("brief_result emitted: %s", msg_id)
        return msg_id

    async def run(self) -> None:
        log.info("briefing agent watching for %s", constants.WS_BRIEF_REQUEST)
        async for request in self._workspace.watch(constants.WS_BRIEF_REQUEST):
            try:
                await self.handle_request(request)
            except Exception:
                log.exception("brief handling failed")


async def cli_test() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parents[3] / "agent-py" / ".env.local")

    agent = BriefingAgent()

    fake_request = {
        "_id": "ws_test_brief",
        "type": constants.WS_BRIEF_REQUEST,
        "session_id": "session_test_brief",
        "payload": {"hcp_id": "hcp_rose"},
    }

    msg_id = await agent.handle_request(fake_request)
    print(f"\nemitted brief_result message id: {msg_id}")

    result = await agent._workspace.db[constants.COLL_AGENT_WORKSPACE].find_one({"_id": msg_id})
    print("\nbrief content:")
    print(json.dumps(result.get("payload"), indent=2, default=str))

    await agent._workspace.close()


if __name__ == "__main__":
    asyncio.run(cli_test())
