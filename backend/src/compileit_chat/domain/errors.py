"""Errors raised when domain invariants are violated."""


class DomainError(Exception):
    """Base class for all domain errors."""


class InvalidSessionIdError(DomainError):
    """The session id is missing or has an unsupported format."""


class InvalidQuestionError(DomainError):
    """The question is empty or too long."""


class InvalidUsernameError(DomainError):
    """The username has an unsupported format."""


class WeakPasswordError(DomainError):
    """A new password does not meet the password rules."""
