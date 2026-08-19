from __future__ import annotations

import array
import enum
import io
import struct
import sys
import typing
from collections.abc import Sequence

import attr

from .symbols import Symbol, TerminalSymbol

type FrozenSymbol = str
type FrozenAction = str
type InternedFrozenSymbol = int
type InternedFrozenProduction = int
type InternedFrozenAction = int
type StateID = int


class FrozenSymbolTable[TokenKindT: enum.Enum, KeywordKindT: enum.Enum]:
    def __init__(
        self,
        interned_symbols: list[Symbol[TokenKindT, KeywordKindT]],
    ) -> None:
        self.interned_symbols: list[FrozenSymbol] = []
        self.interned_terminal_lookup: dict[str, InternedFrozenSymbol] = {}
        self.interned_nonterminal_lookup: dict[str, InternedFrozenSymbol] = {}

        for symbol in sorted(interned_symbols, key=lambda sym: sym.id):
            if isinstance(symbol, TerminalSymbol):
                frozen_symbol = symbol.kind.name
                self.interned_terminal_lookup[frozen_symbol] = symbol.id
            else:
                frozen_symbol = symbol.name
                self.interned_nonterminal_lookup[frozen_symbol] = symbol.id

            self.interned_symbols.append(frozen_symbol)

        self.interned_productions: list[FrozenProduction] = []
        self.interned_actions: list[FrozenAction] = []

    @classmethod
    def from_bytes(
        cls,
        tokens: list[TokenKindT | KeywordKindT],
        reader: io.BufferedReader,
    ) -> FrozenSymbolTable:
        self = object.__new__(cls)

        self.interned_symbols = []
        self.interned_terminal_lookup = {}
        self.interned_nonterminal_lookup = {}
        self.interned_productions = []
        self.interned_actions = []

        for i, token in enumerate(tokens):
            self.interned_symbols.append(token.name)
            self.interned_terminal_lookup[token.name] = i

        sizes_fmt = "<4H"
        chunk = reader.read(struct.calcsize(sizes_fmt))
        expected_terminals, nonterminals, productions, actions = struct.unpack(sizes_fmt, chunk)
        assert len(self.interned_symbols) == expected_terminals, (
            "Regenerate parser table with new tokens"
        )

        nonterminal_names = reader.read(nonterminals).split(b"\0")
        for name in nonterminal_names:
            decoded_name = name.decode()
            self.interned_nonterminal_lookup[decoded_name] = len(self.interned_symbols)
            self.interned_symbols.append(decoded_name)

        for i in range(productions):
            self.interned_productions.append(FrozenProduction.from_bytes(i, reader))

        action_names = reader.read(actions).split(b"\0")
        for name in action_names:
            decoded_name = name.decode()
            self.interned_actions.append(decoded_name)

        return self

    def to_bytes(self, writer: io.BufferedWriter) -> None:
        concatenated_nonterminals = b"\0".join(
            name.encode() for name in self.interned_nonterminal_lookup
        )
        concatenated_actions = b"\0".join(action.encode() for action in self.interned_actions)

        chunk = struct.pack(
            "<4H",
            len(self.interned_terminal_lookup),
            len(concatenated_nonterminals),
            len(self.interned_productions),
            len(concatenated_actions),
        )
        writer.write(chunk)
        writer.write(concatenated_nonterminals)

        for production in self.interned_productions:
            production.to_bytes(writer)

        writer.write(concatenated_actions)

    def get_interned_terminal(self, name: str) -> InternedFrozenSymbol:
        return self.interned_terminal_lookup[name]

    def get_interned_nonterminal(self, name: str) -> InternedFrozenSymbol:
        return self.interned_terminal_lookup[name]

    def get_frozen_action(self, production: InternedFrozenProduction) -> FrozenAction | None:
        interned = self.interned_productions[production]
        if interned.interned_action != UNSET_PRODUCTION_ACTION:
            return self.interned_actions[interned.interned_action - 1]

    def get_frozen_symbol(self, interned_symbol: InternedFrozenSymbol) -> FrozenSymbol:
        return self.interned_symbols[interned_symbol]

    def get_frozen_production(
        self, interned_production: InternedFrozenProduction
    ) -> FrozenProduction:
        return self.interned_productions[interned_production]

    def create_frozen_production(
        self,
        lhs: InternedFrozenSymbol,
        rhs_length: int,
        captured: tuple[int, ...],
        action: str | None,
    ) -> FrozenProduction:
        interned_action = UNSET_PRODUCTION_ACTION
        if action is not None:
            self.interned_actions.append(action)
            interned_action = len(self.interned_actions)  # Intentionally off by one

        frozen_production = FrozenProduction(
            id=len(self.interned_productions),
            lhs=lhs,
            rhs_length=rhs_length,
            captured=captured,
            interned_action=interned_action,
        )
        self.interned_productions.append(frozen_production)
        return frozen_production


