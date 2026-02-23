"""Sequential pipeline orchestrator for WebAPT."""

import re

try:
    from langfuse.decorators import observe, langfuse_context
    _LANGFUSE_AVAILABLE = True
except ImportError:
    # Langfuse not installed — provide no-op fallbacks
    _LANGFUSE_AVAILABLE = False

    def observe(func=None, **kwargs):  # type: ignore[misc]
        """No-op decorator when langfuse is not installed."""
        if func is not None:
            return func
        def decorator(f):
            return f
        return decorator

    class _NoopContext:
        def update_current_trace(self, **kwargs):
            pass

    langfuse_context = _NoopContext()  # type: ignore[assignment]

from .agents.accessibility_checker import build_accessibility_checker
from .agents.application_analyzer import build_application_analyzer
from .agents.qa_verifier import build_qa_verifier
from .config import WebAPTConfig
from .mcp_factory import create_playwright_mcp
from .md_to_pdf import convert_all_reports
from .model_factory import build_model
from .tools.validation_tools import parse_qa_verdict


# ── URL extraction ────────────────────────────────────────────────────────────

def extract_urls(text: str) -> list:
    """Extract all unique URLs from task text, preserving order."""
    pattern = r'https?://[^\s,;)>\]]+'
    return list(dict.fromkeys(re.findall(pattern, text)))


# ── Internal pipeline helpers ─────────────────────────────────────────────────

@observe()
def _run_pipeline_single(
    user_input: str,
    config: WebAPTConfig,
    url_prefix: str = "",
    skip_qa_pdf: bool = False,
) -> str:
    """Run the full WebAPT pipeline for a single URL/task.

    Args:
        user_input: Natural language task description.
        config: WebAPT configuration.
        url_prefix: Optional prefix for log messages (e.g. "[https://url] ").
        skip_qa_pdf: If True, skip QA and PDF steps (used in multi-URL mode
                     where QA/PDF run once after all URLs are processed).

    Returns:
        Partial results list as a formatted string.
    """
    config.ensure_dirs()
    model = build_model(config)
    results = []

    step_total = "2" if skip_qa_pdf else "4"

    # Step 1: Accessibility Check
    print(f"\n{url_prefix}[1/{step_total}] Running Accessibility Checker...")
    mcp_accessibility = create_playwright_mcp("accessibility", config.headless)
    try:
        accessibility_agent = build_accessibility_checker(model, config, mcp_accessibility)
        acc_result = accessibility_agent(user_input)
        acc_result_str = str(acc_result).strip()
        results.append(f"Accessibility: {acc_result_str[:200]}")
        print(f"{url_prefix}  -> Accessibility check complete.")

        # Fallback: if the agent didn't write a report, save from its response text
        acc_reports = list(config.accessibility_reports_dir.glob("*.md"))
        if not acc_reports and acc_result_str and len(acc_result_str) > 50:
            fallback_path = config.accessibility_reports_dir / "accessibility_report.md"
            print(f"{url_prefix}  -> Accessibility agent skipped file_write; saving from response text.")
            fallback_path.write_text(acc_result_str, encoding="utf-8")
    except Exception as e:
        results.append(f"Accessibility: FAILED - {e}")
        print(f"{url_prefix}  -> Accessibility check failed: {e}")

    # Step 2: Application Analysis
    print(f"\n{url_prefix}[2/{step_total}] Running Application Analyzer...")
    mcp_analysis = create_playwright_mcp("analysis", config.headless)
    try:
        analysis_agent = build_application_analyzer(model, config, mcp_analysis)
        analysis_result = analysis_agent(user_input)
        results.append(f"Analysis: {str(analysis_result).strip()[:200]}")
        print(f"{url_prefix}  -> Application analysis complete.")
    except Exception as e:
        results.append(f"Analysis: FAILED - {e}")
        print(f"{url_prefix}  -> Application analysis failed: {e}")

    if skip_qa_pdf:
        return "\n".join(results)

    # Step 3: QA Verification
    print(f"\n{url_prefix}[3/4] Running QA Verifier...")
    results_str, verdict_str = _run_qa(user_input, config, url_prefix)
    results.extend(results_str)

    # Step 4: PDF Conversion
    print(f"\n{url_prefix}[4/4] Converting reports to PDF...")
    pdf_result = _run_pdf(config, url_prefix)
    results.append(pdf_result)

    return "\n".join(results)


