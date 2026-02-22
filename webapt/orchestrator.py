"""Sequential pipeline orchestrator for WebAPT."""

from pathlib import Path

from .agents.accessibility_checker import build_accessibility_checker
from .agents.application_analyzer import build_application_analyzer
from .agents.qa_verifier import build_qa_verifier
from .config import WebAPTConfig
from .mcp_factory import create_playwright_mcp
from .md_to_pdf import convert_all_reports
from .model_factory import build_model


def run_full_pipeline(user_input: str, config: WebAPTConfig) -> str:
    """Run the full WebAPT pipeline: Accessibility -> Analysis -> QA -> PDF.

    Args:
        user_input: Natural language task description from the user.
        config: WebAPT configuration.

    Returns:
        Summary of the pipeline run.
    """
    config.ensure_dirs()
    model = build_model(config)
    results = []

    # Step 1: Accessibility Check
    print("\n[1/4] Running Accessibility Checker...")
    mcp_accessibility = create_playwright_mcp("accessibility", config.headless)
    try:
        accessibility_agent = build_accessibility_checker(model, config, mcp_accessibility)
        acc_result = accessibility_agent(user_input)
        results.append(f"Accessibility: {str(acc_result).strip()[:200]}")
        print("  -> Accessibility check complete.")
    except Exception as e:
        results.append(f"Accessibility: FAILED - {e}")
        print(f"  -> Accessibility check failed: {e}")

    # Step 2: Application Analysis
    print("\n[2/4] Running Application Analyzer...")
    mcp_analysis = create_playwright_mcp("analysis", config.headless)
    try:
        analysis_agent = build_application_analyzer(model, config, mcp_analysis)
        analysis_result = analysis_agent(user_input)
        results.append(f"Analysis: {str(analysis_result).strip()[:200]}")
        print("  -> Application analysis complete.")
    except Exception as e:
        results.append(f"Analysis: FAILED - {e}")
        print(f"  -> Application analysis failed: {e}")

    # Step 3: QA Verification
    print("\n[3/4] Running QA Verifier...")
    try:
        qa_task = (
            f"Verify the reports generated for this task: {user_input}\n"
            f"Project directory: {config.project_dir}\n"
            f"Check accessibility reports in: {config.accessibility_reports_dir}\n"
            f"Check analysis reports in: {config.analysis_reports_dir}\n"
            f"Check screenshots in: {config.screenshots_dir}"
        )
        qa_agent = build_qa_verifier(model, config)
        qa_result = qa_agent(qa_task)
        results.append(f"QA: {str(qa_result).strip()[:200]}")
        print("  -> QA verification complete.")
    except Exception as e:
        results.append(f"QA: FAILED - {e}")
        print(f"  -> QA verification failed: {e}")

    # Step 4: PDF Conversion
    print("\n[4/4] Converting reports to PDF...")
    try:
        pdfs = convert_all_reports(config.project_dir)
        results.append(f"PDF: Generated {len(pdfs)} PDFs")
        for pdf in pdfs:
            print(f"  -> {pdf}")
    except Exception as e:
        results.append(f"PDF: FAILED - {e}")
        print(f"  -> PDF conversion failed: {e}")

    summary = "\n".join([
        "=" * 60,
        "WebAPT Pipeline Complete",
        "=" * 60,
        f"Project: {config.project_name}",
        f"Output: {config.project_dir}",
        "",
        *results,
        "=" * 60,
    ])
    print(f"\n{summary}")
    return summary


def run_single_agent(
    agent_type: str,
    user_input: str,
    config: WebAPTConfig,
    convert_pdf: bool = True,
) -> str:
    """Run a single agent from the pipeline.

    Args:
        agent_type: One of 'accessibility', 'analysis', 'qa'.
        user_input: Natural language task description.
        config: WebAPT configuration.
        convert_pdf: Whether to convert output to PDF.

    Returns:
        Agent result summary.
    """
    config.ensure_dirs()
    model = build_model(config)

    if agent_type == "accessibility":
        print("\nRunning Accessibility Checker...")
        mcp = create_playwright_mcp("accessibility", config.headless)
        agent = build_accessibility_checker(model, config, mcp)
        result = agent(user_input)

    elif agent_type == "analysis":
        print("\nRunning Application Analyzer...")
        mcp = create_playwright_mcp("analysis", config.headless)
        agent = build_application_analyzer(model, config, mcp)
        result = agent(user_input)

    elif agent_type == "qa":
        print("\nRunning QA Verifier...")
        qa_task = (
            f"Verify the reports generated for this task: {user_input}\n"
            f"Project directory: {config.project_dir}\n"
            f"Check accessibility reports in: {config.accessibility_reports_dir}\n"
            f"Check analysis reports in: {config.analysis_reports_dir}\n"
            f"Check screenshots in: {config.screenshots_dir}"
        )
        agent = build_qa_verifier(model, config)
        result = agent(qa_task)

    else:
        return f"Unknown agent type: {agent_type}. Use 'accessibility', 'analysis', or 'qa'."

    result_str = str(result).strip()
    print(f"\nAgent complete. Output: {config.project_dir}")

    if convert_pdf:
        print("Converting reports to PDF...")
        try:
            pdfs = convert_all_reports(config.project_dir)
            for pdf in pdfs:
                print(f"  -> {pdf}")
        except Exception as e:
            print(f"PDF conversion failed: {e}")

    return result_str
