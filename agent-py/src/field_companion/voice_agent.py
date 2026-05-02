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
from .workspace import Workspace, _new_id, _now

ENV_PATH = Path(__file__).resolve().parents[3] / "agent-py" / ".env.local"
load_dotenv(ENV_PATH)

log = logging.getLogger("field_companion.voice_agent")

DEFAULT_REP_ID = "rep_demo"
DEFAULT_HCP_ID = "hcp_rose"
DEFAULT_MODE = constants.CALL_MODE_PRE

WAIT_FOR_RESULT_TIMEOUT_S = 25


def _now_utc() -> datetime:
    return datetime.now(tz=timezone.utc)


class PreCallAgent(Agent):
    def __init__(
        self,
        *,
        chat_ctx: ChatContext,
        workspace: Workspace,
        session_id: str,
        hcp_id: str,
    ) -> None:
        super().__init__(
            chat_ctx=chat_ctx,
            instructions=(
                "You are Field Companion, a voice assistant for a UK pharma "
                "sales rep about to walk into a call with an oncologist. The "
                "rep has tapped to begin prep. Greet them briefly, then call "
                "the dispatch_brief tool to fetch the prep brief. While the "
                "tool is running, stay quiet — the tool itself returns the "
                "spoken brief content. After the tool returns, deliver the "
                "brief in a calm, concise voice. Do not invent facts. Do not "
                "use markdown, lists, or emojis. Plain spoken English only."
            ),
        )
        self._workspace = workspace
        self._session_id = session_id
        self._hcp_id = hcp_id

    async def on_enter(self) -> None:
        await self.session.generate_reply(
            instructions=(
                "Briefly say you're prepping the call, then immediately call "
                "the dispatch_brief tool. One short sentence before the tool, "
                "no more."
            )
        )

    @function_tool()
    async def dispatch_brief(self, context: RunContext) -> str:
        """Request the prep brief for the upcoming call. Returns the brief text to speak."""
        log.info("dispatch_brief called for session=%s hcp=%s", self._session_id, self._hcp_id)

        await self._workspace.emit(
            constants.WS_BRIEF_REQUEST,
            self._session_id,
            {"hcp_id": self._hcp_id},
            hcp_id=self._hcp_id,
        )

        async def _wait_for_result() -> dict[str, Any]:
            async for doc in self._workspace.watch(
                constants.WS_BRIEF_RESULT,
                session_id=self._session_id,
            ):
                return doc

        try:
            doc = await asyncio.wait_for(_wait_for_result(), timeout=WAIT_FOR_RESULT_TIMEOUT_S)
        except asyncio.TimeoutError:
            log.warning("brief timed out for session=%s", self._session_id)
            return (
                "I couldn't pull the brief in time. Open the prep view on screen "
                "and you'll see what we have so far."
            )

        payload = doc.get("payload", {})
        headline = payload.get("headline", "")
        last = payload.get("last_interaction_summary", "")
        opener = payload.get("recommended_opener", "")
        concerns = payload.get("key_concerns", [])
        concerns_text = "; ".join(concerns[:3]) if concerns else ""

        spoken = " ".join(
            part for part in [
                headline,
                last,
                f"Her main concerns going in: {concerns_text}." if concerns_text else "",
                f"Suggested opener: {opener}" if opener else "",
            ] if part
        )
        return spoken or "Brief is ready on screen."


class DuringCallAgent(Agent):
    def __init__(
        self,
        *,
        chat_ctx: ChatContext,
        workspace: Workspace,
        session_id: str,
        hcp_id: str,
    ) -> None:
        super().__init__(
            chat_ctx=chat_ctx,
            instructions=(
                "You are a silent notetaker. Do not speak. Do not interrupt. "
                "Do not respond to anything. Your only job is to listen. "
                "Never call any tool."
            ),
        )
        self._workspace = workspace
        self._session_id = session_id
        self._hcp_id = hcp_id

    async def on_enter(self) -> None:
        log.info("during_call mode entered for session=%s", self._session_id)


