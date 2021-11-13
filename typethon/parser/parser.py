from __future__ import annotations

import io

from ..scanner import Token, scan


class Parser:
    __slits__ = ('_tokens',)

    def __init__(self, source: io.TextIOBase) -> None:
        self.source = source

        self._tokens = None
        self._position = 0

    def _advance(self, by: int = 1) -> int:
        self._position += by
        return self._position

    def _peek(self, offset: int) -> Token:
        return self._tokens[self._position + offset]

    def _next(self) -> Token:
        try:
            return self._peek(0)
        finally:
            self._advance()

    def parse(self):
        self._tokens = scan(self.source)
