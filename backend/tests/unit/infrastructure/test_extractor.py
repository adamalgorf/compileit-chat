"""The extractor against HTML shaped like compileit.com's (Next.js, semantic <main>)."""

from datetime import UTC, datetime

from compileit_chat.domain.documents import Document, FetchedPage, Language
from compileit_chat.infrastructure.crawling.extractor import MainContentExtractor

NOW = datetime(2026, 11, 17, tzinfo=UTC)

CONTACT_PAGE = """
<html lang="sv"><head><title>Kontakta oss | Compileit</title></head><body>
  <header><nav><a href="/om-oss">Om oss</a></nav></header>
  <main>
    <h1>Kontakta oss</h1>
    <h2>Våra kontor</h2>
    <h3>Stockholm</h3><p>Olof Palmes Gata 13</p><p>111 37 Stockholm</p>
    <h2>Kontakta oss</h2>
    <p>Mejla oss på <a href="mailto:hello@compileit.com">hello@compileit.com</a>.</p>
    <form><input name="email"><button>Skicka</button></form>
    <h3>Jonathan<!-- comment --> Ortheden</h3><p>CEO</p>
    <a href="mailto:jonathan@compileit.com">jonathan@compileit.com</a>
    <a href="/uppdrag">Se våra uppdrag</a>
    <div aria-hidden="true"><p>Olof Palmes Gata 13 (karusellkopia)</p></div>
  </main>
  <footer><p>© Compileit</p></footer>
</body></html>
"""


def extract(html: str, url: str = "https://compileit.com/kontakt") -> Document | None:
    return MainContentExtractor().extract(FetchedPage(url=url, html=html, fetched_at=NOW))


def test_renders_main_as_markdown_without_site_chrome() -> None:
    document = extract(CONTACT_PAGE)

    assert document is not None
    assert document.text == (
        "# Kontakta oss\n\n"
        "## Våra kontor\n\n"
        "### Stockholm\n\n"
        "Olof Palmes Gata 13\n\n"
        "111 37 Stockholm\n\n"
        "## Kontakta oss\n\n"
        "Mejla oss på hello@compileit.com.\n\n"
        "### Jonathan Ortheden\n\n"
        "CEO\n\n"
        "jonathan@compileit.com"
    )


def test_keeps_hero_header_and_button_wrapped_headings_inside_main() -> None:
    html = """<html><body><header><p>Sitens meny</p></header><main>
        <header><h1>Toppa din organisation med AI</h1><p>Gör som SkiStar.</p></header>
        <button aria-expanded="false"><h3>Ekonomiassistent</h3></button>
        <button>Boka möte</button>
    </main></body></html>"""

    document = extract(html)

    assert document is not None
    assert document.text == (
        "# Toppa din organisation med AI\n\nGör som SkiStar.\n\n### Ekonomiassistent"
    )


def test_metadata_comes_from_title_and_html_lang() -> None:
    document = extract(CONTACT_PAGE)

    assert document is not None
    assert (document.title, document.lang, document.url, document.crawled_at) == (
        "Kontakta oss",
        Language.SWEDISH,
        "https://compileit.com/kontakt",
        NOW,
    )


def test_repeated_blocks_from_responsive_variants_are_kept_once() -> None:
    html = """<html><body><main>
        <div class="mobile"><h3>AI</h3>
            <p>Smart teknik som gör nytta på riktigt, utan krångel.</p></div>
        <div class="desktop"><h3>AI</h3>
            <p>Smart teknik som gör nytta på riktigt, utan krångel.</p></div>
    </main></body></html>"""

    document = extract(html)

    assert document is not None
    assert document.text == "### AI\n\nSmart teknik som gör nytta på riktigt, utan krångel."


def test_list_items_wrapping_paragraphs_become_bullets() -> None:
    html = """<html><body><main><h2>Frågor vi besvarar</h2><ul>
        <li><p>Var kan AI skapa störst affärsnytta?</p></li>
        <li>Hur säkerställer vi dataskydd?</li>
    </ul></main></body></html>"""

    document = extract(html)

    assert document is not None
    assert document.text == (
        "## Frågor vi besvarar\n\n"
        "- Var kan AI skapa störst affärsnytta?\n\n"
        "- Hur säkerställer vi dataskydd?"
    )


def test_heading_text_excludes_nested_paragraph_and_separates_block_children() -> None:
    html = """<html><body><main>
        <h3>Kundserviceagent<div>01</div><p>Hanterar upp till 60 % av kundtjänsten.</p></h3>
    </main></body></html>"""

    document = extract(html)

    assert document is not None
    assert document.text == "### Kundserviceagent 01\n\nHanterar upp till 60 % av kundtjänsten."


def test_title_falls_back_to_h1_and_language_to_unknown() -> None:
    html = (
        "<html><body><main><h1>Om oss</h1>"
        "<p>Vi bygger digitala tjänster som människor älskar.</p></main></body></html>"
    )

    document = extract(html)

    assert document is not None
    assert (document.title, document.lang) == ("Om oss", Language.UNKNOWN)


def test_pages_without_meaningful_content_are_skipped() -> None:
    assert extract("<html><body><main><p>Laddar…</p></main></body></html>") is None


def test_pages_without_main_fall_back_to_trafilatura() -> None:
    paragraph = "Compileit bygger appar, webb och AI-lösningar för svenska företag. " * 5
    html = f"<html lang='sv'><body><article><h1>Om</h1><p>{paragraph}</p></article></body></html>"

    document = extract(html)

    assert document is not None
    assert "Compileit bygger appar" in document.text
