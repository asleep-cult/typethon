from __future__ import annotations

from typing import Iterable, Optional, Union

from .keywords import KeywordType
from .scanner import Token, TokenType


class TokenStream:
    def __init__(self, tokens: list[Token]) -> None:
        self._tokens = tokens
        self._position = 0

    def tell(self) -> int:
        return self._position

    def at(self, position: Optional[int] = None) -> Token:
        if position is None:
            position = self._position
        return self._tokens[position]

    def advance(self, by: int = 1) -> int:
        self._position += by
        return self._position

    def expect(self, types: Union[TokenType, Iterable[TokenType]]) -> bool:
        if isinstance(types, TokenType):
            types = (types,)
        return self.at().type in types

    def expectkw(self, types: Union[KeywordType, Iterable[KeywordType]]) -> bool:
        if isinstance(types, KeywordType):
            types = (types,)

        token = self.at()
        if token.type is TokenType.IDENTIFIER:
            return token.keyword in types

        return False

    def peek(self, offset: int) -> None:
        return self._tokens[self._position + offset]

    def next(self) -> Token:
        try:
            return self.at()
        finally:
            self.advance()
