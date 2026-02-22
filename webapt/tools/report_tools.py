"""Report generation tools for WebAPT agents."""

import json

from strands import tool


@tool
def write_executive_summary(results_json: str) -> str:
    """Generate a formatted executive summary table from URL check results.

    Args:
        results_json: JSON string with structure:
            [
                {
                    "url": "https://example.com",
                    "status": "accessible",
                    "roles": [
                        {"role": "admin", "login_result": "success", "notes": "Redirected to dashboard"},
                        {"role": "user", "login_result": "failed", "notes": "Invalid credentials error"}
                    ]
                }
            ]

    Returns:
        Formatted Markdown executive summary table.
    """
    try:
        results = json.loads(results_json)
    except json.JSONDecodeError:
        return "Error: Invalid JSON provided. Please provide valid JSON results."

    lines = [
        "## Executive Summary",
        "",
        "| URL | Status | Role | Login Result | Notes |",
        "|-----|--------|------|-------------|-------|",
    ]

    for entry in results:
        url = entry.get("url", "N/A")
        status = entry.get("status", "unknown")
        roles = entry.get("roles", [])

        if not roles:
            lines.append(f"| {url} | {status} | - | - | - |")
        else:
            for i, role_info in enumerate(roles):
                display_url = url if i == 0 else ""
                display_status = status if i == 0 else ""
                role = role_info.get("role", "N/A")
                login_result = role_info.get("login_result", "N/A")
                notes = role_info.get("notes", "")
                lines.append(
                    f"| {display_url} | {display_status} | {role} | {login_result} | {notes} |"
                )

    lines.append("")
    return "\n".join(lines)
