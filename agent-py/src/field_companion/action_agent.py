import asyncio
import json
import logging
import os
from pathlib import Path
from typing import Any, Optional

import anthropic

from . import constants
from .workspace import Workspace, _new_id, _now

log = logging.getLogger("field_companion.action")

ACTION_SYSTEM_PROMPT = """You are a UK pharma medical affairs writer producing a post-call wrap-up for a sales rep who has just finished a face-to-face meeting with an oncologist.

You will receive:
1. The HCP profile.
2. The medicine in scope and its licensed indication.
3. The full transcript of the call (rep and HCP utterances in order).
4. Any safety reports detected during the call (adverse events with outcomes).
5. Any compliance flags detected during the call (off-label discussion triggers).

Your output is a single JSON object with these fields:
- "summary": 2-3 sentences summarising what was discussed. Factual, neutral, no marketing language. Max 80 words.
- "discussed_topics": a list of 2-4 short topic tags (max 4 words each) drawn from the transcript.
- "action_items": a list of EXACTLY 3 concrete next steps the rep should take. Each is one short sentence, action-oriented, starting with a verb. The first item must address the most urgent flag if any safety or compliance flag is present.
- "next_steps": one sentence describing when and how the rep should follow up. Max 20 words.

Rules:
- Do not invent facts not present in the transcript or profile.
- Do not promote off-label use. Treat any compliance flag as a serious item to flag to the rep, not to repeat as a recommendation.
- Plain prose only inside string values. No markdown, no emojis, no bullet characters inside strings.
- Return ONLY the JSON, no preamble.
"""


def _anthropic_client() -> anthropic.AsyncAnthropic:
    return anthropic.AsyncAnthropic(api_key=os.environ["ANTHROPIC_API_KEY"])


def _format_utterances(utterances: list[dict[str, Any]]) -> str:
    if not utterances:
        return "(no utterances captured)"
    lines = []
    for u in utterances:
        speaker = u.get("speaker", "?").upper()
        text = u.get("text", "")
        lines.append(f"{speaker}: {text}")
    return "\n".join(lines)


def _format_flags(flags: list[dict[str, Any]], kind: str) -> str:
    if not flags:
        return f"(no {kind} flags)"
    lines = []
    for f in flags:
        trig = f.get("trigger_text", "")
        rat = f.get("rationale", "")
        sev = f.get("severity", "")
        lines.append(f"- [{sev}] {trig} -- {rat}")
    return "\n".join(lines)


