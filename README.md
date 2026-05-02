# Field Companion

Voice-first agentic assistant for UK pharma sales reps. Pre-call prep, silent in-call notetaking, post-call CRM write-up — all driven by four specialised agents communicating exclusively through MongoDB Atlas change streams.

Built for the **MongoDB Agentic Evolution Hackathon — Multi-Agent Collaboration track**.

## The wedge

Reps make 5-15 face-to-face calls per week with HCPs. They prep in 20 minutes the night before, take notes on paper, and write up CRM entries hours later. Field Companion replaces all three moments:

1. **Pre-call** — rep speaks "prep me", hears a 30-second brief grounded in past call history retrieved by vector search
2. **During-call** — silent notetaker. No interruptions. Background classifier flags adverse events and off-label discussion as awareness banners (not enforcement)
3. **Post-call** — rep taps end, gets a CRM-ready note, three action items, and linked safety/compliance flags within 20 seconds

We don't enforce ABPI Code or pharmacovigilance. Compliance and PV remain the company's responsibility. Field Companion just reduces the chance the rep walks out having missed something worth capturing.

## The four agents

All four communicate exclusively through MongoDB change streams on the `agent_workspace` collection. No direct function calls between them.

| Agent | Trigger | Tools | Writes |
|---|---|---|---|
| **Voice Agent** | LiveKit room connect | Deepgram STT, Anthropic Claude Sonnet 4.5, ElevenLabs TTS | Emits `brief_request` / `finalize_call` / `utterance` |
| **Briefing Agent** | `brief_request` change stream | Voyage AI embeddings, Atlas `$vectorSearch` over `call_history`, Anthropic | Emits `brief_result` |
| **Call Helper Agent** | `utterance` change stream | Regex pre-filter classifier (LLM verification scaffolded but disabled) | Writes `safety_reports`, `compliance_flags` |
| **Action Agent** | `finalize_call` change stream | Anthropic Claude Sonnet 4.5 | Writes `crm_notes`, emits `finalize_result` |

## MongoDB doing real work

This is not decorative MongoDB usage. Each feature earns its place:

- **`$vectorSearch`** — Briefing Agent retrieves the 3 most semantically relevant past memorable points for the upcoming HCP, ranked by cosine similarity over Voyage `voyage-3` embeddings (1024-dim). Filtered by `hcp_id`.
- **Change streams** — the wake-up signal. Each agent runs as an `asyncio` task watching a filtered change stream on `agent_workspace`. When a message of the right type lands, the agent fires.
- **Document model** — HCP profiles, product authorisations, and call sessions are nested documents with arrays (interactions, prescribing patterns, utterances appending live).
- **Linked references** — CRM notes carry `linked_safety_report_ids` and `linked_compliance_flag_ids` arrays so the post-call view can render flag chips next to the action items that address them.

## The 10 collections

| Collection | Purpose |
|---|---|
| `hcp_profiles` | Per-HCP profile, prescribing pattern, communication style |
| `product_authorisations` | Medicine licence info — drives the off-label compliance check |
| `call_history` | Past memorable points + 1024-dim Voyage embeddings (vector indexed) |
| `call_sessions` | One doc per call with utterances appending live |
| `agent_workspace` | Inter-agent message bus (change streams) |
| `safety_reports` | Adverse event detections from Call Helper |
| `compliance_flags` | ABPI Code Clause 11.2 detections from Call Helper |
| `crm_notes` | Final CRM write-up with linked flag IDs |
| `email_drafts` | Optional follow-up draft (cut for time) |
| `medical_knowledge` | Reserved for medical knowledge retrieval (cut for time) |

## Tech stack

- **Backend** — Python 3.13, single async process, PyMongo direct (no LangGraph, no LangChain framework wrapper)
- **Voice** — LiveKit Agents 1.5, Deepgram Nova-3 STT, Anthropic Claude Sonnet 4.5 LLM, ElevenLabs TTS
- **Database** — MongoDB Atlas M10, MongoDB 8.0, eu-west-2 (London)
- **Embeddings** — Voyage AI `voyage-3`
- **Real-time classifier** — strict regex pre-filter (LLM scaffolded, disabled for reliability)
- **Frontend** — Next.js 15 + LiveKit React Components

## Demo flow

1. Dashboard shows Dr Eleanor Rose, Royal Marsden Sutton, 2pm, lymphoma.
2. Rep taps her card and speaks "Prep me." Within 10s, four cards animate in and the agent speaks the 30-second brief.
3. Rep taps "I'm on the call." Consent timestamp visible.
4. Dr Rose says: *"I had a patient on Lymvora three weeks ago who developed severe neutropenia and we admitted her to hospital."* — yellow awareness banner appears within 2s. Document appears in `safety_reports`.
5. Dr Rose says: *"What about using it first-line in fit younger patients?"* — red awareness banner. Document in `compliance_flags`.
6. Rep taps "End call." Within 20s: panels populate — CRM note, three action items, linked flag chips.
7. Atlas tab visible throughout, showing documents accumulating live across `agent_workspace`, `safety_reports`, `compliance_flags`, `crm_notes`. **The multi-agent collaboration on screen.**

## Running locally

```bash
cd agent-py
uv sync
uv run python -m field_companion.main          # background agents
uv run python -m field_companion.voice_agent dev   # voice agent
```

Frontend:
```bash
cd frontend
pnpm install
pnpm dev
```

Environment variables in `agent-py/.env.local` (see `.env.example`).

## Status

- ✅ Four agents written and individually tested end-to-end
- ✅ Vector search retrieving semantically relevant call history
- ✅ Strict-mode classifier passing on planted phrases (5/5)
- ✅ CRM notes with linked safety/compliance IDs
- ✅ Change-stream message bus with reconnection handling
- ✅ Console-mode voice round-trip proven

## Licence

MIT (see `LICENSE`).
