"""`compileit-chat` CLI: maintenance and administration commands run outside the API."""

from __future__ import annotations

import asyncio
import logging
import sys
from typing import TYPE_CHECKING

import typer

from compileit_chat.application.errors import IngestionError, UserExistsError
from compileit_chat.application.use_cases.secrets import KNOWN_SECRETS
from compileit_chat.config import BACKEND_DIR, Settings
from compileit_chat.container import ConfigurationError, Container
from compileit_chat.domain.errors import DomainError
from compileit_chat.interface.cli.generated_docs import with_diagram

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

ARCHITECTURE_DOC = BACKEND_DIR.parent / "docs" / "architecture.md"
_EXPECTED_ERRORS = (ConfigurationError, IngestionError, DomainError, UserExistsError, ValueError)

app = typer.Typer(help="Compileit chat maintenance commands.", no_args_is_help=True)


@app.callback()
def _configure_logging(verbose: bool = typer.Option(False, "--verbose", "-v")) -> None:
    logging.basicConfig(
        level=logging.INFO if verbose else logging.WARNING,
        format="%(levelname)s %(name)s: %(message)s",
    )


def _run(command: Callable[[Container], Awaitable[None]]) -> None:
    """Run an async command against a started container; expected errors exit 1 cleanly."""

    async def main() -> None:
        container = Container(Settings())
        try:
            await container.start()  # migrate the database, load secrets
            await command(container)
        finally:
            await container.stop()

    try:
        asyncio.run(main())
    except _EXPECTED_ERRORS as error:
        typer.secho(f"Error: {error}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from error


def _secret_input(prompt: str, from_stdin: bool) -> str:
    """Hidden, confirmed prompt; or one line from stdin for scripts (never a CLI argument,
    which would end up in shell history and process listings)."""
    if from_stdin:
        # Strip the line ending only (CRLF too, from files made on Windows); spaces are kept,
        # since they can be part of a password.
        return sys.stdin.readline().rstrip("\r\n")
    value: str = typer.prompt(prompt, hide_input=True, confirmation_prompt=True)
    return value


# --- content -----------------------------------------------------------------------------


@app.command()
def ingest(
    crawl: bool = typer.Option(
        True, help="Re-crawl the site. --no-crawl rebuilds the index from the snapshot."
    ),
) -> None:
    """Crawl compileit.com, update the page snapshot and rebuild the search index.

    Idempotent: every run replaces the snapshot and the index wholesale.
    """

    async def command(container: Container) -> None:
        if crawl:
            crawled = await container.ingest_website().execute()
            typer.echo(
                f"Crawl: {crawled.pages_fetched} pages fetched, {crawled.documents} kept "
                f"({crawled.skipped_empty} without content, {crawled.skipped_duplicate} "
                f"duplicates), saved to {container.settings.snapshot_path}"
            )
        indexed = await container.build_index().execute()
        typer.echo(f"Index: {indexed.chunks} chunks from {indexed.documents} pages")

    _run(command)


# --- database and accounts ---------------------------------------------------------------


@app.command("db-upgrade")
def db_upgrade() -> None:
    """Create or migrate the database schema (the API also does this on startup)."""

    async def command(container: Container) -> None:
        typer.echo("Database is up to date.")

    _run(command)


@app.command("create-user")
def create_user(
    username: str,
    password_stdin: bool = typer.Option(
        False, "--password-stdin", help="Read the password from stdin instead of prompting."
    ),
) -> None:
    """Create a login. The password is hashed with Argon2id; only the hash is stored."""
    password = _secret_input("Lösenord", password_stdin)

    async def command(container: Container) -> None:
        user = await container.create_user().execute(username, password)
        typer.echo(f"Created user {user.username}.")

    _run(command)


@app.command("set-secret")
def set_secret(
    name: str = typer.Argument(help=f"One of: {', '.join(sorted(KNOWN_SECRETS))}"),
    value_stdin: bool = typer.Option(
        False, "--value-stdin", help="Read the value from stdin instead of prompting."
    ),
) -> None:
    """Store a secret in the database, encrypted with SECRETS_MASTER_KEY."""
    value = _secret_input(name, value_stdin)

    async def command(container: Container) -> None:
        await container.store_secret().execute(name, value)
        typer.echo(f"Stored {name} (encrypted).")

    _run(command)


@app.command("new-master-key")
def new_master_key() -> None:
    """Print a new random SECRETS_MASTER_KEY. Keep it outside the code and the database."""
    typer.echo(Container.new_master_key())


# --- docs --------------------------------------------------------------------------------


@app.command()
def docs(
    check: bool = typer.Option(
        False, "--check", help="Only verify the docs are up to date (exit 1 if not)."
    ),
) -> None:
    """Regenerate the orchestration graph diagram in docs/architecture.md from code."""
    path = ARCHITECTURE_DOC
    current = path.read_text(encoding="utf-8")
    updated = with_diagram(current, Container(Settings()).orchestration_diagram())
    if check:
        if updated != current:
            typer.secho(f"{path} is out of date: run `make docs`.", fg=typer.colors.RED, err=True)
            raise typer.Exit(code=1)
        typer.echo(f"{path} is up to date.")
        return
    path.write_text(updated, encoding="utf-8", newline="\n")
    typer.echo(f"Updated {path}")
