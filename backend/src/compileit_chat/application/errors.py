"""Errors that adapters raise across port boundaries, translated from framework exceptions."""


class AgentError(Exception):
    """The chat agent could not produce an answer (provider error, timeout, too many steps)."""
