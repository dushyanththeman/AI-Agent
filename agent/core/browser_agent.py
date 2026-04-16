from __future__ import annotations

import asyncio
import base64
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict

from dotenv import load_dotenv
from langchain_groq import ChatGroq
from browser_use import Agent
from browser_use.browser.browser import Browser
from browser_use.browser.context import BrowserContextConfig
from browser_use import BrowserConfig


DEFAULT_MODEL: str = "llama-3.3-70b-versatile"
DEFAULT_BASE_URL: str = "http://localhost:5050"


@dataclass(frozen=True)
class BrowserAgentResult:
    """Return value for a single browser agent run."""

    success: bool
    final_output: str
    screenshots_dir: str
    steps: int
    started_at: float
    finished_at: float


def _ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


def _save_base64_png(b64: str, out_path: Path) -> None:
    """Persist a base64-encoded PNG screenshot to disk."""

    _ensure_dir(out_path.parent)
    data = base64.b64decode(b64)
    out_path.write_bytes(data)

def _infer_success(agent_result: Any) -> bool:
    """
    Best-effort success inference for browser-use 0.1.x results.
    """
    all_results = getattr(agent_result, "all_results", None)
    if not isinstance(all_results, list) or not all_results:
        return False

    # Check the LAST result only — intermediate errors are just retries
    last = all_results[-1]
    is_done = bool(getattr(last, "is_done", False))
    success_flag = getattr(last, "success", None)
    last_has_error = bool(getattr(last, "error", None))

    if last_has_error:
        return False
    if success_flag is True:
        return True
    return is_done


def _task_to_instructions(nl_task: str, base_url: str) -> str:
    """
    Wrap the user task with strict constraints for UI-only operation.

    This intentionally avoids DOM selectors/API shortcuts by instructing the agent
    to behave like a human (click visible controls, type into visible fields).
    """

    return "\n".join(
        [
            "You are an IT support browser operator.",
            "You must use ONLY the website UI like a human.",
            "Do NOT use developer tools, code execution, API calls, or hidden DOM queries.",
            "Do NOT assume endpoints; always navigate via visible links/buttons/forms.",
            f"The admin panel base URL is: {base_url}",
            "",
            "Goal:",
            nl_task.strip(),
        ]
    )


async def run_browser_task(
    *,
    nl_task: str,
    task_id: str,
    base_url: str = DEFAULT_BASE_URL,
    model: str = DEFAULT_MODEL,
    screenshots_root: str = "screenshots",
    headless: bool = False,
) -> BrowserAgentResult:
    """
    Execute a natural-language IT request by visually operating the admin panel.

    - Opens a real (non-headless) browser by default.
    - Saves a screenshot after every agent step to `screenshots/<task_id>/<step>.png`.
    """

    started_at = time.time()
    screenshots_dir = Path(screenshots_root) / task_id
    _ensure_dir(screenshots_dir)

    load_dotenv(override=False)
    if not os.environ.get("GROQ_API_KEY"):
        raise RuntimeError("Missing GROQ_API_KEY in environment.")

    llm = ChatGroq(
        model="llama-3.3-70b-versatile",
        api_key=os.getenv("GROQ_API_KEY"),
        max_tokens=512,
        temperature=0,
    )

    browser = Browser(
        config=BrowserConfig(
            headless=headless,
        )
    )

    step_counter: Dict[str, int] = {"n": 0}

    def on_new_step(state: Any, model_output: Any, steps: int) -> None:
        """
        Callback invoked by browser-use after each step.

        `state.screenshot` is expected to be a base64 png string in current versions.
        """

        try:
            b64 = getattr(state, "screenshot", None)
            if not b64:
                return
            step_counter["n"] += 1
            out_path = screenshots_dir / f"{step_counter['n']:03d}.png"
            _save_base64_png(str(b64), out_path)
        except Exception:
            # Screenshot saving should never crash the run.
            return

    task_instructions = _task_to_instructions(nl_task, base_url)

    agent = Agent(
        task=task_instructions,
        llm=llm,
        browser=browser,
        max_actions_per_step=1,
        max_failures=3,
        use_vision=False,
        save_conversation_path=None,
    )

    try:
        final_output = await agent.run()
    finally:
        # Ensure browser is closed even on failure.
        try:
            await browser.close()
        except Exception:
            pass

    finished_at = time.time()
    return BrowserAgentResult(
        success=_infer_success(final_output),
        final_output=str(final_output),
        screenshots_dir=str(screenshots_dir),
        steps=step_counter["n"],
        started_at=started_at,
        finished_at=finished_at,
    )


def run_browser_task_sync(
    *,
    nl_task: str,
    task_id: str,
    base_url: str = DEFAULT_BASE_URL,
    model: str = DEFAULT_MODEL,
    screenshots_root: str = "screenshots",
    headless: bool = False,
) -> BrowserAgentResult:
    """Synchronous wrapper for `run_browser_task`."""

    return asyncio.run(
        run_browser_task(
            nl_task=nl_task,
            task_id=task_id,
            base_url=base_url,
            model=model,
            screenshots_root=screenshots_root,
            headless=headless,
        )
    )

