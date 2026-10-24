"""
Assistant persistence services.

Split by aggregate -- threads, messages and runs each own a file -- rather
than the house single-service module, because this one domain carries three
distinct lifecycles. The shared, user-scoped thread lookup and title
derivation live in ``_common``.

Every unit of work is handed to ``run_db`` so the whole session lifecycle
stays inside one worker thread.
"""

from ._common import derive_title, owned_thread
from .message import MessageService
from .run import GENERIC_ERROR_TEXT, RunService
from .thread import ThreadService
from .tool_call_log import ToolCallLogService

__all__ = [
    "ThreadService",
    "MessageService",
    "RunService",
    "ToolCallLogService",
    "GENERIC_ERROR_TEXT",
    "derive_title",
    "owned_thread",
]