@observe()
def _run_qa(user_input: str, config: WebAPTConfig, url_prefix: str = "") -> tuple:
    """Run the QA verifier step. Returns (result_lines, verdict_str)."""
    qa_task = (
        f"Verify the reports generated for this task: {user_input}\n"
        f"Project directory: {config.project_dir}\n"
        f"Check accessibility reports in: {config.accessibility_reports_dir}\n"
        f"Check analysis reports in: {config.analysis_reports_dir}\n"
        f"Check screenshots in: {config.screenshots_dir}\n"
        f"Check accessibility screenshots in: {config.accessibility_screenshots_dir}\n"
        f"Check analysis screenshots in: {config.analysis_screenshots_dir}\n"
        f"Original user task (pass to run_*_agent tools if you need to rerun): {user_input}\n"
        f"CRITICAL: You MUST call file_write to save your QA report to "
        f"{config.project_dir}/qa_report.md before finishing."
    )
    model = build_model(config)
    results = []
    verdict_str = "UNKNOWN"
    qa_report_path = config.project_dir / "qa_report.md"
    try:
        qa_agent = build_qa_verifier(model, config)
        qa_result = qa_agent(qa_task)
        print(f"{url_prefix}  -> QA verification complete.")

        # Fallback: if the agent didn't write qa_report.md, extract from its last response
        if not qa_report_path.exists():
            result_text = str(qa_result).strip()
            if result_text and len(result_text) > 50:
                print(f"{url_prefix}  -> QA agent skipped file_write; saving report from response text.")
                qa_report_path.write_text(result_text, encoding="utf-8")
            else:
                print(f"{url_prefix}  -> WARNING: qa_report.md not created and no response text available.")

        verdict = parse_qa_verdict(str(qa_report_path))
        overall = verdict.get("overall", "UNKNOWN")
        reruns = verdict.get("reruns_performed", "none")
        verdict_str = overall
        results.append(f"QA: {overall} (reruns: {reruns})")
    except Exception as e:
        results.append(f"QA: FAILED - {e}")
        print(f"{url_prefix}  -> QA verification failed: {e}")
    return results, verdict_str


@observe()
def _run_pdf(config: WebAPTConfig, url_prefix: str = "") -> str:
    """Run PDF conversion step. Returns a result line."""
    try:
        pdfs = convert_all_reports(config.project_dir)
        for pdf in pdfs:
            print(f"{url_prefix}  -> {pdf}")
        return f"PDF: Generated {len(pdfs)} PDFs"
    except Exception as e:
        print(f"{url_prefix}  -> PDF conversion failed: {e}")
        return f"PDF: FAILED - {e}"


def _build_url_task(full_task: str, target_url: str) -> str:
    """Build a per-URL task string preserving credentials/context from the original."""
    other_urls = [u for u in extract_urls(full_task) if u != target_url]
    task = full_task
    for other_url in other_urls:
        task = task.replace(other_url, "").strip()
    # Clean up orphaned punctuation/separators from removed URLs
    task = re.sub(r'[\s,;]+', ' ', task).strip()
    # Ensure target URL is prominent
    if target_url not in task:
        task = f"{target_url}\n{task}"
    return task.strip()


def _build_combined_summary(urls: list, per_url_results: list, config: WebAPTConfig) -> str:
    """Run QA + PDF once over all URL results, then build combined summary."""
    # Step 3: QA over all collected reports
    print(f"\n[Multi-URL QA] Running QA Verifier over all {len(urls)} URL reports...")
    combined_user_input = "\n".join(urls)
    qa_results, verdict_str = _run_qa(combined_user_input, config)

    # Step 4: PDF conversion for all reports
    print("\n[Multi-URL PDF] Converting all reports to PDF...")
    pdf_result = _run_pdf(config)

    # Build combined summary
    lines = [
        "=" * 60,
        f"WebAPT Multi-URL Pipeline Complete ({len(urls)} URLs)",
        "=" * 60,
        f"Project: {config.project_name}",
        f"Output: {config.project_dir}",
        "",
    ]
    for i, (url, result) in enumerate(zip(urls, per_url_results), 1):
        lines.append(f"[URL {i}/{len(urls)}] {url}")
        for line in result.splitlines():
            lines.append(f"  {line}")
        lines.append("")

    lines.extend([
        *qa_results,
        pdf_result,
        "=" * 60,
    ])

    summary = "\n".join(lines)
    print(f"\n{summary}")
    return summary


