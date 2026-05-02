import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from dotenv import load_dotenv
from livekit.agents import (
    Agent,
    AgentServer,
    AgentSession,
    ChatContext,
    JobContext,
    JobProcess,
    RunContext,
    TurnHandlingOptions,
    cli,
    function_tool,
    room_io,
)
from livekit.plugins import ai_coustics, anthropic, deepgram, elevenlabs, silero
from livekit.plugins.turn_detector.multilingual import MultilingualModel

from . import constants
from .main import start_background_agents
from .workspace import Workspace

ENV_PATH = Path(__file__).resolve().parents[3] / "agent-py" / ".env.local"
load_dotenv(ENV_PATH)

log = logging.getLogger("field_companion.voice_agent")

DEFAULT_HCP_ID = "hcp_rose"
WAIT_FOR_RESULT_TIMEOUT_S = 25


def _now_utc() -> datetime:
    return datetime.now(tz=timezone.utc)


class FieldCompanionAgent(Agent):
    """One agent, three demo beats. Tool selection driven by what the rep says."""

    def __init__(
        self,
        *,
        chat_ctx: ChatContext,
        workspace: Workspace,
        session_id: str,
        hcp_id: str,
        mode: str,
    ) -> None:
        super().__init__(
            chat_ctx=chat_ctx,
            instructions=(
                "You are Field Companion, a voice assistant for a UK pharma sales rep. "
                "The rep is preparing for a face-to-face call with Dr Eleanor Rose, "
                "consultant medical oncologist at Royal Marsden Sutton. The medicine in "
                "scope is Lymvora.\n\n"
                "You decide which tool to call based on what the rep says:\n"
                "1. If the rep asks you to prep, brief, or summarise before the call "
                "(e.g. 'prep me', 'brief me', 'what should I know'), call the get_brief tool. "
                "Then deliver the brief in calm spoken English.\n"
                "2. If the rep tells you something the doctor said during the call "
                "(e.g. 'she said...', 'the doctor mentioned...', 'I just heard her say...'), "
                "call the flag_utterance tool with the exact words. Acknowledge briefly "
                "after the tool returns, but keep it short.\n"
                "3. If the rep asks to wrap up, finalise, or end the call (e.g. 'wrap this up', "
                "'end the call', 'write the note'), call the wrap_call tool. Then speak the "
                "three action items in plain English.\n\n"
                "Speak plainly. No markdown. No lists. Keep responses concise."
            ),
        )
        self._workspace = workspace
        self._session_id = session_id
        self._hcp_id = hcp_id
        self._mode = mode

    async def on_enter(self) -> None:
        if self._mode == "pre_call":
            await self.session.generate_reply(
                instructions=(
                    "Greet the rep briefly, then immediately call the get_brief tool "
                    "and speak the brief in calm spoken English. Keep the greeting to "
                    "one short sentence such as 'Pulling your brief now.'"
                )
            )
        elif self._mode == "post_call":
            await self.session.generate_reply(
                instructions=(
                    "Immediately call the wrap_call tool to finalise the call. "
                    "When it returns, speak the three action items in plain spoken English. "
                    "Do not greet the rep — just deliver the wrap."
                )
            )

    @function_tool()
    async def get_brief(self, context: RunContext) -> str:
        """Fetch the pre-call brief for Dr Rose. Call when the rep asks to be prepped, briefed, or summarised before the call."""
        await self._workspace.emit(
            constants.WS_BRIEF_REQUEST,
            self._session_id,
            {"hcp_id": self._hcp_id},
            hcp_id=self._hcp_id,
        )

        async def _wait() -> dict[str, Any]:
            async for doc in self._workspace.watch(
                constants.WS_BRIEF_RESULT, session_id=self._session_id
            ):
                return doc

        try:
            doc = await asyncio.wait_for(_wait(), timeout=WAIT_FOR_RESULT_TIMEOUT_S)
        except asyncio.TimeoutError:
            return "I couldn't pull the brief in time."

        p = doc.get("payload", {})
        parts = [
            p.get("headline", ""),
            p.get("last_interaction_summary", ""),
        ]
        concerns = p.get("key_concerns", [])
        if concerns:
            parts.append("Her main concerns: " + "; ".join(concerns[:3]) + ".")
        opener = p.get("recommended_opener", "")
        if opener:
            parts.append("Suggested opener: " + opener)
        return " ".join(part for part in parts if part)

    @function_tool()
    async def flag_utterance(self, context: RunContext, utterance: str) -> str:
        """Flag what the doctor said for safety or compliance review. Pass the exact words the doctor used."""
        msg_id = "ws_" + os.urandom(6).hex()
        await self._workspace.db[constants.COLL_AGENT_WORKSPACE].insert_one({
            "_id": msg_id,
            "type": constants.WS_UTTERANCE,
            "session_id": self._session_id,
            "hcp_id": self._hcp_id,
            "payload": {
                "speaker": constants.UTTERANCE_SPEAKER_HCP,
                "text": utterance,
                "hcp_id": self._hcp_id,
            },
            "created_at": _now_utc(),
        })

        await self._workspace.db[constants.COLL_CALL_SESSIONS].update_one(
            {"_id": self._session_id},
            {
                "$push": {"utterances": {"speaker": "hcp", "text": utterance}},
                "$setOnInsert": {
                    "_id": self._session_id,
                    "hcp_id": self._hcp_id,
                    "rep_id": "rep_demo",
                    "status": "in_progress",
                },
            },
            upsert=True,
        )

        await asyncio.sleep(2)

        safety = await self._workspace.db[constants.COLL_SAFETY_REPORTS].find_one(
            {"session_id": self._session_id, "trigger_text": utterance}
        )
        compliance = await self._workspace.db[constants.COLL_COMPLIANCE_FLAGS].find_one(
            {"session_id": self._session_id, "trigger_text": utterance}
        )

        if safety:
            return "Safety flag captured. Adverse event with hospital outcome logged."
        if compliance:
            return "Compliance flag captured. Off-label discussion logged."
        return "Captured. Nothing flagged."

    @function_tool()
    async def wrap_call(self, context: RunContext) -> str:
        """Wrap up the call. Call when the rep asks to finalise, end the call, or write the note."""
        await self._workspace.emit(
            constants.WS_FINALIZE_CALL,
            self._session_id,
            {"hcp_id": self._hcp_id},
            hcp_id=self._hcp_id,
        )

        async def _wait() -> dict[str, Any]:
            async for doc in self._workspace.watch(
                constants.WS_FINALIZE_RESULT, session_id=self._session_id
            ):
                return doc

        try:
            doc = await asyncio.wait_for(_wait(), timeout=WAIT_FOR_RESULT_TIMEOUT_S)
        except asyncio.TimeoutError:
            return "I couldn't finalise in time."

        p = doc.get("payload", {})
        actions = p.get("action_items", [])
        if not actions:
            return "Wrap done. No action items captured."
        return "Three things to action. " + " ".join(
            f"{i + 1}. {a}" for i, a in enumerate(actions[:3])
        )


