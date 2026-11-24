"""Sitemap-first website crawler that respects robots.txt.

Discovery: URLs from the sitemap(s) announced in robots.txt (or /sitemap.xml). Only if that
yields nothing does it fall back to following same-site links from the start page, bounded
by depth and page count.
"""

from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from urllib.parse import urljoin, urlsplit, urlunsplit
from urllib.robotparser import RobotFileParser
from xml.etree import ElementTree

import httpx
from lxml import html as lxml_html

from compileit_chat.domain.documents import FetchedPage

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

logger = logging.getLogger(__name__)

_SITEMAP_NS = "{http://www.sitemaps.org/schemas/sitemap/0.9}"
_MAX_SITEMAP_NESTING = 2
_NON_HTML_SUFFIXES = (".pdf", ".jpg", ".jpeg", ".png", ".gif", ".svg", ".webp", ".zip", ".mp4")


@dataclass(frozen=True, slots=True)
class CrawlConfig:
    """Crawl scope and limits; the defaults are polite for a small site."""

    site_url: str
    user_agent: str
    max_pages: int = 200
    max_depth: int = 3
    concurrency: int = 4
    timeout_seconds: float = 15.0
    exclude_patterns: tuple[str, ...] = ()


class SitemapCrawler:
    """`WebCrawlerPort` adapter: sitemap first and robots.txt respected. It follows links only when
    the site has no usable sitemap.
    """

    def __init__(
        self, config: CrawlConfig, transport: httpx.AsyncBaseTransport | None = None
    ) -> None:
        self._config = config
        self._transport = transport  # injectable for tests
        root = urlsplit(config.site_url)
        self._scheme = root.scheme
        self._netloc = root.netloc.lower()
        self._excludes = [re.compile(pattern) for pattern in config.exclude_patterns]

    async def crawl(self) -> AsyncIterator[FetchedPage]:
        """Yield each in-scope HTML page once, fetching a few at a time."""
        async with self._client() as client:
            robots = await self._load_robots(client)
            seeds = await self._sitemap_urls(client, robots)
            follow_links = not seeds
            if follow_links:
                logger.warning("No sitemap URLs found; falling back to following links")
                seeds = [self._canonical(self._config.site_url)]
            else:
                logger.info("Sitemap lists %d in-scope URLs", len(seeds))
            async for page in self._fetch_breadth_first(client, robots, seeds, follow_links):
                yield page

    # --- discovery -----------------------------------------------------------------------

    async def _load_robots(self, client: httpx.AsyncClient) -> RobotFileParser:
        robots = RobotFileParser()
        try:
            response = await client.get(self._absolute("/robots.txt"))
        except httpx.HTTPError:
            logger.warning("robots.txt unreachable; assuming everything is allowed")
            robots.parse([])
            return robots
        # Same semantics as urllib's own loader: auth errors forbid, other 4xx allow.
        if response.status_code in (401, 403):
            robots.parse(["User-agent: *", "Disallow: /"])
        elif response.status_code >= 400:
            robots.parse([])
        else:
            robots.parse(response.text.splitlines())
        return robots

    async def _sitemap_urls(self, client: httpx.AsyncClient, robots: RobotFileParser) -> list[str]:
        pending = [(url, 0) for url in robots.site_maps() or [self._absolute("/sitemap.xml")]]
        urls: dict[str, None] = {}  # ordered set
        while pending:
            sitemap_url, nesting = pending.pop(0)
            for loc, is_index in await self._read_sitemap(client, sitemap_url):
                if is_index and nesting < _MAX_SITEMAP_NESTING:
                    pending.append((loc, nesting + 1))
                elif not is_index and self._in_scope(loc):
                    urls[self._canonical(loc)] = None
        return list(urls)

    async def _read_sitemap(self, client: httpx.AsyncClient, url: str) -> list[tuple[str, bool]]:
        """(loc, is_nested_sitemap) pairs; empty if the sitemap is missing or malformed."""
        try:
            response = await client.get(url)
            response.raise_for_status()
            root = ElementTree.fromstring(response.content)
        except (httpx.HTTPError, ElementTree.ParseError) as error:
            logger.warning("Could not read sitemap %s: %s", url, error)
            return []
        is_index = root.tag == f"{_SITEMAP_NS}sitemapindex"
        return [
            (loc.text.strip(), is_index)
            for loc in root.iter(f"{_SITEMAP_NS}loc")
            if loc.text and loc.text.strip()
        ]

    # --- fetching ------------------------------------------------------------------------

    async def _fetch_breadth_first(
        self,
        client: httpx.AsyncClient,
        robots: RobotFileParser,
        seeds: list[str],
        follow_links: bool,
    ) -> AsyncIterator[FetchedPage]:
        delay = float(robots.crawl_delay(self._config.user_agent) or 0)
        semaphore = asyncio.Semaphore(1 if delay else self._config.concurrency)
        seen, frontier, depth, fetched = set(seeds), seeds, 0, 0

        while frontier and fetched < self._config.max_pages:
            batch = frontier[: self._config.max_pages - fetched]
            pages = await asyncio.gather(
                *(self._fetch(client, semaphore, robots, url, delay) for url in batch)
            )
            next_frontier: list[str] = []
            for page in pages:
                if page is None:
                    continue
                fetched += 1
                yield page
                if follow_links and depth < self._config.max_depth:
                    new_links = [link for link in self._links(page) if link not in seen]
                    seen.update(new_links)
                    next_frontier.extend(new_links)
            frontier, depth = next_frontier, depth + 1

    async def _fetch(
        self,
        client: httpx.AsyncClient,
        semaphore: asyncio.Semaphore,
        robots: RobotFileParser,
        url: str,
        delay: float,
    ) -> FetchedPage | None:
        if not robots.can_fetch(self._config.user_agent, url):
            logger.info("Disallowed by robots.txt: %s", url)
            return None
        async with semaphore:
            try:
                response = await client.get(url)
            except httpx.HTTPError as error:
                logger.warning("Fetch failed for %s: %s", url, error)
                return None
            finally:
                if delay:
                    await asyncio.sleep(delay)

        final_url = self._canonical(str(response.url))
        if response.status_code != httpx.codes.OK:
            logger.warning("Skipping %s: HTTP %d", url, response.status_code)
            return None
        if "text/html" not in response.headers.get("content-type", ""):
            logger.info("Skipping non-HTML %s", url)
            return None
        if not self._in_scope(final_url):
            logger.info("Skipping %s: redirected off-site to %s", url, final_url)
            return None
        return FetchedPage(url=final_url, html=response.text, fetched_at=datetime.now(UTC))

    def _links(self, page: FetchedPage) -> list[str]:
        tree = lxml_html.fromstring(page.html)
        hrefs = (anchor.get("href") for anchor in tree.iter("a"))
        absolute = (urljoin(page.url, href) for href in hrefs if href)
        return list(dict.fromkeys(self._canonical(u) for u in absolute if self._in_scope(u)))

    # --- URL scope -----------------------------------------------------------------------

    def _in_scope(self, url: str) -> bool:
        parts = urlsplit(url)
        return (
            parts.scheme in ("http", "https")
            and _bare_host(parts.netloc) == _bare_host(self._netloc)
            and not parts.path.lower().endswith(_NON_HTML_SUFFIXES)
            and not any(pattern.search(parts.path) for pattern in self._excludes)
        )

    def _canonical(self, url: str) -> str:
        """Site's own scheme and host (www/apex unified), no query, fragment or trailing slash."""
        path = urlsplit(url).path.rstrip("/")
        return urlunsplit((self._scheme, self._netloc, path, "", ""))

    def _absolute(self, path: str) -> str:
        return urlunsplit((self._scheme, self._netloc, path, "", ""))

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            transport=self._transport,
            headers={"User-Agent": self._config.user_agent},
            timeout=self._config.timeout_seconds,
            follow_redirects=True,
        )


def _bare_host(netloc: str) -> str:
    host = netloc.lower()
    return host.removeprefix("www.")
