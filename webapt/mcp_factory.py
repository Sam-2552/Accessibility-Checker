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

    # When running headed, ensure the subprocess can find the display server.
    # Background workers (systemd, Flask threads) often lack DISPLAY/WAYLAND_DISPLAY.
    env: dict[str, str] | None = None
    if not headless:
        env = dict(os.environ)
        # Guarantee a DISPLAY is set (fall back to :0 which is the common default)
        if "DISPLAY" not in env and "WAYLAND_DISPLAY" not in env:
            env.setdefault("DISPLAY", ":0")

    return MCPClient(
        lambda args=args, env=env: stdio_client(
            StdioServerParameters(command="npx", args=args, env=env)
        )
    )
