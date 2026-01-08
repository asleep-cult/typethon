from __future__ import annotations

import attr
import enum
import typing
import io

from .symbols import Symbol, TerminalSymbol

TokenKindT = typing.TypeVar('TokenKindT', bound=enum.Enum)
KeywordKindT = typing.TypeVar('KeywordKindT', bound=enum.Enum)


FrozenSymbol = str
InternedFrozenSymbol = int
InternedFrozenProduction = int
StateID = int


class FrozenSymbolTable(typing.Generic[TokenKindT, KeywordKindT]):
    def __init__(
        self,
        interned_symbols: typing.List[Symbol[TokenKindT, KeywordKindT]]
    ) -> None:
        self.interned_symbols: typing.List[FrozenSymbol] = []
        self.interned_terminal_lookup: typing.Dict[
            str, InternedFrozenSymbol
        ] = {}
        self.interned_nonterminal_lookup: typing.Dict[str, InternedFrozenSymbol] = {}
        for symbol in sorted(interned_symbols, key=lambda symbol: symbol.id):
            if isinstance(symbol, TerminalSymbol):
                frozen_symbol = symbol.kind.name
                self.interned_terminal_lookup[frozen_symbol] = symbol.id
            else:
                frozen_symbol = symbol.name
                self.interned_nonterminal_lookup[frozen_symbol] = symbol.id

            self.interned_symbols.append(frozen_symbol)

        self.interned_productions: typing.List[FrozenProduction] = []
        self.production_action_lookup: typing.Dict[InternedFrozenProduction, str] = {}

    def get_interned_terminal(self, name: str) -> InternedFrozenSymbol:
        return self.interned_terminal_lookup[name]

    def get_interned_nonterminal(self, name: str) -> InternedFrozenSymbol:
        return self.interned_terminal_lookup[name]

    def get_frozen_action(self, production: InternedFrozenProduction) -> typing.Optional[str]:
        return self.production_action_lookup.get(production)

    def get_frozen_symbol(self, interned_symbol: InternedFrozenSymbol) -> FrozenSymbol:
        return self.interned_symbols[interned_symbol]

    def get_frozen_production(self, interned_production: InternedFrozenProduction) -> FrozenProduction:
        return self.interned_productions[interned_production]

    def create_frozen_production(
        self,
        lhs: InternedFrozenSymbol,
        rhs_length: int,
        captured: typing.Tuple[int, ...],
    ) -> FrozenProduction:
        frozen_production = FrozenProduction(
            id=len(self.interned_productions),
            lhs=lhs,
            rhs_length=rhs_length,
            captured=captured,
        )
        self.interned_productions.append(frozen_production)
        return frozen_production

    def add_production_action(self, production: InternedFrozenProduction, name: str) -> None:
        self.production_action_lookup[production] = name


@attr.s(kw_only=True, slots=True, eq=True, hash=True)
class FrozenProduction:
    id: int = attr.ib()
    lhs: InternedFrozenSymbol = attr.ib()
    rhs_length: int = attr.ib()
    captured: typing.Tuple[int, ...] = attr.ib()


class ActionKind(enum.IntEnum):
    SHIFT = enum.auto()
    REDUCE = enum.auto()
    ACCEPT = enum.auto()


class FrozenParserTable(typing.Generic[TokenKindT, KeywordKindT]):
    def __init__(self, frozen_symbols: FrozenSymbolTable[TokenKindT, KeywordKindT]) -> None:
        self.frozen_symbols = frozen_symbols
        self.actions: typing.Dict[
            typing.Tuple[StateID, InternedFrozenSymbol],
            typing.Tuple[ActionKind, typing.Union[StateID, InternedFrozenProduction]]
        ] = {}
        self.gotos: typing.Dict[
            typing.Tuple[StateID, InternedFrozenSymbol],
            StateID
        ] = {}

    def get_action(self, state_id: StateID, symbol: InternedFrozenSymbol) -> typing.Optional[
        typing.Tuple[ActionKind, typing.Union[StateID, InternedFrozenProduction]]
    ]:
        return self.actions.get((state_id, symbol))

    def get_goto(self, state_id: StateID, symbol: InternedFrozenSymbol) -> typing.Optional[int]:
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

        for (state_id, interned_symbol), value in self.actions.items():
            if state_id not in grouped_tables:
                grouped_tables[state_id] = ([], [])

            actions = grouped_tables[state_id][0]
            symbol = self.frozen_symbols.get_frozen_symbol(interned_symbol)
            actions.append((symbol, *value))

        for (state_id, interned_symbol), value in self.gotos.items():
            if state_id not in grouped_tables:
                grouped_tables[state_id] = ([], [])

            gotos = grouped_tables[state_id][1]
            symbol = self.frozen_symbols.get_frozen_symbol(interned_symbol)
            gotos.append((symbol, value))

        writer = io.StringIO()

        for state_id, item in grouped_tables.items():
            writer.write(f'<state #{state_id}>\n')

            actions = item[0]
            writer.write(f'[ Actions: {len(actions)} ]\n')
            for symbol, action, number in actions:
                writer.write(f'  (for symbol {str(symbol)!r}) {action.name} ')

                match action:
                    case ActionKind.SHIFT:
                        writer.write(f'-> state #{number}')
                    case ActionKind.REDUCE:
                        production = self.frozen_symbols.get_frozen_production(number)
                        lhs = self.frozen_symbols.get_frozen_symbol(production.lhs)
                        writer.write(f'[production: {lhs}]')

                writer.write('\n')

            gotos = item[1]
            writer.write(f'[ GOTOs: {len(gotos)} ]\n')
            for symbol, destination_id in gotos:
                writer.write(f'  (for symbol {symbol!r}) -> state #{destination_id}\n')

        writer.write('\n')

        return writer.getvalue()
