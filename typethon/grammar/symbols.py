from __future__ import annotations

import attr
import enum
import typing

from ..syntax.tokens import TokenKind


@attr.s(kw_only=True, slots=True, hash=True, eq=True, repr=False)
class NonterminalSymbol:
    name: str = attr.ib(hash=True)
    entrypoint: bool = attr.ib(default=False)
    productions: typing.List[Production] = attr.ib(factory=list, hash=False)

    def __str__(self) -> str:
        return f'nonterminal-symbol: {self.name}'

    def __repr__(self) -> str:
        parts = [f'<nonterminal-symbol: {self.name}>:']
        for production in self.productions:
            string = '  | '
            for symbol in production.rhs:
                if isinstance(symbol, NonterminalSymbol):
                    string += f'{symbol.name} '
                else:
                    string += f'{symbol} '

            parts.append(string)

        return '\n'.join(parts)


class TerminalKind(enum.IntEnum):
    EPSILON = enum.auto()


@attr.s(kw_only=True, slots=True, hash=True, eq=True)
class TerminalSymbol:
    kind: int = attr.ib()

    def __str__(self) -> str:
        return self.kind.name


@attr.s(kw_only=True, slots=True, hash=True, eq=True)
class Production:
    lhs: NonterminalSymbol = attr.ib()
    rhs: typing.List[Symbol] = attr.ib(factory=list, hash=False)

    def __str__(self) -> str:
        parts: typing.List[str] = []
        for symbol in self.rhs:
            if isinstance(symbol, NonterminalSymbol):
                parts.append(symbol.name)
            else:
                parts.append(str(symbol))

        return ' '.join(parts)


EPSILON = TerminalSymbol(kind=TerminalKind.EPSILON)
EOF = TerminalSymbol(kind=TokenKind.EOF)

Symbol = typing.Union[NonterminalSymbol, TerminalSymbol]
