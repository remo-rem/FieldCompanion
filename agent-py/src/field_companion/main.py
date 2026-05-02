import asyncio
import logging
import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

from . import constants
from .action_agent import ActionAgent
from .briefing_agent import BriefingAgent
from .call_helper_agent import CallHelperAgent
from .workspace import Workspace

ENV_PATH = Path(__file__).resolve().parents[3] / "agent-py" / ".env.local"
load_dotenv(ENV_PATH)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
)
log = logging.getLogger("field_companion.main")

_started_lock = asyncio.Lock()
_started: bool = False
_tasks: list[asyncio.Task] = []
_workspace: Optional[Workspace] = None


async def _briefing_loop(workspace: Workspace) -> None:
    agent = BriefingAgent(workspace=workspace)
    log.info("briefing agent started")
    await agent.run()


async def _action_loop(workspace: Workspace) -> None:
    agent = ActionAgent(workspace=workspace)
    log.info("action agent started")
    await agent.run()


async def _call_helper_loop(workspace: Workspace) -> None:
    agent = CallHelperAgent(workspace=workspace)
    log.info("call helper agent started")
    async for msg in workspace.watch(constants.WS_UTTERANCE):
        try:
            payload = msg.get("payload", {})
            session_id = msg.get("session_id")
            hcp_id = payload.get("hcp_id") or msg.get("hcp_id")
            text = payload.get("text", "")
            speaker = payload.get("speaker", "")
            if speaker != constants.UTTERANCE_SPEAKER_HCP:
                continue
            if not session_id or not hcp_id or not text:
                continue
            await agent.handle_utterance(session_id, hcp_id, text)
        except Exception:
            log.exception("call helper failed on utterance")


async def start_background_agents() -> None:
    """Idempotently start the three background watchers. Safe to call multiple times."""
    global _started, _workspace, _tasks
    async with _started_lock:
        if _started:
            return
        _workspace = Workspace()
        _tasks = [
            asyncio.create_task(_briefing_loop(_workspace), name="briefing_agent"),
            asyncio.create_task(_action_loop(_workspace), name="action_agent"),
            asyncio.create_task(_call_helper_loop(_workspace), name="call_helper_agent"),
        ]
        _started = True
        log.info("all background agents started (%d tasks)", len(_tasks))


async def stop_background_agents() -> None:
    global _started, _workspace, _tasks
    async with _started_lock:
        if not _started:
            return
        for task in _tasks:
            task.cancel()
        await asyncio.gather(*_tasks, return_exceptions=True)
        if _workspace is not None:
            await _workspace.close()
        _tasks = []
        _workspace = None
        _started = False
        log.info("all background agents stopped")


async def standalone() -> None:
    """Run the three background agents without the voice agent (for testing the bus)."""
    await start_background_agents()
    log.info("running standalone — Ctrl+C to stop")
    try:
        await asyncio.gather(*_tasks)
    except asyncio.CancelledError:
        pass
    finally:
        await stop_background_agents()


if __name__ == "__main__":
    try:
        asyncio.run(standalone())
    except KeyboardInterrupt:
        log.info("shutdown requested")
