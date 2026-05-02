import asyncio
import json
import logging
import re
import sys
from pathlib import Path
from typing import Any, Optional

from . import constants
from .workspace import Workspace, _new_id, _now

log = logging.getLogger("field_companion.call_helper")

SAFETY_REGEX = re.compile(
    r"\b(severe\s+neutropenia|febrile\s+neutropenia|neutropenia|thrombocytopenia|"
    r"atrial\s+fibrillation|afib|major\s+bleeding|haemorrhage|hemorrhage|"
    r"opportunistic\s+infection|pjp|sepsis)\b.*?\b("
    r"admitted|admission|hospitalised|hospitalized|hospital|icu|intensive\s+care|"
    r"died|death|fatal|transfused|transfusion)\b",
    re.IGNORECASE | re.DOTALL,
)

COMPLIANCE_LINE_REGEX = re.compile(
    r"\b(first[\s-]?line|1l|front[\s-]?line|frontline|treatment[\s-]?naive|"
    r"untreated|newly\s+diagnosed|upfront|before\s+(chemo|r-?chop|standard))\b",
    re.IGNORECASE,
)
COMPLIANCE_SOLICIT_REGEX = re.compile(
    r"\b(what\s+about|could\s+we|would\s+you|is\s+there\s+a\s+case|"
    r"what\s+if|hypothetically|in\s+theory|off[\s-]?label|unlicensed|"
    r"outside\s+the\s+indication|thinking\s+about|considering|looking\s+at)\b",
    re.IGNORECASE,
)


def _classify(utterance: str) -> dict[str, Any]:
    if SAFETY_REGEX.search(utterance):
        outcome_is_hospital = bool(
            re.search(r"\b(admitted|admission|hospital|icu)\b", utterance, re.IGNORECASE)
        )
        return {
            "category": "safety",
            "trigger_category": "hospitalisation" if outcome_is_hospital else "adverse_event",
            "severity": constants.FLAG_SEVERITY_WARNING,
            "matched_terms": ["regex_safety_match"],
            "rationale": "Detected a named adverse event together with a clinical outcome.",
        }
    if COMPLIANCE_LINE_REGEX.search(utterance) and COMPLIANCE_SOLICIT_REGEX.search(utterance):
        return {
            "category": "compliance",
            "abpi_clause": constants.ABPI_CLAUSE_11_2,
            "severity": constants.FLAG_SEVERITY_CRITICAL,
            "matched_terms": ["regex_compliance_match"],
            "rationale": "Detected a line-of-therapy phrase together with a solicitation framing.",
        }
    return {"category": "none"}


class CallHelperAgent:
    def __init__(self, workspace: Optional[Workspace] = None) -> None:
        self._workspace = workspace

    async def classify(self, utterance: str) -> dict[str, Any]:
        return _classify(utterance)

    async def handle_utterance(
        self,
        session_id: str,
        hcp_id: str,
        utterance: str,
    ) -> Optional[str]:
        if self._workspace is None:
            raise RuntimeError("workspace required for handle_utterance")

        verdict = await self.classify(utterance)
        category = verdict.get("category")

        if category == "safety":
            doc_id = _new_id("sr")
            await self._workspace.db[constants.COLL_SAFETY_REPORTS].insert_one({
                "_id": doc_id,
                "session_id": session_id,
                "hcp_id": hcp_id,
                "detected_at": _now(),
                "trigger_text": utterance,
                "trigger_category": verdict["trigger_category"],
                "severity": verdict["severity"],
                "suggested_followup": verdict["rationale"],
                "raw_classifier_output": verdict,
            })
            log.info("safety_report written: %s", doc_id)
            return doc_id

        if category == "compliance":
            doc_id = _new_id("cf")
            await self._workspace.db[constants.COLL_COMPLIANCE_FLAGS].insert_one({
                "_id": doc_id,
                "session_id": session_id,
                "hcp_id": hcp_id,
                "detected_at": _now(),
                "trigger_text": utterance,
                "abpi_clause": verdict["abpi_clause"],
                "rationale": verdict["rationale"],
                "severity": verdict["severity"],
                "raw_classifier_output": verdict,
            })
            log.info("compliance_flag written: %s", doc_id)
            return doc_id

        return None


async def cli_test() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    agent = CallHelperAgent()

    phrases = sys.argv[1:] or [
        "Look, the data's interesting, but I had a patient on Lymvora three weeks ago who developed severe neutropenia and we admitted her to hospital.",
        "Actually, while I have you, what about using it first-line in fit younger patients?",
        "What's the median PFS in AURORA-2 again?",
        "I've seen a bit of cytopenia with Lymvora but nothing I couldn't manage in clinic.",
    ]

    for phrase in phrases:
        print(f"\nUTTERANCE: {phrase}")
        verdict = await agent.classify(phrase)
        print(f"VERDICT:   {json.dumps(verdict, indent=2)}")


if __name__ == "__main__":
    asyncio.run(cli_test())
