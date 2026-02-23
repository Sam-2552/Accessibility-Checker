"""Validation tools for the QA Verifier agent."""

import re
from pathlib import Path

from strands import tool


def parse_qa_verdict(qa_report_path: str) -> dict:
    """Parse the VERDICT block from qa_report.md.

    Looks for the machine-readable block at the end of the QA report:

        ## VERDICT
        - accessibility_report: PASS|FAIL|MISSING
        - analysis_report: PASS|FAIL|MISSING
        - screenshots_accessibility: PASS|FAIL|MISSING
        - screenshots_analysis: PASS|FAIL|MISSING
        - overall: PASS|PARTIAL|FAIL

    Returns:
        dict with keys: overall, accessibility_report, analysis_report,
        screenshots_accessibility, screenshots_analysis.
        Returns {'overall': 'UNKNOWN'} if the block is not present or not parseable.
    """
    p = Path(qa_report_path)
    if not p.exists():
        return {"overall": "UNKNOWN"}

    content = p.read_text(encoding="utf-8")

    # Find the VERDICT block (case-insensitive header)
    verdict_match = re.search(r"##\s+VERDICT\s*\n((?:- \S+:\s*\S+\s*\n?)+)", content, re.IGNORECASE)
    if not verdict_match:
        return {"overall": "UNKNOWN"}

    block = verdict_match.group(1)
    result: dict = {}

    for line in block.splitlines():
        m = re.match(r"-\s+(\w+):\s*(\w+)", line.strip())
        if m:
            key = m.group(1).lower()
            value = m.group(2).upper()
            result[key] = value

    if "overall" not in result:
        return {"overall": "UNKNOWN"}

    return result


@tool
def check_file_exists(file_path: str) -> str:
    """Check if a file exists on disk.

    Args:
        file_path: Absolute or relative path to check.

    Returns:
        JSON-like string with exists status and file size if found.
    """
    p = Path(file_path)
    if p.exists():
        size = p.stat().st_size
        return f'{{"exists": true, "path": "{p}", "size_bytes": {size}}}'
    return f'{{"exists": false, "path": "{p}"}}'


@tool
def check_markdown_structure(file_path: str, required_sections: str = "") -> str:
    """Analyze a Markdown file's structure and check for required sections.

    Args:
        file_path: Path to the Markdown file to analyze.
        required_sections: Comma-separated list of required section headings
            (e.g. "Executive Summary,Per-URL Details,Per-Role Details").
            Leave empty to just report the structure.

    Returns:
        Analysis of the Markdown structure including headers found,
        missing required sections, and image references.
    """
    p = Path(file_path)
    if not p.exists():
        return f"Error: File not found: {file_path}"

    content = p.read_text(encoding="utf-8")
    lines = content.split("\n")

    # Extract headers
    headers = []
    for i, line in enumerate(lines, 1):
        match = re.match(r"^(#{1,6})\s+(.+)", line)
        if match:
            level = len(match.group(1))
            title = match.group(2).strip()
            headers.append({"level": level, "title": title, "line": i})

    # Extract image references
    images = re.findall(r"!\[([^\]]*)\]\(([^)]+)\)", content)

    # Extract tables (lines starting with |)
    table_count = len([l for l in lines if l.strip().startswith("|") and "|" in l[1:]])

    # Check required sections
    missing = []
    if required_sections:
        required = [s.strip() for s in required_sections.split(",") if s.strip()]
        found_titles = [h["title"].lower() for h in headers]
        for req in required:
            if not any(req.lower() in t for t in found_titles):
                missing.append(req)

    result_lines = [
        f"## Markdown Structure Analysis: {p.name}",
        f"- Total lines: {len(lines)}",
        f"- Headers found: {len(headers)}",
        f"- Image references: {len(images)}",
        f"- Table rows: {table_count}",
        "",
        "### Headers:",
    ]
    for h in headers:
        indent = "  " * (h["level"] - 1)
        result_lines.append(f"{indent}- {'#' * h['level']} {h['title']} (line {h['line']})")

    if images:
        result_lines.append("")
        result_lines.append("### Image References:")
        for alt, src in images:
            result_lines.append(f"- ![{alt}]({src})")

    if missing:
        result_lines.append("")
        result_lines.append("### Missing Required Sections:")
        for m in missing:
            result_lines.append(f"- {m}")
    elif required_sections:
        result_lines.append("")
        result_lines.append("### All required sections present.")

    return "\n".join(result_lines)


@tool
def list_directory_contents(dir_path: str, pattern: str = "*") -> str:
    """List files in a directory matching an optional glob pattern.

    Args:
        dir_path: Path to the directory to list.
        pattern: Glob pattern to filter files (default: "*" for all files).

    Returns:
        List of files with their sizes, or error if directory not found.
    """
    p = Path(dir_path)
    if not p.exists():
        return f"Error: Directory not found: {dir_path}"
    if not p.is_dir():
        return f"Error: Not a directory: {dir_path}"

    files = sorted(p.glob(pattern))
    if not files:
        return f"No files matching '{pattern}' in {dir_path}"

    result_lines = [f"## Contents of {dir_path} (pattern: {pattern})", ""]
    for f in files:
        if f.is_file():
            size = f.stat().st_size
            result_lines.append(f"- {f.name} ({size:,} bytes)")
        elif f.is_dir():
            result_lines.append(f"- {f.name}/ (directory)")

    result_lines.append(f"\nTotal: {len(files)} items")
    return "\n".join(result_lines)