# ── Public API ────────────────────────────────────────────────────────────────

@observe()
def run_full_pipeline(user_input: str, config: WebAPTConfig) -> str:
    """Run the full WebAPT pipeline: Accessibility -> Analysis -> QA -> PDF.

    For multiple URLs in user_input, each URL is processed sequentially with
    accessibility and analysis, then a single QA + PDF pass covers all reports.

    Args:
        user_input: Natural language task description (may contain multiple URLs).
        config: WebAPT configuration.

    Returns:
        Summary of the pipeline run.
    """
    langfuse_context.update_current_trace(
        name="run_full_pipeline",
        input=user_input,
        metadata={"project": config.project_name},
    )
    urls = extract_urls(user_input)

    if len(urls) <= 1:
        # Single URL (or no URL) — run the existing full 4-step pipeline
        result = _run_pipeline_single(user_input, config)
        summary = "\n".join([
            "=" * 60,
            "WebAPT Pipeline Complete",
            "=" * 60,
            f"Project: {config.project_name}",
            f"Output: {config.project_dir}",
            "",
            result,
            "=" * 60,
        ])
        print(f"\n{summary}")
        return summary

    # Multiple URLs — run steps 1+2 for each URL sequentially,
    # then QA + PDF once over all reports
    print(f"[Multi-URL] Found {len(urls)} URLs — running sequentially")
    all_results = []

    for i, url in enumerate(urls, 1):
        print(f"\n[URL {i}/{len(urls)}] Processing: {url}")
        url_task = _build_url_task(user_input, url)
        # Run accessibility + analysis only (skip_qa_pdf=True);
        # QA and PDF will run once for all in _build_combined_summary
        result = _run_pipeline_single(
            url_task,
            config,
            url_prefix=f"[{i}/{len(urls)} {url}] ",
            skip_qa_pdf=True,
        )
        all_results.append(result)

    return _build_combined_summary(urls, all_results, config)


@observe()
def run_accessibility_only(user_input: str, config: WebAPTConfig) -> str:
    """Run accessibility agent + QA + PDF only (no analysis agent).

    Args:
        user_input: Natural language task description.
        config: WebAPT configuration.

    Returns:
        Summary of the accessibility scan.
    """
    langfuse_context.update_current_trace(
        name="run_accessibility_only",
        input=user_input,
        metadata={"project": config.project_name},
    )
    config.ensure_dirs()
    model = build_model(config)

    # Step 1: Accessibility Check
    print("\n[1/3] Running Accessibility Checker...")
    mcp = create_playwright_mcp("accessibility", config.headless)
    try:
        acc_agent = build_accessibility_checker(model, config, mcp)
        acc_result = acc_agent(user_input)
        acc_summary = str(acc_result).strip()[:200]
        print("  -> Accessibility check complete.")
    except Exception as e:
        acc_summary = f"FAILED - {e}"
        print(f"  -> Accessibility check failed: {e}")

    # Step 2: QA (validates accessibility report only)
    print("\n[2/3] Running QA Verifier (accessibility only)...")
    qa_task = (
        f"Verify the ACCESSIBILITY report only for: {user_input}\n"
        f"Check accessibility reports in: {config.accessibility_reports_dir}\n"
        f"Check screenshots in: {config.accessibility_screenshots_dir}\n"
        f"Project directory: {config.project_dir}\n"
        f"Note: Analysis report is not expected — do NOT rerun analysis agent.\n"
        f"Original user task (pass to run_accessibility_agent tool if you need to rerun): {user_input}\n"
        f"CRITICAL: You MUST call file_write to save your QA report to "
        f"{config.project_dir}/qa_report.md before finishing."
    )
    qa_report_path = config.project_dir / "qa_report.md"
    qa_summary = "UNKNOWN"
    try:
        qa_agent = build_qa_verifier(model, config)
        qa_result = qa_agent(qa_task)
        if not qa_report_path.exists():
            result_text = str(qa_result).strip()
            if result_text and len(result_text) > 50:
                qa_report_path.write_text(result_text, encoding="utf-8")
        verdict = parse_qa_verdict(str(qa_report_path))
        qa_summary = verdict.get("overall", "UNKNOWN")
        print(f"  -> QA complete: {qa_summary}")
    except Exception as e:
        qa_summary = f"FAILED - {e}"
        print(f"  -> QA failed: {e}")

    # Step 3: PDF Conversion
    print("\n[3/3] Converting reports to PDF...")
    try:
        pdfs = convert_all_reports(config.project_dir)
        pdf_summary = f"Generated {len(pdfs)} PDF(s)"
        print(f"  -> {pdf_summary}")
    except Exception as e:
        pdf_summary = f"PDF conversion failed: {e}"
        print(f"  -> {pdf_summary}")

    summary = "\n".join([
        "=" * 60,
        "WebAPT Accessibility Scan Complete",
        "=" * 60,
        f"Project: {config.project_name}",
        f"Output: {config.project_dir}",
        "",
        f"Accessibility: {acc_summary}",
        f"QA: {qa_summary}",
        f"PDF: {pdf_summary}",
        "=" * 60,
    ])
    print(f"\n{summary}")
    return summary


