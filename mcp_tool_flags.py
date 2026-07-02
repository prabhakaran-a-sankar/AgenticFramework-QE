"""
MCP Tool Feature Flags

Central on/off switch for every tool exposed by mcp_server.py.

Edit DEFAULT_FLAGS below to change the defaults, or override at runtime
(without editing this file) using environment variables:

    QEAF_ENABLE_STANDALONE_AUTOMATION=false
    QEAF_ENABLE_TEST_ANALYSER=false

The env var name is QEAF_ENABLE_<TOOL_NAME_IN_UPPERCASE>.
Truthy values: 1, true, yes, on.  Falsy values: 0, false, no, off.

A disabled tool is simply NOT registered with the MCP server, so it never
appears in the client's tool list.
"""

import os

from quality_engineering_agentic_framework.utils.logger import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Defaults — flip these to change what is on out of the box.
# ---------------------------------------------------------------------------
DEFAULT_FLAGS = {
    "standalone_automation": True,
    "test_analyser": True,
}

_TRUE_VALUES = {"1", "true", "yes", "on"}
_FALSE_VALUES = {"0", "false", "no", "off"}


def _env_key(tool_name: str) -> str:
    return f"QEAF_ENABLE_{tool_name.upper()}"


def is_tool_enabled(tool_name: str) -> bool:
    """
    Return whether a tool is enabled. Environment variable overrides the
    default; an unknown tool name defaults to disabled.
    """
    raw = os.environ.get(_env_key(tool_name))
    if raw is not None:
        val = raw.strip().lower()
        if val in _TRUE_VALUES:
            return True
        if val in _FALSE_VALUES:
            return False
        logger.warning(
            f"Unrecognized value '{raw}' for {_env_key(tool_name)}; "
            f"falling back to default."
        )
    return DEFAULT_FLAGS.get(tool_name, False)


def enabled_tools() -> list:
    """List of currently-enabled tool names (defaults + env overrides applied)."""
    return [name for name in DEFAULT_FLAGS if is_tool_enabled(name)]
