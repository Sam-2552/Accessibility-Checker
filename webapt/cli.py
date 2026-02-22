"""CLI entry point for WebAPT."""

import argparse
import sys

from .config import WebAPTConfig
from .md_to_pdf import convert_all_reports
from .orchestrator import run_full_pipeline, run_single_agent


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="webapt",
        description="WebAPT - Web Application Access and Analysis Checker",
    )
    parser.add_argument(
        "--project", "-p",
        default=None,
        help="Project name (used for output directory and sessions)",
    )
    parser.add_argument(
        "--task", "-t",
        default=None,
        help="Task description (non-interactive single run)",
    )
    parser.add_argument(
        "--agent", "-a",
        choices=["accessibility", "analysis", "qa"],
        default=None,
        help="Run a single agent instead of the full pipeline",
    )
    parser.add_argument(
        "--convert-pdf",
        action="store_true",
        default=False,
        help="Only convert existing Markdown reports to PDF (no agent run)",
    )
    parser.add_argument(
        "--no-pdf",
        action="store_true",
        default=False,
        help="Skip PDF conversion after agent run",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        default=None,
        help="Run browser in headless mode (default: from env or true)",
    )
    parser.add_argument(
        "--headed",
        action="store_true",
        default=False,
        help="Run browser in headed (visible) mode",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)

    config = WebAPTConfig.from_env(project_name=args.project)

    # Override headless from CLI flags
    if args.headed:
        config.headless = False
    elif args.headless:
        config.headless = True

    # PDF-only mode
    if args.convert_pdf:
        config.ensure_dirs()
        print(f"Converting reports in {config.project_dir} to PDF...")
        pdfs = convert_all_reports(config.project_dir)
        if pdfs:
            for pdf in pdfs:
                print(f"  -> {pdf}")
            print(f"\nGenerated {len(pdfs)} PDF(s).")
        else:
            print("No Markdown reports found to convert.")
        return

    # Non-interactive single run
    if args.task:
        if args.agent:
            run_single_agent(
                args.agent, args.task, config,
                convert_pdf=not args.no_pdf,
            )
        else:
            run_full_pipeline(args.task, config)
        return

    # Interactive mode
    print("=" * 60)
    print("  WebAPT - Web Application Access and Analysis Checker")
    print("=" * 60)
    print(f"  Project: {config.project_name}")
    print(f"  Provider: {config.provider}")
    print(f"  Output: {config.project_dir}")
    print()
    print("Commands:")
    print("  Type a task description to run the full pipeline")
    print("  'accessibility <task>' - Run accessibility check only")
    print("  'analysis <task>'     - Run application analysis only")
    print("  'qa'                  - Run QA verification only")
    print("  'pdf'                 - Convert reports to PDF")
    print("  'exit' / 'quit'       - Exit")
    print()

    while True:
        try:
            user_input = input("webapt> ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nExiting...")
            break

        if not user_input:
            continue

        if user_input.lower() in ("exit", "quit"):
            break

        if user_input.lower() == "pdf":
            config.ensure_dirs()
            pdfs = convert_all_reports(config.project_dir)
            if pdfs:
                for pdf in pdfs:
                    print(f"  -> {pdf}")
            else:
                print("No reports found to convert.")
            continue

        if user_input.lower() == "qa":
            run_single_agent("qa", "Verify all generated reports", config, convert_pdf=False)
            continue

        # Check for agent-specific prefixes
        for prefix in ("accessibility", "analysis"):
            if user_input.lower().startswith(prefix + " "):
                task = user_input[len(prefix) + 1:].strip()
                if task:
                    run_single_agent(prefix, task, config, convert_pdf=not args.no_pdf)
                    break
        else:
            # Full pipeline
            run_full_pipeline(user_input, config)

        print()


if __name__ == "__main__":
    main()
