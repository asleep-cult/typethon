from __future__ import annotations

import attr
import enum
import typing


@attr.s(kw_only=True, slots=True, hash=True, eq=True, repr=False)
class NonterminalSymbol:
    name: str = attr.ib(hash=True)
    entrypoint: bool = attr.ib(default=False)
    productions: typing.List[Production] = attr.ib(factory=list, hash=False)

    def __repr__(self) -> str:
        return self.name

    def __str__(self) -> str:
        return f'nonterminal-symbol: {self.name}'

    def dump_nonterminal(self) -> str:
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
    EPSILON = -1


@attr.s(kw_only=True, slots=True, hash=True, eq=True)
class TerminalSymbol:
    kind: str = attr.ib()

    def __str__(self) -> str:
        return self.kind


@attr.s(kw_only=True, slots=True, hash=True, eq=True)
class Production:
    lhs: NonterminalSymbol = attr.ib()
    rhs: typing.List[Symbol] = attr.ib(factory=list, hash=False)

    def __repr__(self) -> str:
        parts: typing.List[str] = [f'{self.lhs.name} ->']
        for symbol in self.rhs:
            if isinstance(symbol, NonterminalSymbol):
                parts.append(symbol.name)
            else:
                parts.append(str(symbol))

        return ' '.join(parts)


EPSILON = TerminalSymbol(kind='EPSILON')
EOF = TerminalSymbol(kind='EOF')

Symbol = typing.Union[NonterminalSymbol, TerminalSymbol]
