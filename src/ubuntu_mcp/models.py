"""Shared response models and the `@safe_tool` decorator.

Every MCP tool in this project returns the same predictable shape:

    {"success": true,  "data": {...}, "error": null}
    {"success": false, "data": null,  "error": {"code": "...", "message": "..."}}

`@safe_tool` wraps a tool implementation, catches our own exception
hierarchy (and, as a last resort, any other exception) and converts it
into the structured error shape above -- so a failure in one tool call
never crashes the server process and never leaks a stack trace, secret,
or local filesystem detail to the MCP client.
"""

from __future__ import annotations

import functools
import logging
from typing import Any, Awaitable, Callable, Optional, TypeVar

from pydantic import BaseModel

from .exceptions import MCPServerError

logger = logging.getLogger("ubuntu_mcp")

F = TypeVar("F", bound=Callable[..., Awaitable[Any]])


class ErrorDetail(BaseModel):
    code: str
    message: str


class ToolResult(BaseModel):
    success: bool
    data: Optional[Any] = None
    error: Optional[ErrorDetail] = None


def _to_jsonable(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    return value


def safe_tool(func: F) -> F:
    """Decorator: run a tool, always return a plain dict, never raise."""

    @functools.wraps(func)
    async def wrapper(*args: Any, **kwargs: Any) -> dict:
        tool_name = func.__name__
        try:
            result = await func(*args, **kwargs)
            return ToolResult(success=True, data=_to_jsonable(result)).model_dump(
                mode="json"
            )
        except MCPServerError as exc:
            logger.warning("Tool %s failed: [%s] %s", tool_name, exc.code, exc.message)
            return ToolResult(
                success=False, error=ErrorDetail(code=exc.code, message=exc.message)
            ).model_dump(mode="json")
        except Exception as exc:  # noqa: BLE001 - final safety net, never re-raise
            logger.exception("Unhandled error in tool %s", tool_name)
            return ToolResult(
                success=False,
                error=ErrorDetail(
                    code="INTERNAL_ERROR",
                    message=f"An unexpected internal error occurred in '{tool_name}'.",
                ),
            ).model_dump(mode="json")

    return wrapper  # type: ignore[return-value]
