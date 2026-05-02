from datetime import datetime, timezone
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class MongoModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True, arbitrary_types_allowed=True)


class Utterance(MongoModel):
    speaker: Literal["rep", "hcp"]
    text: str
    started_at: datetime
    ended_at: Optional[datetime] = None


class CallSession(MongoModel):
    id: str = Field(alias="_id")
    hcp_id: str
    rep_id: str
    status: Literal["scheduled", "in_progress", "completed"] = "scheduled"
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    consent_recorded_at: Optional[datetime] = None
    location: Optional[str] = None
    topic: Optional[str] = None
    utterances: list[Utterance] = Field(default_factory=list)


class WorkspaceMessage(MongoModel):
    id: str = Field(alias="_id")
    type: Literal[
        "brief_request",
        "brief_result",
        "finalize_call",
        "finalize_result",
    ]
    session_id: str
    hcp_id: Optional[str] = None
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utcnow)
    consumed_at: Optional[datetime] = None


class BriefResultPayload(MongoModel):
    headline: str
    last_interaction_summary: str
    recommended_opener: str
    key_concerns: list[str]
    retrieved_history_ids: list[str] = Field(default_factory=list)


class SafetyReport(MongoModel):
    id: str = Field(alias="_id")
    session_id: str
    hcp_id: str
    detected_at: datetime = Field(default_factory=utcnow)
    trigger_text: str
    trigger_category: Literal[
        "adverse_event",
        "serious_adverse_event",
        "hospitalisation",
        "death",
    ]
    severity: Literal["info", "warning", "critical"]
    suggested_followup: str
    raw_classifier_output: dict[str, Any] = Field(default_factory=dict)


class ComplianceFlag(MongoModel):
    id: str = Field(alias="_id")
    session_id: str
    hcp_id: str
    detected_at: datetime = Field(default_factory=utcnow)
    trigger_text: str
    abpi_clause: Literal["ABPI Code Clause 11.1", "ABPI Code Clause 11.2"]
    rationale: str
    severity: Literal["info", "warning", "critical"]
    raw_classifier_output: dict[str, Any] = Field(default_factory=dict)


class CRMNote(MongoModel):
    id: str = Field(alias="_id")
    session_id: str
    hcp_id: str
    rep_id: str
    created_at: datetime = Field(default_factory=utcnow)
    summary: str
    discussed_topics: list[str]
    action_items: list[str]
    linked_safety_report_ids: list[str] = Field(default_factory=list)
    linked_compliance_flag_ids: list[str] = Field(default_factory=list)
    next_steps: Optional[str] = None


class EmailDraft(MongoModel):
    id: str = Field(alias="_id")
    session_id: str
    hcp_id: str
    rep_id: str
    created_at: datetime = Field(default_factory=utcnow)
    subject: str
    body: str
    status: Literal["draft", "sent"] = "draft"
