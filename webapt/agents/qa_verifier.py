"""QA Verifier agent builder."""

from strands import Agent
from strands.session.file_session_manager import FileSessionManager
from strands_tools import file_read, file_write

from ..config import WebAPTConfig
from ..prompts.qa import QA_SYSTEM_PROMPT
from ..tools.agent_runner_tools import (
    run_accessibility_agent,
    run_analysis_agent,
    set_agent_runner_context,
)
from ..tools.validation_tools import (
    check_file_exists,
    check_markdown_structure,
    list_directory_contents,
)


def build_qa_verifier(
    model,
    config: WebAPTConfig,
) -> Agent:
    """Build the QA Verifier agent.

    This agent reads generated reports and validates their structure,
    content completeness, and screenshot references.  It can also
    re-invoke the Accessibility Checker and Application Analyzer agents
    via run_accessibility_agent / run_analysis_agent tools when it
    determines that the reports need improvement.

    Args:
        model: The LLM model instance.
        config: WebAPT configuration.

    Returns:
        Configured Strands Agent.
    """
    config.ensure_dirs()

    # Give the runner tools access to the current config + model so they
    # can spin up sub-agents on behalf of the QA verifier.
    set_agent_runner_context(config, model)

    session_manager = FileSessionManager(
        session_id=f"{config.project_name}_qa",
        storage_dir=str(config.sessions_dir),
    )

    prompt = QA_SYSTEM_PROMPT + f"""

## Output Paths (use these exact paths)
- Accessibility reports: {config.accessibility_reports_dir}
- Analysis reports: {config.analysis_reports_dir}
- Screenshots (base): {config.screenshots_dir}
- Screenshots (accessibility agent): {config.accessibility_screenshots_dir}
- Screenshots (analysis agent): {config.analysis_screenshots_dir}
- Write QA report to: {config.project_dir}/qa_report.md
"""

    return Agent(
        model=model,
        tools=[
            file_read,
            file_write,
            check_file_exists,
            check_markdown_structure,
            list_directory_contents,
            run_accessibility_agent,   # re-run accessibility checker
            run_analysis_agent,        # re-run application analyzer
        ],
        session_manager=session_manager,
        system_prompt=prompt,
        agent_id="qa_verifier",
    )
