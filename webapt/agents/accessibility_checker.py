"""Accessibility Checker agent builder."""

from strands import Agent
from strands.session.file_session_manager import FileSessionManager
from strands.tools.mcp import MCPClient
from strands_tools import file_read, file_write

from ..config import WebAPTConfig
from ..prompts.accessibility import ACCESSIBILITY_SYSTEM_PROMPT
from ..tools.screenshot_tools import save_screenshot_with_metadata
from ..tools.report_tools import write_executive_summary


def build_accessibility_checker(
    model,
    config: WebAPTConfig,
    mcp_client: MCPClient,
) -> Agent:
    """Build the Accessibility Checker agent.

    This agent navigates to URLs, tests login with various roles,
    and produces a Markdown report with screenshots.

    Args:
        model: The LLM model instance.
        config: WebAPT configuration.
        mcp_client: Playwright MCP client for browser automation.

    Returns:
        Configured Strands Agent.
    """
    config.ensure_dirs()

    session_manager = FileSessionManager(
        session_id=f"{config.project_name}_accessibility",
        storage_dir=str(config.sessions_dir),
    )

    # Inject output paths into the system prompt
    prompt = ACCESSIBILITY_SYSTEM_PROMPT + f"""

## Output Paths (use these exact paths)
- Reports directory: {config.accessibility_reports_dir}
- Screenshots directory: {config.screenshots_dir}
- Use output_dir="{config.screenshots_dir}" when calling save_screenshot_with_metadata
"""

    return Agent(
        model=model,
        tools=[
            file_write,
            file_read,
            save_screenshot_with_metadata,
            write_executive_summary,
            mcp_client,
        ],
        session_manager=session_manager,
        system_prompt=prompt,
        agent_id="accessibility_checker",
    )
