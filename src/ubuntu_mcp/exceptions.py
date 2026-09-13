"""Custom exception hierarchy.

Every exception carries a short machine-readable `code` and a
human-readable `message`. Tool wrappers catch these (and only these,
plus a final generic fallback) and turn them into structured error
responses instead of leaking tracebacks or environment details.
"""

from __future__ import annotations


class MCPServerError(Exception):
    code = "SERVER_ERROR"

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class ValidationError(MCPServerError):
    code = "VALIDATION_ERROR"


class SecurityError(MCPServerError):
    code = "SECURITY_ERROR"


class FileOperationError(MCPServerError):
    code = "FILE_OPERATION_ERROR"


class NotFoundError(MCPServerError):
    code = "NOT_FOUND"


class NetworkError(MCPServerError):
    code = "NETWORK_ERROR"


class ToolExecutionError(MCPServerError):
    code = "TOOL_EXECUTION_ERROR"
