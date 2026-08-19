from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

_SENTENCE_END = re.compile(r"(?<=[.!?。！？])\s+|\n+")
_SPACE = re.compile(r"\s+")


@dataclass(frozen=True)
class Sentence:
    index: int
    start: int
    end: int
    text: str


def normalize_text(value: str) -> str:
    return _SPACE.sub(" ", unicodedata.normalize("NFKC", value).strip())


def normalize_for_match(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold()
    return re.sub(r"[\s\-_/·.,!?()\[\]{}'\"]+", "", normalized)


def split_sentences(text: str) -> tuple[Sentence, ...]:
    if not text:
        return ()
    sentences: list[Sentence] = []
    cursor = 0
    for match in _SENTENCE_END.finditer(text):
        end = match.start()
        chunk = text[cursor:end].strip()
        if chunk:
            actual_start = text.find(chunk, cursor, end + 1)
            sentences.append(Sentence(len(sentences), actual_start, actual_start + len(chunk), chunk))
        cursor = match.end()
    chunk = text[cursor:].strip()
    if chunk:
        actual_start = text.find(chunk, cursor)
        sentences.append(Sentence(len(sentences), actual_start, actual_start + len(chunk), chunk))
    return tuple(sentences)


def sentence_index_at(sentences: tuple[Sentence, ...], offset: int) -> int:
    for sentence in sentences:
        if sentence.start <= offset <= sentence.end:
            return sentence.index
    return max(0, len(sentences) - 1)


def find_literal_spans(text: str, phrase: str) -> tuple[tuple[int, int], ...]:
    """Find literal spans while tolerating whitespace differences.

    Author aliases remain explicit; this function never invents a semantic match.
    """
    phrase = phrase.strip()
    if not phrase:
        return ()
    pattern = re.escape(phrase)
    pattern = pattern.replace(r"\ ", r"\s*")
    return tuple((match.start(), match.end()) for match in re.finditer(pattern, text, re.IGNORECASE))


def window(text: str, start: int, end: int, radius: int = 24) -> str:
    return text[max(0, start - radius) : min(len(text), end + radius)]
