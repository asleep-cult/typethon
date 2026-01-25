from __future__ import annotations

import attr
import enum
import io

from .symbols import Symbol, TerminalSymbol


type FrozenSymbol = str
type InternedFrozenSymbol = int
type InternedFrozenProduction = int
type StateID = int


class FrozenSymbolTable[TokenKindT: enum.Enum, KeywordKindT: enum.Enum]:
    def __init__(
        self,
        interned_symbols: list[Symbol[TokenKindT, KeywordKindT]],
    ) -> None:
        self.interned_symbols: list[FrozenSymbol] = []
        self.interned_terminal_lookup: dict[
            str, InternedFrozenSymbol
        ] = {}
        self.interned_nonterminal_lookup: dict[str, InternedFrozenSymbol] = {}
        for symbol in interned_symbols:
            if isinstance(symbol, TerminalSymbol):
                frozen_symbol = symbol.kind.name
                self.interned_terminal_lookup[frozen_symbol] = symbol.id
            else:
                frozen_symbol = symbol.name
                self.interned_nonterminal_lookup[frozen_symbol] = symbol.id

            self.interned_symbols.append(frozen_symbol)

        self.interned_productions: list[FrozenProduction] = []
        self.production_action_lookup: dict[InternedFrozenProduction, str] = {}

    def get_interned_terminal(self, name: str) -> InternedFrozenSymbol:
        return self.interned_terminal_lookup[name]

    def get_interned_nonterminal(self, name: str) -> InternedFrozenSymbol:
        return self.interned_terminal_lookup[name]

    def get_frozen_action(self, production: InternedFrozenProduction) -> str | None:
        return self.production_action_lookup.get(production)

    def get_frozen_symbol(self, interned_symbol: InternedFrozenSymbol) -> FrozenSymbol:
        return self.interned_symbols[interned_symbol]

    def get_frozen_production(self, interned_production: InternedFrozenProduction) -> FrozenProduction:
        return self.interned_productions[interned_production]

    def create_frozen_production(
        self,
        lhs: InternedFrozenSymbol,
        rhs_length: int,
        captured: tuple[int, ...],
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
    captured: tuple[int, ...] = attr.ib()


class ActionKind(enum.IntEnum):
    REJECT = -1
    SHIFT = enum.auto()
    REDUCE = enum.auto()
    ACCEPT = enum.auto()


UNSET_ACTION = (ActionKind.REJECT, -1)
UNSET_GOTO = -1


class FrozenParserTable[TokenKindT: enum.Enum, KeywordKindT: enum.Enum]:
    def __init__(
        self,
        number_of_states: int,
        frozen_symbols: FrozenSymbolTable[TokenKindT, KeywordKindT]
    ) -> None:
        self.frozen_symbols = frozen_symbols
        self.actions: list[
            list[tuple[ActionKind, StateID | InternedFrozenProduction]]
        ] = []
        self.gotos: list[list[StateID]] = []

        for _ in range(number_of_states):
            self.actions.append([UNSET_ACTION] * len(frozen_symbols.interned_terminal_lookup))

        for _ in range(number_of_states):
            self.gotos.append([UNSET_GOTO] * len(frozen_symbols.interned_nonterminal_lookup))

    def get_action(self, state_id: StateID, interned_symbol: InternedFrozenSymbol) -> tuple[
        ActionKind, StateID | InternedFrozenProduction
    ]:
        return self.actions[state_id][interned_symbol]

    def get_goto(self, state_id: StateID, interned_symbol: InternedFrozenSymbol) -> StateID:
        index = interned_symbol - len(self.frozen_symbols.interned_terminal_lookup)
        return self.gotos[state_id][index]

    def dump_table(self) -> str:
        writer = io.StringIO()

        for state_id in range(len(self.actions)):
            writer.write(f'<state #{state_id}>\n')

            actions: list[
                tuple[
                    FrozenSymbol,
                    ActionKind,
                    StateID | InternedFrozenProduction
                ]
            ] = []

            for i, (action, number) in enumerate(self.actions[state_id]):
                if action is ActionKind.REJECT:
                    continue

                symbol = self.frozen_symbols.get_frozen_symbol(i)
                actions.append((symbol, action, number))

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

            gotos: list[tuple[FrozenSymbol, StateID]] = []

            for i, goto_state in enumerate(self.gotos[state_id]):
                index = i + len(self.frozen_symbols.interned_terminal_lookup)
                symbol = self.frozen_symbols.get_frozen_symbol(index)
                gotos.append((symbol, goto_state))

            writer.write(f'[ GOTOs: {len(gotos)} ]\n')
            for symbol, destination_id in gotos:
                writer.write(f'  (for symbol {symbol!r}) -> state #{destination_id}\n')

        writer.write('\n')

        return writer.getvalue()
