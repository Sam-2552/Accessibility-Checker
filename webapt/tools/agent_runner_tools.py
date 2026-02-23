"""Agent runner tools — allow the QA Verifier to re-invoke sub-agents."""

from strands import tool

from ..config import WebAPTConfig
from ..mcp_factory import create_playwright_mcp
from ..agents.accessibility_checker import build_accessibility_checker
from ..agents.application_analyzer import build_application_analyzer

# Module-level context holder — set by build_qa_verifier before the agent runs
_config: "WebAPTConfig | None" = None
_model = None


def set_agent_runner_context(config: WebAPTConfig, model) -> None:
    """Inject config and model so the runner tools can create sub-agents.

    Call this before building the QA Verifier agent.
    """
    global _config, _model
    _config = config
    _model = model


@tool
def run_accessibility_agent(task: str, fix_instructions: str = "") -> str:
    """Re-run the Accessibility Checker agent with optional fix instructions.

    Use this when the accessibility report is missing, incomplete, or has quality issues.
    Provide specific fix_instructions describing what to fix or improve based on your review.
    The agent will run fresh with the original task + your fix instructions appended.

    Args:
        task: The original user task (URL + roles etc.)
        fix_instructions: Specific instructions for what to fix/improve based on your QA
            review.  e.g. "The previous run missed screenshots. Ensure you take a screenshot
            of the login page and dashboard. Also the report is missing the role-based
            analysis section."

    Returns:
        Agent completion summary (first 500 chars of result).
    """
    if not _config or not _model:
        return "Error: agent runner context not initialized — call set_agent_runner_context first"

    enhanced_task = task
    if fix_instructions:
        enhanced_task += (
            f"\n\n## QA Fix Instructions (IMPORTANT - address these issues):\n{fix_instructions}"
        )

    mcp = create_playwright_mcp("accessibility_qa_retry", _config.headless)
    agent = build_accessibility_checker(_model, _config, mcp)
    result = agent(enhanced_task)
    return f"Accessibility agent completed. Result: {str(result)[:500]}"


@tool
def run_analysis_agent(task: str, fix_instructions: str = "") -> str:
    """Re-run the Application Analyzer agent with optional fix instructions.

    Use this when the analysis report is missing, incomplete, or has quality issues.
    Provide specific fix_instructions describing what to fix based on your QA review.

    Args:
        task: The original user task.
        fix_instructions: Specific instructions for what to fix/improve.
            e.g. "The previous run did not document any API endpoints.
            Ensure you capture all XHR/fetch requests and document them.
            Also missing technology stack detection."

    Returns:
        Agent completion summary (first 500 chars of result).
    """
    if not _config or not _model:
        return "Error: agent runner context not initialized — call set_agent_runner_context first"

    enhanced_task = task
    if fix_instructions:
        enhanced_task += (
            f"\n\n## QA Fix Instructions (IMPORTANT - address these issues):\n{fix_instructions}"
        )

    mcp = create_playwright_mcp("analysis_qa_retry", _config.headless)
    agent = build_application_analyzer(_model, _config, mcp)
    result = agent(enhanced_task)
    return f"Analysis agent completed. Result: {str(result)[:500]}"
