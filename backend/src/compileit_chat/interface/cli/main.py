"""`compileit-chat` CLI: maintenance commands run outside the API."""

from __future__ import annotations

import asyncio
import logging

import typer

from compileit_chat.application.errors import IngestionError
from compileit_chat.config import BACKEND_DIR, Settings
from compileit_chat.container import ConfigurationError, Container
from compileit_chat.interface.cli.generated_docs import with_diagram

ARCHITECTURE_DOC = BACKEND_DIR.parent / "docs" / "architecture.md"

app = typer.Typer(help="Compileit chat maintenance commands.", no_args_is_help=True)


@app.callback()
def _configure_logging(verbose: bool = typer.Option(False, "--verbose", "-v")) -> None:
    logging.basicConfig(
        level=logging.INFO if verbose else logging.WARNING,
        format="%(levelname)s %(name)s: %(message)s",
    )


@app.command()
def ingest(
    crawl: bool = typer.Option(
        True, help="Re-crawl the site. --no-crawl rebuilds the index from the snapshot."
    ),
) -> None:
    """Crawl compileit.com, update the page snapshot and rebuild the search index.

    Idempotent: every run replaces the snapshot and the index wholesale.
    """
    container = Container(Settings())
    try:
        asyncio.run(_ingest(container, crawl=crawl))
    except (ConfigurationError, IngestionError) as error:
        typer.secho(f"Error: {error}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from error


async def _ingest(container: Container, *, crawl: bool) -> None:
    if crawl:
        crawled = await container.ingest_website().execute()
        typer.echo(
            f"Crawl: {crawled.pages_fetched} pages fetched, {crawled.documents} kept "
            f"({crawled.skipped_empty} without content, {crawled.skipped_duplicate} duplicates)"
            f", saved to {container.settings.snapshot_path}"
        )
    indexed = await container.build_index().execute()
    typer.echo(f"Index: {indexed.chunks} chunks from {indexed.documents} pages")


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
