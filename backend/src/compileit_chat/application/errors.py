"""Errors that adapters raise across port boundaries, translated from framework exceptions."""


class AgentError(Exception):
    """The chat agent could not produce an answer (provider error, timeout, too many steps)."""


class IngestionError(Exception):
    """Ingestion or indexing cannot proceed; existing content is left untouched."""
