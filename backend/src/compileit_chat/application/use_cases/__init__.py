"""Use cases: one class per user-visible operation, receiving its ports via the constructor."""

from compileit_chat.application.use_cases.accounts import (
    Authenticate,
    CreateUser,
    Login,
    LoginResult,
    Logout,
)
from compileit_chat.application.use_cases.ask_question import AskQuestion
from compileit_chat.application.use_cases.build_index import BuildIndex, IndexReport
from compileit_chat.application.use_cases.history import (
    ChatWithHistory,
    DeleteConversation,
    GetConversation,
    ListConversations,
)
from compileit_chat.application.use_cases.ingest_website import IngestReport, IngestWebsite
from compileit_chat.application.use_cases.secrets import StoreSecret

__all__ = [
    "AskQuestion",
    "Authenticate",
    "BuildIndex",
    "ChatWithHistory",
    "CreateUser",
    "DeleteConversation",
    "GetConversation",
    "IndexReport",
    "IngestReport",
    "IngestWebsite",
    "ListConversations",
    "Login",
    "LoginResult",
    "Logout",
    "StoreSecret",
]
