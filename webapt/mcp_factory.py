"""Create isolated Playwright MCP clients."""

import os
from pathlib import Path

from dotenv import load_dotenv
from mcp import stdio_client, StdioServerParameters
from strands.tools.mcp import MCPClient

# Load .env so PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH is available
load_dotenv()


def create_playwright_mcp(label: str, headless: bool = True) -> MCPClient:
    """Create an isolated Playwright MCP client.

    Each client gets its own --user-data-dir to prevent state conflicts
    between agents running concurrently.

    Args:
        label: Unique label for this MCP instance (e.g. 'accessibility', 'analysis').
        headless: Whether to run the browser in headless mode.
    """
    base = Path(".playwright-mcp").resolve()
    user_data_dir = base / label
    user_data_dir.mkdir(parents=True, exist_ok=True)

    args = [
        "-y", "@playwright/mcp@latest",
        "--isolated",
        "--user-data-dir", str(user_data_dir),
    ]
    if headless:
        args.insert(2, "--headless")

    # ARM64 / custom Chromium support: pass --executable-path if env var is set
    chromium_exe = os.environ.get("PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH", "").strip()
    if chromium_exe:
        args.extend(["--executable-path", chromium_exe])

    return MCPClient(
        lambda args=args: stdio_client(
            StdioServerParameters(command="npx", args=args)
        )
    )
