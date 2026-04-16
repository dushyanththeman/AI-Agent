from __future__ import annotations

import asyncio
import os
import time
import uuid

from agent.core.browser_agent import run_browser_task


async def main() -> None:
    """
    Runs two end-to-end browser agent tasks against the local admin panel.

    Prereqs:
    - Admin panel is running at http://localhost:5050
    - GROQ_API_KEY is set in environment
    """

    tasks = [
        "reset password for ashley25@example.com",
        "assign Pro license to kathleenshields@example.com",
    ]
    for task_text in tasks:
        await run_task(task_text)
        print("Sleeping 10s before next task...")
        time.sleep(10)


async def run_task(task_text: str) -> None:
    base_url = os.environ.get("ADMIN_PANEL_URL", "http://localhost:5050")
    
    task_id = str(uuid.uuid4())[:8]
    print("\n==============================")
    print("Task:", task_text)
    print("Task ID:", task_id)
    print("==============================")

    result = await run_browser_task(
        nl_task=task_text,
        task_id=task_id,
        base_url=base_url,
        screenshots_root="screenshots",
        headless=False,
    )

    print("Success:", result.success)
    print("Steps:", result.steps)
    print("Screenshots:", result.screenshots_dir)
    print("Final output:\n", result.final_output)


if __name__ == "__main__":
    asyncio.run(main())