class ActionAgent:
    def __init__(self, workspace: Optional[Workspace] = None) -> None:
        self._workspace = workspace or Workspace()
        self._llm = _anthropic_client()

    async def _gather_session_state(self, session_id: str) -> dict[str, Any]:
        db = self._workspace.db
        session = await db[constants.COLL_CALL_SESSIONS].find_one({"_id": session_id})
        safety = await db[constants.COLL_SAFETY_REPORTS].find({"session_id": session_id}).to_list(length=20)
        compliance = await db[constants.COLL_COMPLIANCE_FLAGS].find({"session_id": session_id}).to_list(length=20)
        return {
            "session": session,
            "safety": safety,
            "compliance": compliance,
        }

    async def _compose_wrap(
        self,
        hcp_profile: dict[str, Any],
        product: dict[str, Any],
        utterances: list[dict[str, Any]],
        safety: list[dict[str, Any]],
        compliance: list[dict[str, Any]],
    ) -> dict[str, Any]:
        user_message = (
            f"HCP profile:\n{json.dumps(hcp_profile, default=str)[:3000]}\n\n"
            f"Medicine in scope:\n{json.dumps(product, default=str)[:1500]}\n\n"
            f"Call transcript:\n{_format_utterances(utterances)}\n\n"
            f"Safety reports:\n{_format_flags(safety, 'safety')}\n\n"
            f"Compliance flags:\n{_format_flags(compliance, 'compliance')}\n\n"
            "Compose the wrap-up now."
        )

        response = await self._llm.messages.create(
            model=constants.ANTHROPIC_MODEL,
            max_tokens=700,
            system=ACTION_SYSTEM_PROMPT,
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
            log.warning("finalize_call missing session_id or hcp_id: %s", request)
            return None

        log.info("processing finalize_call session=%s hcp=%s", session_id, hcp_id)

        db = self._workspace.db
        hcp_profile = await db[constants.COLL_HCP_PROFILES].find_one({"_id": hcp_id}) or {}
        product = await db[constants.COLL_PRODUCT_AUTHORISATIONS].find_one({"_id": "prod_lymvora"}) or {}

        state = await self._gather_session_state(session_id)
        session_doc = state["session"] or {}
        utterances = session_doc.get("utterances", [])
        safety = state["safety"]
        compliance = state["compliance"]

        try:
            wrap = await self._compose_wrap(hcp_profile, product, utterances, safety, compliance)
        except Exception:
            log.exception("wrap composition failed; returning fallback")
            wrap = {
                "summary": "Call completed. Auto-summary unavailable.",
                "discussed_topics": [],
                "action_items": [
                    "Review call transcript in the wrap view.",
                    "Capture any commitments manually.",
                    "Schedule follow-up with the HCP.",
                ],
                "next_steps": "Follow up within one week.",
            }

        rep_id = session_doc.get("rep_id", "rep_demo")
        note_id = _new_id("note")
        await db[constants.COLL_CRM_NOTES].insert_one({
            "_id": note_id,
            "session_id": session_id,
            "hcp_id": hcp_id,
            "rep_id": rep_id,
            "created_at": _now(),
            "summary": wrap.get("summary", ""),
            "discussed_topics": wrap.get("discussed_topics", []),
            "action_items": wrap.get("action_items", []),
            "linked_safety_report_ids": [s.get("_id") for s in safety],
            "linked_compliance_flag_ids": [c.get("_id") for c in compliance],
            "next_steps": wrap.get("next_steps"),
        })
        log.info("crm_note written: %s", note_id)

        result_payload = {
            "crm_note_id": note_id,
            "summary": wrap.get("summary", ""),
            "action_items": wrap.get("action_items", []),
            "discussed_topics": wrap.get("discussed_topics", []),
            "next_steps": wrap.get("next_steps", ""),
            "safety_count": len(safety),
            "compliance_count": len(compliance),
        }

        msg_id = await self._workspace.emit(
            constants.WS_FINALIZE_RESULT,
            session_id,
            result_payload,
            hcp_id=hcp_id,
        )
        log.info("finalize_result emitted: %s", msg_id)
        return msg_id

    async def run(self) -> None:
        log.info("action agent watching for %s", constants.WS_FINALIZE_CALL)
        async for request in self._workspace.watch(constants.WS_FINALIZE_CALL):
            try:
                await self.handle_request(request)
            except Exception:
                log.exception("finalize handling failed")


async def cli_test() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parents[3] / "agent-py" / ".env.local")

    workspace = Workspace()
    db = workspace.db

    fake_session_id = "session_test_action"
    await db[constants.COLL_CALL_SESSIONS].update_one(
        {"_id": fake_session_id},
        {"$set": {
            "_id": fake_session_id,
            "hcp_id": "hcp_rose",
            "rep_id": "rep_demo",
            "status": "completed",
            "started_at": _now(),
            "ended_at": _now(),
            "utterances": [
                {"speaker": "rep", "text": "Thanks for making time today, Dr Rose."},
                {"speaker": "hcp", "text": "I had a patient on Lymvora three weeks ago who developed severe neutropenia and we admitted her to hospital."},
                {"speaker": "rep", "text": "I'll flag that with our medical information team and circle back."},
                {"speaker": "hcp", "text": "Actually, while I have you, what about using it first-line in fit younger patients?"},
                {"speaker": "rep", "text": "First-line use sits outside the licensed indication. I can't discuss that, but I'll send a medical information enquiry."},
            ],
        }},
        upsert=True,
    )

    await db[constants.COLL_SAFETY_REPORTS].insert_one({
        "_id": _new_id("sr"),
        "session_id": fake_session_id,
        "hcp_id": "hcp_rose",
        "detected_at": _now(),
        "trigger_text": "I had a patient on Lymvora three weeks ago who developed severe neutropenia and we admitted her to hospital.",
        "trigger_category": "hospitalisation",
        "severity": "warning",
        "suggested_followup": "Detected named adverse event with hospital outcome.",
    })
    await db[constants.COLL_COMPLIANCE_FLAGS].insert_one({
        "_id": _new_id("cf"),
        "session_id": fake_session_id,
        "hcp_id": "hcp_rose",
        "detected_at": _now(),
        "trigger_text": "what about using it first-line in fit younger patients?",
        "abpi_clause": constants.ABPI_CLAUSE_11_2,
        "rationale": "First-line use solicitation falls outside Lymvora's second-line+ indication.",
        "severity": "critical",
    })

    agent = ActionAgent(workspace=workspace)
    fake_request = {
        "_id": "ws_test_action",
        "type": constants.WS_FINALIZE_CALL,
        "session_id": fake_session_id,
        "payload": {"hcp_id": "hcp_rose"},
    }
    msg_id = await agent.handle_request(fake_request)
    print(f"\nemitted finalize_result message id: {msg_id}")

    result = await db[constants.COLL_AGENT_WORKSPACE].find_one({"_id": msg_id})
    print("\nwrap content:")
    print(json.dumps(result.get("payload"), indent=2, default=str))

    await workspace.close()


if __name__ == "__main__":
    asyncio.run(cli_test())
