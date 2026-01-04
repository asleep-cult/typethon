from __future__ import annotations

import attr
import enum
import typing

from ..syntax.tokens import StdTokenKind, STD_TOKENS, TokenMap, KeywordMap

TokenKindT = typing.TypeVar('TokenKindT', bound=enum.Enum)
KeywordKindT = typing.TypeVar('KeywordKindT', bound=enum.Enum)


class FrozenSymbolTable(typing.Generic[TokenKindT, KeywordKindT]):
    def __init__(
        self,
        tokens: TokenMap[TokenKindT],
        keywords: KeywordMap[KeywordKindT],
    ) -> None:
        self.terminals: typing.List[typing.Union[StdTokenKind, TokenKindT, KeywordKindT]] = []
        for _, token in STD_TOKENS:
            self.terminals.append(token)

        for _, token in tokens:
            self.terminals.append(token)

        for _, keyword in keywords:
            self.terminals.append(keyword)

        self.frozen_productions: typing.List[FrozenProduction] = []
        self.frozen_actions: typing.Dict[int, str] = {}
        self.frozen_nonterminals: typing.Dict[str, FrozenSymbol] = {}

    def get_frozen_terminal(
        self,
        terminal: typing.Union[StdTokenKind, TokenKindT, KeywordKindT]
    ) -> FrozenSymbol:
        return FrozenSymbol(
            kind=FrozenSymbolKind.TERMINAL,
            id=self.terminals.index(terminal),
        )

    def get_frozen_nonterminal(self, name: str) -> FrozenSymbol:
        return self.frozen_nonterminals[name]

    def get_frozen_action(self, production: FrozenProduction) -> typing.Optional[str]:
        return self.frozen_actions.get(production.id)

    def create_frozen_nonterminal(self, name: str) -> FrozenSymbol:
        symbol = FrozenSymbol(
            kind=FrozenSymbolKind.NONTERMINAL,
            id=len(self.frozen_nonterminals),
        )
        self.frozen_nonterminals[name] = symbol
        return symbol

    def create_frozen_production(
        self,
        lhs: FrozenSymbol,
        rhs_length: int,
        captured: typing.Tuple[int, ...],
    ) -> FrozenProduction:
        if lhs.kind is not FrozenSymbolKind.NONTERMINAL:
            raise ValueError('Production lhs must be a nonterminal symbol')

        frozen_production = FrozenProduction(
            id=len(self.frozen_productions),
            lhs=lhs.id,
            rhs_length=rhs_length,
            captured=captured,
        )
        self.frozen_productions.append(frozen_production)
        return frozen_production

    def add_production_action(self, production: FrozenProduction, name: str) -> None:
        self.frozen_actions[production.id] = name


class FrozenSymbolKind(enum.IntEnum):
    NONTERMINAL = enum.auto()
    TERMINAL = enum.auto()


@attr.s(kw_only=True, slots=True, eq=True, hash=True)
class FrozenSymbol:
    kind: FrozenSymbolKind = attr.ib()
    id: int = attr.ib()


@attr.s(kw_only=True, slots=True, eq=True, hash=True)
class FrozenProduction:
    id: int = attr.ib()
    lhs: int = attr.ib()
    rhs_length: int = attr.ib()
    captured: typing.Tuple[int, ...] = attr.ib()

    def get_lhs(self) -> FrozenSymbol:
        return FrozenSymbol(kind=FrozenSymbolKind.NONTERMINAL, id=self.lhs)
