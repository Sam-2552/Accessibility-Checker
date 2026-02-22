"""Screenshot management tools for WebAPT agents."""

import re
import shutil
from datetime import datetime
from pathlib import Path

from strands import tool


@tool
def save_screenshot_with_metadata(
    screenshot_path: str,
    domain: str,
    context: str,
    role: str = "",
    output_dir: str = "./outputs/web_analysis/screenshots",
) -> str:
    """Save a screenshot with standardized naming and return a Markdown image reference.

    Renames/copies the screenshot to follow the naming convention:
    {domain}_{context}_{role}_{timestamp}.png

    Args:
        screenshot_path: Path to the existing screenshot file from browser_take_screenshot.
        domain: The domain being tested (e.g. 'example.com').
        context: What the screenshot shows (e.g. 'landing', 'login', 'dashboard').
        role: The user role if applicable (e.g. 'admin', 'user'). Empty string if not role-specific.
        output_dir: Directory to store the screenshot.

    Returns:
        Markdown image reference string like ![description](path)
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # Sanitize domain for filename
    safe_domain = re.sub(r"[^\w\-]", "_", domain.replace(".", "_"))
    safe_context = re.sub(r"[^\w\-]", "_", context)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M")

    parts = [safe_domain, safe_context]
    if role:
        safe_role = re.sub(r"[^\w\-]", "_", role)
        parts.append(safe_role)
    parts.append(timestamp)

    new_name = "_".join(parts) + ".png"
    new_path = output_path / new_name

    # Copy the screenshot
    src = Path(screenshot_path)
    if src.exists():
        shutil.copy2(str(src), str(new_path))
    else:
        return f"Error: screenshot not found at {screenshot_path}"

    description = f"{context}"
    if role:
        description += f" ({role})"
    description += f" - {domain}"

    return f"Screenshot saved. Use in report as: ![{description}]({new_path})"