class PostCallAgent(Agent):
    def __init__(
        self,
        *,
        chat_ctx: ChatContext,
        workspace: Workspace,
        session_id: str,
        hcp_id: str,
    ) -> None:
        super().__init__(
            chat_ctx=chat_ctx,
            instructions=(
                "You are Field Companion wrapping up the call. The rep has "
                "tapped end. Briefly say you're writing up the note, then "
                "call dispatch_finalize. After the tool returns, speak a "
                "concise summary of the action items only — no preamble, no "
                "small talk. Plain spoken English."
            ),
        )
        self._workspace = workspace
        self._session_id = session_id
        self._hcp_id = hcp_id

    async def on_enter(self) -> None:
        await self.session.generate_reply(
            instructions=(
                "One short sentence saying you're writing the note, then "
                "immediately call dispatch_finalize."
            )
        )

    @function_tool()
    async def dispatch_finalize(self, context: RunContext) -> str:
        """Request the post-call wrap. Returns the action-item summary to speak."""
        log.info("dispatch_finalize called for session=%s", self._session_id)

        await self._workspace.emit(
            constants.WS_FINALIZE_CALL,
            self._session_id,
            {"hcp_id": self._hcp_id},
            hcp_id=self._hcp_id,
        )

        async def _wait_for_result() -> dict[str, Any]:
            async for doc in self._workspace.watch(
                constants.WS_FINALIZE_RESULT,
                session_id=self._session_id,
            ):
                return doc

        try:
            doc = await asyncio.wait_for(_wait_for_result(), timeout=WAIT_FOR_RESULT_TIMEOUT_S)
        except asyncio.TimeoutError:
            log.warning("finalize timed out for session=%s", self._session_id)
            return "I couldn't finalise in time. The wrap view on screen has what's done so far."

        payload = doc.get("payload", {})
        actions = payload.get("action_items", [])
        if not actions:
            return "No action items captured. Note is on screen."
        action_text = "; ".join(actions[:3])
        return f"Three things to action: {action_text}."


def _build_agent(
    mode: str,
    *,
    chat_ctx: ChatContext,
    workspace: Workspace,
    session_id: str,
    hcp_id: str,
) -> Agent:
    if mode == constants.CALL_MODE_PRE:
        return PreCallAgent(
            chat_ctx=chat_ctx, workspace=workspace, session_id=session_id, hcp_id=hcp_id
        )
    if mode == constants.CALL_MODE_DURING:
        return DuringCallAgent(
            chat_ctx=chat_ctx, workspace=workspace, session_id=session_id, hcp_id=hcp_id
        )
    if mode == constants.CALL_MODE_POST:
        return PostCallAgent(
            chat_ctx=chat_ctx, workspace=workspace, session_id=session_id, hcp_id=hcp_id
        )
    raise ValueError(f"unknown mode: {mode}")


server = AgentServer()


def prewarm(proc: JobProcess) -> None:
    proc.userdata["vad"] = silero.VAD.load()


server.setup_fnc = prewarm


@server.rtc_session(agent_name="field-companion-agent")
async def field_companion_session(ctx: JobContext) -> None:
    ctx.log_context_fields = {"room": ctx.room.name}
    await start_background_agents()

    meta: dict[str, str] = {}
    if ctx.job.metadata:
        try:
            meta = json.loads(ctx.job.metadata)
        except json.JSONDecodeError:
            log.warning("ctx.job.metadata was not valid JSON; using defaults")

    mode = meta.get("mode", DEFAULT_MODE)
    rep_id = meta.get("rep_id", DEFAULT_REP_ID)
    hcp_id = meta.get("hcp_id", DEFAULT_HCP_ID)
    session_id = meta.get("session_id", ctx.room.name)

    log.info(
        "starting field companion session mode=%s rep=%s hcp=%s session=%s",
        mode, rep_id, hcp_id, session_id,
    )

    workspace = Workspace()
    chat_ctx = ChatContext()

    voice_id = os.environ.get("ELEVENLABS_VOICE_ID")
    tts: Optional[Any] = None
    if voice_id:
        tts = elevenlabs.TTS(voice_id=voice_id)

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
        agent=_build_agent(
            mode,
            chat_ctx=chat_ctx,
            workspace=workspace,
            session_id=session_id,
            hcp_id=hcp_id,
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
    await ctx.connect()


if __name__ == "__main__":
    cli.run_app(server)