@attr.s(kw_only=True, slots=True, eq=True, hash=True)
class FrozenProduction:
    id: int = attr.ib()
    lhs: InternedFrozenSymbol = attr.ib()
    rhs_length: int = attr.ib()
    captured: tuple[int, ...] = attr.ib()
    interned_action: InternedFrozenAction = attr.ib()

    @classmethod
    def from_bytes(cls, id: int, reader: io.BufferedReader) -> FrozenProduction:
        self = object.__new__(cls)
        self.id = id

        prod_fmt = "<4H"
        chunk = reader.read(struct.calcsize(prod_fmt))
        self.lhs, self.rhs_length, captured, self.interned_action = struct.unpack(prod_fmt, chunk)

        self.captured = tuple(i for i in range(captured.bit_length()) if captured & 1 << i)
        return self

    def to_bytes(self, writer: io.BufferedWriter) -> None:
        bitset = 0
        for i in self.captured:
            bitset |= 1 << i

        writer.write(struct.pack("<4H", self.lhs, self.rhs_length, bitset, self.interned_action))


class ActionKind(enum.IntEnum):
    REJECT = 0
    SHIFT = 1
    REDUCE = 2
    ACCEPT = 3


UNSET_PRODUCTION_ACTION = 0
UNSET_ACTION = 0
UNSET_GOTO = 0