server = AgentServer()


def prewarm(proc: JobProcess) -> None:
    proc.userdata["vad"] = silero.VAD.load()


server.setup_fnc = prewarm


@server.rtc_session(agent_name="my-agent")
async def field_companion_session(ctx: JobContext) -> None:
    ctx.log_context_fields = {"room": ctx.room.name}
    await ctx.connect()
    await start_background_agents()

    # The frontend stuffs {mode, hcp_id, session_id, ...} as JSON into the
    # RoomAgentDispatch metadata. Read the unsuffixed session_id from here so
    # the workspace bus correlates with what the API/views poll for.
    raw_metadata = ctx.job.metadata or "{}"
    try:
        meta = json.loads(raw_metadata)
    except json.JSONDecodeError:
        log.warning("failed to parse job metadata: %r", raw_metadata)
        meta = {}

    session_id = meta.get("session_id") or ctx.room.name
    hcp_id = meta.get("hcp_id") or DEFAULT_HCP_ID
    mode = meta.get("mode") or "pre_call"

    workspace = Workspace()
    chat_ctx = ChatContext()

    voice_id = os.environ.get("ELEVENLABS_VOICE_ID")
    tts: Optional[Any] = elevenlabs.TTS(voice_id=voice_id) if voice_id else None

    session = AgentSession(
        stt=deepgram.STT(model="nova-3"),
        llm=anthropic.LLM(model=constants.ANTHROPIC_MODEL),
        tts=tts,
        vad=ctx.proc.userdata["vad"],
        turn_handling=TurnHandlingOptions(
            turn_detection=MultilingualModel(),
            preemptive_generation={"enabled": False},
        ),
    )

    await session.start(
        agent=FieldCompanionAgent(
            chat_ctx=chat_ctx,
            workspace=workspace,
            session_id=session_id,
            hcp_id=hcp_id,
            mode=mode,
        ),
        room=ctx.room,
        room_options=room_io.RoomOptions(
            audio_input=room_io.AudioInputOptions(
                noise_cancellation=ai_coustics.audio_enhancement(
                    model=ai_coustics.EnhancerModel.QUAIL_VF_L
                ),
            ),
        ),
    )


if __name__ == "__main__":
    cli.run_app(server)
