"""Application Analyzer agent builder."""

from strands import Agent
from strands.session.file_session_manager import FileSessionManager
from strands.tools.mcp import MCPClient
from strands_tools import file_read, file_write

from ..config import WebAPTConfig
from ..prompts.analysis import APPLICATION_ANALYSIS_SYSTEM_PROMPT
from ..tools.screenshot_tools import save_screenshot_with_metadata


def build_application_analyzer(
    model,
    config: WebAPTConfig,
    mcp_client: MCPClient,
) -> Agent:
    """Build the Application Analyzer agent.

    This agent performs comprehensive web application analysis including
    crawling, API discovery, role-based analysis, and technology detection.

    Args:
        model: The LLM model instance.
        config: WebAPT configuration.
        mcp_client: Playwright MCP client for browser automation.

    Returns:
        Configured Strands Agent.
    """
    config.ensure_dirs()

    session_manager = FileSessionManager(
        session_id=f"{config.project_name}_analysis",
        storage_dir=str(config.sessions_dir),
    )

    prompt = APPLICATION_ANALYSIS_SYSTEM_PROMPT + f"""

## Output Paths (use these exact paths)
- Reports directory: {config.analysis_reports_dir}
- Screenshots directory: {config.analysis_screenshots_dir}
- Use output_dir="{config.screenshots_dir}" and agent_name="analysis" when calling save_screenshot_with_metadata
- Always pass agent_name='analysis' when calling save_screenshot_with_metadata
- Write the analysis report to: {config.analysis_reports_dir}/analysis.md
"""

    return Agent(
        model=model,
        tools=[
            file_write,
            file_read,
            save_screenshot_with_metadata,
            mcp_client,
        ],
        session_manager=session_manager,
        system_prompt=prompt,
        agent_id="application_analyzer",
    )