@observe()
def run_analysis_only(user_input: str, config: WebAPTConfig) -> str:
    """Run analysis agent + QA + PDF only (no accessibility agent).

    Args:
        user_input: Natural language task description.
        config: WebAPT configuration.

    Returns:
        Summary of the analysis scan.
    """
    langfuse_context.update_current_trace(
        name="run_analysis_only",
        input=user_input,
        metadata={"project": config.project_name},
    )
    config.ensure_dirs()
    model = build_model(config)

    # Step 1: Application Analysis
    print("\n[1/3] Running Application Analyzer...")
    mcp = create_playwright_mcp("analysis", config.headless)
    try:
        ana_agent = build_application_analyzer(model, config, mcp)
        ana_result = ana_agent(user_input)
        ana_summary = str(ana_result).strip()[:200]
        print("  -> Application analysis complete.")
    except Exception as e:
        ana_summary = f"FAILED - {e}"
        print(f"  -> Application analysis failed: {e}")

    # Step 2: QA (validates analysis report only)
    print("\n[2/3] Running QA Verifier (analysis only)...")
    qa_task = (
        f"Verify the ANALYSIS report only for: {user_input}\n"
        f"Check analysis reports in: {config.analysis_reports_dir}\n"
        f"Check screenshots in: {config.analysis_screenshots_dir}\n"
        f"Project directory: {config.project_dir}\n"
        f"Note: Accessibility report is not expected — do NOT rerun accessibility agent.\n"
        f"Original user task (pass to run_analysis_agent tool if you need to rerun): {user_input}\n"
        f"CRITICAL: You MUST call file_write to save your QA report to "
        f"{config.project_dir}/qa_report.md before finishing."
    )
    qa_report_path = config.project_dir / "qa_report.md"
    qa_summary = "UNKNOWN"
    try:
        qa_agent = build_qa_verifier(model, config)
        qa_result = qa_agent(qa_task)
        if not qa_report_path.exists():
            result_text = str(qa_result).strip()
            if result_text and len(result_text) > 50:
                qa_report_path.write_text(result_text, encoding="utf-8")
        verdict = parse_qa_verdict(str(qa_report_path))
        qa_summary = verdict.get("overall", "UNKNOWN")
        print(f"  -> QA complete: {qa_summary}")
    except Exception as e:
        qa_summary = f"FAILED - {e}"
        print(f"  -> QA failed: {e}")

    # Step 3: PDF Conversion
    print("\n[3/3] Converting reports to PDF...")
    try:
        pdfs = convert_all_reports(config.project_dir)
        pdf_summary = f"Generated {len(pdfs)} PDF(s)"
        print(f"  -> {pdf_summary}")
    except Exception as e:
        pdf_summary = f"PDF conversion failed: {e}"
        print(f"  -> {pdf_summary}")

    summary = "\n".join([
        "=" * 60,
        "WebAPT Analysis Scan Complete",
        "=" * 60,
        f"Project: {config.project_name}",
        f"Output: {config.project_dir}",
        "",
        f"Analysis: {ana_summary}",
        f"QA: {qa_summary}",
        f"PDF: {pdf_summary}",
        "=" * 60,
    ])
    print(f"\n{summary}")
    return summary


@observe()
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
    langfuse_context.update_current_trace(
        name=f"run_single_agent_{agent_type}",
        input=user_input,
        metadata={"project": config.project_name, "agent_type": agent_type},
    )
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