class FrozenParserTable[TokenKindT: enum.Enum, KeywordKindT: enum.Enum]:
    def __init__(
        self,
        frozen_symbols: FrozenSymbolTable[TokenKindT, KeywordKindT],
        number_of_states: int,
        actions: memoryview[int],
        gotos: memoryview[int],
    ) -> None:
        self.number_of_states = number_of_states
        self.frozen_symbols = frozen_symbols
        self.actions = actions
        self.gotos = gotos

    @classmethod
    def from_bytes(
        cls,
        frozen_symbols: FrozenSymbolTable,
        reader: io.BufferedReader,
    ) -> FrozenParserTable:
        self = object.__new__(cls)
        self.frozen_symbols = frozen_symbols

        header_fmt = "<3I"
        chunk = reader.read(struct.calcsize(header_fmt))
        self.number_of_states, action_size, goto_size = struct.unpack(header_fmt, chunk)

        # Using 32 bit numbers to represent states resulted in a 3,856 KB binary.
        # Using 16 bit numbers resulted in a 1,931 KB binary.
        # With 16 bit numbers, only 14 bits are usable in action table because the
        # top two bits are for the action kind. So there is a theoretical limit
        # of 16,383 states, the current grammar has 5,003.
        action_table = array.array("H")
        action_table.frombytes(reader.read(action_size))

        goto_table = array.array("H")
        goto_table.frombytes(reader.read(goto_size))

        # XXX: Setting the shape makes it completely unindexable, very useless
        # shape = self.number_of_states, len(frozen_symbols.interned_terminal_lookup)
        self.actions = memoryview(action_table)

        # shape = self.number_of_states, len(self.frozen_symbols.interned_nonterminal_lookup)
        self.gotos = memoryview(goto_table)

        return self

    def to_bytes(self, writer: io.BufferedWriter) -> None:
        header_fmt = "<3I"
        writer.write(
            struct.pack(
                header_fmt,
                self.number_of_states,
                self.actions.nbytes,
                self.gotos.nbytes,
            )
        )
        writer.write(self.actions)
        writer.write(self.gotos)

    def pack_action(self, action: ActionKind, number: InternedFrozenProduction | StateID) -> int:
        action_value = action.value
        number = number & 0x3FFF  # 32 bit: 0x3FFFFFFF

        packed_action = (action_value << 14) | number  # 32: 30
        return packed_action & 0xFFFF  # 32 bit: 0xFFFFFFFF

    def unpack_action(self, packed_action: int) -> tuple[ActionKind, InternedFrozenProduction]:
        action = ActionKind((packed_action & 0xC000) >> 14)  # 32 bit: 0xC0000000
        production_id = packed_action & 0x3FFF
        return action, production_id

    def action_index(self, state_id: StateID, symbol_id: InternedFrozenSymbol) -> int:
        terminals = len(self.frozen_symbols.interned_terminal_lookup)
        return (state_id * terminals) + symbol_id

    def goto_index(self, state_id: StateID, symbol_id: InternedFrozenSymbol) -> int:
        nonterminals = len(self.frozen_symbols.interned_nonterminal_lookup)
        return (state_id * nonterminals) + symbol_id

    def all_actions(self, state_id: StateID) -> typing.Iterator[tuple[ActionKind, StateID]]:
        terminals = len(self.frozen_symbols.interned_terminal_lookup)
        actions = self.actions[state_id * terminals : (state_id + 1) * terminals]
        return (self.unpack_action(action) for action in actions)

    def all_gotos(self, state_id: StateID) -> Sequence[StateID]:
        nonterminals = len(self.frozen_symbols.interned_nonterminal_lookup)
        return self.gotos[state_id * nonterminals : (state_id + 1) * nonterminals]

    def get_action(
        self, state_id: StateID, interned_symbol: InternedFrozenSymbol
    ) -> tuple[ActionKind, StateID | InternedFrozenProduction] | None:
        result = self.actions[self.action_index(state_id, interned_symbol)]
        if result == UNSET_ACTION:
            return None

        return self.unpack_action(result)

    def get_goto(self, state_id: StateID, interned_symbol: InternedFrozenSymbol) -> StateID | None:
        symbol_index = interned_symbol - len(self.frozen_symbols.interned_terminal_lookup)
        result = self.gotos[self.goto_index(state_id, symbol_index)]
        if result == UNSET_GOTO:
            return None

        return result - 1

    def get_action_map(
        self, state_id: StateID
    ) -> list[tuple[FrozenSymbol, ActionKind, StateID | InternedFrozenProduction]]:
        actions: list[tuple[FrozenSymbol, ActionKind, StateID | InternedFrozenProduction]] = []

        for i, (action, number) in enumerate(self.all_actions(state_id)):
            if action is ActionKind.REJECT:
                continue

            symbol = self.frozen_symbols.get_frozen_symbol(i)
            actions.append((symbol, action, number))

        return actions

    def get_goto_map(self, state_id: StateID) -> list[tuple[FrozenSymbol, StateID]]:
        gotos: list[tuple[FrozenSymbol, StateID]] = []

        for i, goto_state in enumerate(self.all_gotos(state_id)):
            index = i + len(self.frozen_symbols.interned_terminal_lookup)
            symbol = self.frozen_symbols.get_frozen_symbol(index)
            gotos.append((symbol, goto_state))

        return gotos

    def dump_table(self) -> str:
        writer = io.StringIO()

        for state_id in range(self.number_of_states):
            writer.write(f"<state #{state_id}>\n")

            actions = self.get_action_map(state_id)

            writer.write(f"[ Actions: {len(actions)} ]\n")
            for symbol, action, number in actions:
                writer.write(f"  (for symbol {str(symbol)!r}) {action.name} ")

                match action:
                    case ActionKind.SHIFT:
                        writer.write(f"-> state #{number}")
                    case ActionKind.REDUCE:
                        production = self.frozen_symbols.get_frozen_production(number)
                        lhs = self.frozen_symbols.get_frozen_symbol(production.lhs)
                        writer.write(f"[production: {lhs}]")

                writer.write("\n")

            gotos = self.get_goto_map(state_id)
            writer.write(f"[ GOTOs: {len(gotos)} ]\n")
            for symbol, destination_id in gotos:
                writer.write(f"  (for symbol {symbol!r}) -> state #{destination_id}\n")

        writer.write("\n")

        return writer.getvalue()
