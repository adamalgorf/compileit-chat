"""Crawler tests against an in-memory site served by `httpx.MockTransport` (no network)."""

from __future__ import annotations

import httpx

from compileit_chat.infrastructure.crawling.crawler import CrawlConfig, SitemapCrawler

SITE = "https://example.com"
HTML = "text/html; charset=utf-8"


def sitemap(*locs: str, index: bool = False) -> str:
    tag, item = ("sitemapindex", "sitemap") if index else ("urlset", "url")
    entries = "".join(f"<{item}><loc>{loc}</loc></{item}>" for loc in locs)
    return f'<{tag} xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{entries}</{tag}>'


def page(*links: str) -> str:
    anchors = "".join(f'<a href="{href}">x</a>' for href in links)
    return f"<html><body><main>{anchors}</main></body></html>"


class FakeSite:
    """Routes by path; records every requested path."""

    def __init__(self, routes: dict[str, tuple[int, str, str]]) -> None:
        self.routes = routes
        self.requested: list[str] = []

    def handle(self, request: httpx.Request) -> httpx.Response:
        self.requested.append(request.url.path)
        if request.url.host not in ("example.com", "www.example.com"):
            return httpx.Response(404)
        status, content_type, body = self.routes.get(request.url.path, (404, "text/plain", ""))
        if status in (301, 308):
            return httpx.Response(status, headers={"location": body})
        return httpx.Response(status, headers={"content-type": content_type}, text=body)


async def crawl(site: FakeSite, **config: object) -> list[str]:
    crawler = SitemapCrawler(
        CrawlConfig(site_url=SITE, user_agent="test-bot", **config),
        transport=httpx.MockTransport(site.handle),
    )
    return [p.url async for p in crawler.crawl()]


async def test_sitemap_first_respects_robots_scope_and_content_type() -> None:
    site = FakeSite(
        {
            "/robots.txt": (
                200,
                "text/plain",
                f"User-agent: *\nDisallow: /privat\nSitemap: {SITE}/sitemap-index.xml",
            ),
            "/sitemap-index.xml": (
                200,
                "application/xml",
                sitemap(f"{SITE}/pages.xml", index=True),
            ),
            "/pages.xml": (
                200,
                "application/xml",
                sitemap(
                    "https://www.example.com/",  # www and trailing slash are canonicalised
                    f"{SITE}/om-oss/",
                    f"{SITE}/privat/hemligt",  # disallowed by robots.txt
                    f"{SITE}/medarbetare/1-anna",  # excluded by pattern
                    f"{SITE}/broschyr.pdf",  # not HTML by suffix
                    f"{SITE}/bild",  # not HTML by content type
                    f"{SITE}/saknas",  # 404
                    "https://other.com/x",  # off-site
                ),
            ),
            "/": (200, HTML, page("/inte-i-sitemap")),
            "/om-oss": (200, HTML, page()),
            "/bild": (200, "image/png", ""),
        }
    )

    urls = await crawl(site, exclude_patterns=(r"^/medarbetare/",))

    assert sorted(urls) == [SITE, f"{SITE}/om-oss"]
    assert "/privat/hemligt" not in site.requested
    assert "/medarbetare/1-anna" not in site.requested
    assert "/inte-i-sitemap" not in site.requested  # sitemap mode does not follow links


async def test_falls_back_to_link_crawl_bounded_by_depth() -> None:
    site = FakeSite(
        {
            "/": (
                200,
                HTML,
                page("/a", "/b#sektion", "https://other.com/", "mailto:x@example.com"),
            ),
            "/a": (200, HTML, page("/c", "/")),
            "/b": (200, HTML, page()),
            "/c": (200, HTML, page()),
        }
    )

    urls = await crawl(site, max_depth=1)

    assert sorted(urls) == [SITE, f"{SITE}/a", f"{SITE}/b"]


async def test_stops_at_max_pages() -> None:
    locs = [f"{SITE}/sida-{i}" for i in range(5)]
    routes = {f"/sida-{i}": (200, HTML, page()) for i in range(5)}
    site = FakeSite({"/sitemap.xml": (200, "application/xml", sitemap(*locs)), **routes})

    assert len(await crawl(site, max_pages=2)) == 2


async def test_redirect_is_recorded_under_its_final_url() -> None:
    site = FakeSite(
        {
            "/sitemap.xml": (200, "application/xml", sitemap(f"{SITE}/gammal")),
            "/gammal": (308, "", f"{SITE}/ny"),
            "/ny": (200, HTML, page()),
        }
    )

    assert await crawl(site) == [f"{SITE}/ny"]


async def test_forbidden_robots_txt_means_nothing_is_fetched() -> None:
    site = FakeSite(
        {
            "/robots.txt": (403, "text/plain", ""),
            "/sitemap.xml": (200, "application/xml", sitemap(f"{SITE}/om-oss")),
            "/om-oss": (200, HTML, page()),
        }
    )

    assert await crawl(site) == []
    assert "/om-oss" not in site.requested
