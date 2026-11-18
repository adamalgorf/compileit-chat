"""Errors that adapters raise across port boundaries, translated from framework exceptions."""


class AgentError(Exception):
    """The chat agent could not produce an answer (provider error, timeout, too many steps)."""


class IngestionError(Exception):
    """Ingestion or indexing cannot proceed; existing content is left untouched."""


class AuthenticationError(Exception):
    """Wrong username or password, or an inactive account. Deliberately unspecific."""


class UserExistsError(Exception):
    """A user with this username already exists."""


class ConversationNotFoundError(Exception):
    """No such conversation for this user (also used when it belongs to someone else)."""
