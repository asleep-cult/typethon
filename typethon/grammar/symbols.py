from __future__ import annotations

import enum
import typing

import attr

from ..syntax.tokens import StdTokenKind


@attr.s(kw_only=True, slots=True, hash=False, eq=False, repr=False)
class NonterminalSymbol[TokenKindT: enum.Enum, KeywordKindT: enum.Enum]:
    id: int = attr.ib()
    name: str = attr.ib()
    entrypoint: bool = attr.ib(default=False)
    productions: list[Production[TokenKindT, KeywordKindT]] = attr.ib(factory=list)

    def __hash__(self) -> int:
        return self.id

    def __str__(self) -> str:
        return self.name

    def __repr__(self) -> str:
        return f"<nonterminal-symbol: {self.name}>"

    def dump_nonterminal(self) -> str:
        parts = [f"<nonterminal-symbol: {self.name}>:"]
        for production in self.productions:
            string = "  | "
            for i, symbol in enumerate(production.rhs):
                if i in production.captured:
                    string += "!"

                if isinstance(symbol, NonterminalSymbol):
                    string += f"{symbol.name} "
                else:
                    string += f"{symbol} "

            parts.append(string)

        return "\n".join(parts)


@attr.s(kw_only=True, slots=True, eq=True, hash=False)
class TerminalSymbol[TokenKindT: enum.Enum, KeywordKindT: enum.Enum]:
    id: int = attr.ib()
    kind: TokenKindT | KeywordKindT | StdTokenKind = attr.ib()

    def __str__(self) -> str:
        return str(self.kind)

    def __hash__(self) -> int:
        return self.id


@attr.s(kw_only=True, slots=True, hash=False, eq=False)
class Production[TokenKindT: enum.Enum, KeywordKindT: enum.Enum]:
    id: int = attr.ib()
    lhs: NonterminalSymbol[TokenKindT, KeywordKindT] = attr.ib()
    rhs: list[Symbol[TokenKindT, KeywordKindT]] = attr.ib(factory=list)
    captured: list[int] = attr.ib(factory=list)
    # List of indexes in rhs that should be captured from the parse tree
    action: str | None = attr.ib(default=None)

    def __hash__(self) -> int:
        return self.id

    def add_symbol(self, symbol: Symbol[TokenKindT, KeywordKindT], capture: bool) -> None:
        if capture:
            self.captured.append(len(self.rhs))

        self.rhs.append(symbol)

    def insert_symbol(
        self, index: int, symbol: Symbol[TokenKindT, KeywordKindT], capture: bool
    ) -> None:
        updated_captured: list[int] = []
        if capture:
            updated_captured.append(index)

        for captured in self.captured:
            if captured >= index:
                updated_captured.append(captured + 1)
            else:
                updated_captured.append(captured)

        self.rhs.insert(index, symbol)
        self.captured = updated_captured

    def __repr__(self) -> str:
        parts: list[str] = [f"{self.lhs.name} ->"]
        for symbol in self.rhs:
            if isinstance(symbol, NonterminalSymbol):
                parts.append(symbol.name)
            else:
                parts.append(str(symbol))

        return " ".join(parts)


EOF = TerminalSymbol[typing.Any, typing.Any](id=0, kind=StdTokenKind.EOF)

type Symbol[TokenKindT: enum.Enum, KeywordKindT: enum.Enum] = (
    NonterminalSymbol[TokenKindT, KeywordKindT] | TerminalSymbol[TokenKindT, KeywordKindT]
)
