from __future__ import annotations

import attr
import enum
import typing
import io

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

    def get_nonterminal_name_by_id(self, id: int) -> str:
        for name, nonterminal in self.frozen_nonterminals.items():
            if nonterminal.id == id:
                return name

        return 'unknown'

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


class ActionKind(enum.IntEnum):
    SHIFT = enum.auto()
    REDUCE = enum.auto()
    ACCEPT = enum.auto()
    REJECT = enum.auto()


class FrozenParserTable(typing.Generic[TokenKindT, KeywordKindT]):
    def __init__(self, frozen_symbols: FrozenSymbolTable[TokenKindT, KeywordKindT]) -> None:
        self.frozen_symbols = frozen_symbols
        self.actions: typing.Dict[
            typing.Tuple[int, FrozenSymbol], typing.Tuple[ActionKind, int]
        ] = {}
        self.gotos: typing.Dict[typing.Tuple[int, FrozenSymbol], int] = {}

    def get_action(self, state_id: int, symbol: FrozenSymbol) -> typing.Optional[
        typing.Tuple[ActionKind, int]
    ]:
        return self.actions.get((state_id, symbol))

    def get_goto(self, state_id: int, symbol: FrozenSymbol) -> typing.Optional[int]:
        return self.gotos.get((state_id, symbol))

    def dump_table(self) -> str:
        grouped_tables: typing.Dict[
            int, 
            typing.Tuple[
                typing.List[
                    typing.Tuple[FrozenSymbol, ActionKind, int]
                ],  # Actions
                typing.List[typing.Tuple[FrozenSymbol, int]],  # GOTOs
            ]
        ] = {}

        for key, value in self.actions.items():
            if key[0] not in grouped_tables:
                grouped_tables[key[0]] = ([], [])

            item = grouped_tables[key[0]]
            actions = item[0]
            actions.append((key[1], *value))

        for key, value in self.gotos.items():
            if key[0] not in grouped_tables:
                grouped_tables[key[0]] = ([], [])

            item = grouped_tables[key[0]]
            gotos = item[1]
            gotos.append((key[1], value))

        writer = io.StringIO()

        for state_id, item in grouped_tables.items():
            writer.write(f'<state #{state_id}>\n')

            actions = item[0]
            writer.write(f'[ Actions: {len(actions)} ]\n')
            for symbol, action, number in actions:
                terminal = self.frozen_symbols.terminals[symbol.id]
                writer.write(f'  (for symbol {str(terminal)!r}) {action.name} ')

                match action:
                    case ActionKind.SHIFT:
                        writer.write(f'-> state #{number}')
                    case ActionKind.REDUCE:
                        production = self.frozen_symbols.frozen_productions[number]
                        name = self.frozen_symbols.get_nonterminal_name_by_id(production.lhs)
                        writer.write(f'[production: {name}]')

                writer.write('\n')

            gotos = item[1]
            writer.write(f'[ GOTOs: {len(gotos)} ]\n')
            for symbol, destination_id in gotos:
                symbol_name = 'unknown'
                for name, nonterminal in self.frozen_symbols.frozen_nonterminals.items():
                    if nonterminal.id == symbol.id:
                        symbol_name = name

                writer.write(f'  (for symbol {str(symbol_name)!r}) -> state #{destination_id}\n')

        writer.write('\n')

        return writer.getvalue()
