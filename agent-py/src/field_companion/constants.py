from typing import Final

DB_NAME: Final = "field_companion"

COLL_HCP_PROFILES: Final = "hcp_profiles"
COLL_PRODUCT_AUTHORISATIONS: Final = "product_authorisations"
COLL_MEDICAL_KNOWLEDGE: Final = "medical_knowledge"
COLL_CALL_HISTORY: Final = "call_history"
COLL_CALL_SESSIONS: Final = "call_sessions"
COLL_AGENT_WORKSPACE: Final = "agent_workspace"
COLL_SAFETY_REPORTS: Final = "safety_reports"
COLL_COMPLIANCE_FLAGS: Final = "compliance_flags"
COLL_CRM_NOTES: Final = "crm_notes"
COLL_EMAIL_DRAFTS: Final = "email_drafts"

VECTOR_INDEX_CALL_HISTORY: Final = "call_history_vector"
EMBEDDING_DIMS: Final = 1024
VOYAGE_MODEL: Final = "voyage-3"

WS_BRIEF_REQUEST: Final = "brief_request"
WS_BRIEF_RESULT: Final = "brief_result"
WS_UTTERANCE: Final = "utterance"
WS_FINALIZE_CALL: Final = "finalize_call"
WS_FINALIZE_RESULT: Final = "finalize_result"

CALL_MODE_PRE: Final = "pre_call"
CALL_MODE_DURING: Final = "during_call"
CALL_MODE_POST: Final = "post_call"

UTTERANCE_SPEAKER_REP: Final = "rep"
UTTERANCE_SPEAKER_HCP: Final = "hcp"

FLAG_SEVERITY_INFO: Final = "info"
FLAG_SEVERITY_WARNING: Final = "warning"
FLAG_SEVERITY_CRITICAL: Final = "critical"

ABPI_CLAUSE_11_1: Final = "ABPI Code Clause 11.1"
ABPI_CLAUSE_11_2: Final = "ABPI Code Clause 11.2"

ANTHROPIC_MODEL: Final = "claude-sonnet-4-5-20250929"
