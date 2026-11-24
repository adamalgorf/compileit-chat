"""Swedish tokenizer for lexical search: case-folded, stop words removed, Snowball-stemmed."""

from __future__ import annotations

import re

import snowballstemmer

_WORD = re.compile(r"[^\W_]+")  # runs of Unicode letters/digits; splits "AI-tjänster"
_LETTER_DIGIT_BOUNDARY = re.compile(r"(?<=[^\W\d_])(?=\d)|(?<=\d)(?=[^\W\d_])")

# Function words that carry no topical signal in questions like "Hur kontaktar man er?".
_STOP_WORDS = frozenset(
    """
    alla allt andra att av bara blir då de dem den denna deras det detta din du där efter
    eller en er era ert ett finns för från får ha har hade hos hur här i in inte jag kan
    man med men mig min mot mycket ni nu när och om oss på sedan sig sin sina ska skulle
    som så till under upp ut vad var vara vid vilka vilken vilket vi vår vårt våra än är
    över the and of to in for
    """.split()
)


class SwedishTokenizer:
    """Text -> search terms. Stemming lets "tjänster" match "tjänst" and "tjänsten".

    The same tokenizer runs on chunks and on queries, so both sides use the same terms.
    """

    def __init__(self) -> None:
        self._stemmer = snowballstemmer.stemmer("swedish")

    def __call__(self, text: str) -> list[str]:
        words = (
            part
            for word in _WORD.findall(text.casefold())
            # "Kundserviceagent01" (a heading glued to a decorative counter) -> two tokens
            for part in _LETTER_DIGIT_BOUNDARY.split(word)
            if part and part not in _STOP_WORDS
        )
        return list(self._stemmer.stemWords(list(words)))
