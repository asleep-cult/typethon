from __future__ import annotations

import attr
import enum
import typing
import io

from . import ast
from .symbols import (
    Production,
    TerminalSymbol,
    NonterminalSymbol,
    Symbol,
    EPSILON,
    EOF,
)

KeywordT = typing.TypeVar('KeywordT', bound=enum.IntEnum)
ExpressionT = typing.TypeVar('ExpressionT', bound=ast.ExpressionNode[typing.Any])


@attr.s(kw_only=True, slots=True, hash=True, eq=True)
class ParserItem:
    production: Production = attr.ib(repr=False)
    position: int = attr.ib()
    lookahead: TerminalSymbol = attr.ib()

    def __str__(self) -> str:
        parts: typing.List[str] = []

        for symbol in self.production.rhs:
            if isinstance(symbol, NonterminalSymbol):
                parts.append(symbol.name)
            else:
                parts.append(str(symbol))

        parts.insert(self.position, '*')
        string = ' '.join(parts)
        return f'{self.production.lhs.name} -> {string}, ({self.lookahead})'

    def current_symbol(self) -> typing.Optional[Symbol]:
        if len(self.production.rhs) > self.position:
            return self.production.rhs[self.position]


@attr.s(kw_only=True, slots=True)
class ParserState:
    id: int = attr.ib()
    items: typing.Set[ParserItem] = attr.ib()

    def dump_state(self) -> str:
        writer = io.StringIO()
        writer.write(f'<parser state #{self.id}>\n')

        for i, item in enumerate(self.items):
            writer.write(f'  ({i}., pos={item.position}, lookahead={item.lookahead}): ')
            writer.write(f'{item.production.lhs.name} -> ')

            for j, symbol in enumerate(item.production.rhs):
                if j == item.position:
                    writer.write(f'* ')

                if isinstance(symbol, NonterminalSymbol):
                    writer.write(f'{symbol.name} ')
                else:
                    writer.write(f'{str(symbol)!r} ')

            writer.write('\n')

        return writer.getvalue()


class ActionKind(enum.IntEnum):
    SHIFT = enum.auto()
    REDUCE = enum.auto()
    ACCEPT = enum.auto()
    REJECT = enum.auto()


class ParserTable:
    def __init__(self) -> None:
        self.actions: typing.Dict[
            typing.Tuple[int, TerminalSymbol], typing.Tuple[ActionKind, int]
        ] = {}
        self.gotos: typing.Dict[typing.Tuple[int, NonterminalSymbol], int] = {}

    def add_accept(self, state_id: int) -> None:
        self.actions[state_id, EOF] = (ActionKind.ACCEPT, -1)

    def add_shift(self, state_id: int, symbol: TerminalSymbol, next_id: int) -> None:
        self.actions[state_id, symbol] = (ActionKind.SHIFT, next_id)

    def add_reduce(self, state_id: int, symbol: TerminalSymbol, production_id: int) -> None:
        self.actions[state_id, symbol] = (ActionKind.REDUCE, production_id)

    def add_goto(self, state_id: int, symbol: NonterminalSymbol, destination_id: int) -> None:
        self.gotos[state_id, symbol] = destination_id

    def get_action(self, state_id: int, symbol: TerminalSymbol) -> typing.Optional[
        typing.Tuple[ActionKind, int]
    ]:
        return self.actions.get((state_id, symbol))

    def get_goto(self, state_id: int, symbol: NonterminalSymbol) -> typing.Optional[int]:
        return self.gotos.get((state_id, symbol))

    def dump_table(self, productions: typing.List[Production]) -> str:
        grouped_tables: typing.Dict[
            int, 
            typing.Tuple[
                typing.List[typing.Tuple[TerminalSymbol, ActionKind, int]],  # Actions
                typing.List[typing.Tuple[NonterminalSymbol, int]],  # GOTOs
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
                writer.write(f'  (for symbol {str(symbol)!r}) {action.name} ')

                match action:
                    case ActionKind.SHIFT:
                        writer.write(f'-> state #{number}')
                    case ActionKind.REDUCE:
                        production = productions[number]
                        writer.write(f'[production: {production}]')
                
                writer.write('\n')

            gotos = item[1]
            writer.write(f'[ GOTOs: {len(gotos)} ]\n')
            for symbol, destination_id in gotos:
                writer.write(f'  (for symbol {symbol.name}) -> state #{destination_id}\n')

        writer.write('\n')

        return writer.getvalue()


class Generator(typing.Generic[KeywordT]):
    def __init__(self, rules: typing.List[ast.RuleNode[KeywordT]]) -> None:
        self.rules = rules
        self.nonterminals: typing.Dict[str, NonterminalSymbol] = {}
        self.epsilon_nonterminals: typing.Set[NonterminalSymbol] = set()
        self.first_sets: typing.Dict[NonterminalSymbol, typing.Set[TerminalSymbol]] = {}

        self.productions: typing.List[Production] = []
        self.table = ParserTable()

        self.states: typing.List[ParserState] = []
        self.transitions: typing.Dict[typing.Tuple[Symbol, int], int] = {}

    def initialize_nonterminals(self) -> None:
        for rule in self.rules:
            nonterminal = NonterminalSymbol(name=rule.name, entrypoint=rule.entrypoint)
            self.nonterminals[nonterminal.name] = nonterminal

    def initialize_productions(self) -> None:
        for rule in self.rules:
            self.initialize_productions_for_rule(rule)

    def initialize_productions_for_rule(self, rule: ast.RuleNode[KeywordT]) -> None:
        nonterminal = self.nonterminals[rule.name]

        for item in rule.items:
            production = Production(lhs=nonterminal)
            self.add_symbols_for_expression(production.rhs, item.expression)
            nonterminal.productions.append(production)

    def add_symbols_for_expression(
        self,
        symbols: typing.List[Symbol],
        expression: ast.ExpressionNode[KeywordT],
    ) -> None:
        match expression:
            case ast.StarNode():
                # star-a:b = nonterminal
                nonterminal = NonterminalSymbol(
                    name=f'star-{expression.startpos}:{expression.endpos}'
                )
                self.nonterminals[nonterminal.name] = nonterminal
                symbols.append(nonterminal)
                # | ()
                empty_production = Production(lhs=nonterminal, rhs=[EPSILON])
                nonterminal.productions.append(empty_production)
                # | expr
                production = Production(lhs=nonterminal)
                self.add_symbols_for_expression(production.rhs, expression.expression)
                nonterminal.productions.append(production)
                # | nonterminal
                production = Production(lhs=nonterminal, rhs=[nonterminal])
                nonterminal.productions.append(production)

            case ast.PlusNode():
                # plus-a:b = nonterminal
                nonterminal = NonterminalSymbol(
                    name=f'plus-{expression.startpos}-{expression.endpos}'
                )
                self.nonterminals[nonterminal.name] = nonterminal
                symbols.append(nonterminal)
                # | expr
                production = Production(lhs=nonterminal)
                self.add_symbols_for_expression(production.rhs, expression.expression)
                nonterminal.productions.append(production)
                # | nonterminal
                production = Production(lhs=nonterminal, rhs=[nonterminal])
                nonterminal.productions.append(production)

            case ast.OptionalNode():
                # optional-a:b = nonterminal
                nonterminal = NonterminalSymbol(
                    name=f'optional-{expression.startpos}-{expression.endpos}'
                )
                self.nonterminals[nonterminal.name] = nonterminal
                symbols.append(nonterminal)
                # | ()
                empty_production = Production(lhs=nonterminal, rhs=[EPSILON])
                nonterminal.productions.append(empty_production)
                # | expr
                production = Production(lhs=nonterminal)
                self.add_symbols_for_expression(production.rhs, expression.expression)
                nonterminal.productions.append(production)

            case ast.AlternativeNode():
                # plus-a:b = nonterminal
                nonterminal = NonterminalSymbol(
                    name=f'alternative-{expression.startpos}-{expression.endpos}'
                )
                self.nonterminals[nonterminal.name] = nonterminal
                symbols.append(nonterminal)
                # | lhs
                production = Production(lhs=nonterminal)
                self.add_symbols_for_expression(production.rhs, expression.lhs)
                nonterminal.productions.append(production)
                # | rhs
                production = Production(lhs=nonterminal)
                self.add_symbols_for_expression(production.rhs, expression.rhs)
                nonterminal.productions.append(production)

            case ast.GroupNode():
                for expression in expression.expressions:
                    self.add_symbols_for_expression(symbols, expression)

            case ast.KeywordNode():
                symbols.append(TerminalSymbol(kind=expression.keyword))

            case ast.TokenNode():
                symbols.append(TerminalSymbol(kind=expression.kind))

            case ast.NameNode():
                if expression.value not in self.nonterminals:
                    raise ValueError(f'{expression.value!r} is not a valid nonterminal symbol')

                symbols.append(self.nonterminals[expression.value])

    def compute_epsilon_nonterminals(self) -> None:
        # First, add every nonterminal with at least one production containing epsilon
        for nonterminal in self.nonterminals.values():
            if any(EPSILON in production.rhs for production in nonterminal.productions):
                self.epsilon_nonterminals.add(nonterminal)

        changed = True
        while changed:
            changed = False

            for nonterminal in self.nonterminals.values():
                # Next, add every nonterminal with at least one production such that all symbols
                # in the production are already within the epsilon nonterminals set
                if any(
                    self.epsilon_nonterminals.issuperset(production.rhs)
                    for production in nonterminal.productions
                ):
                    changed = nonterminal not in self.epsilon_nonterminals
                    self.epsilon_nonterminals.add(nonterminal)

    def compute_first_sets(self) -> None:
        for nonterminal in self.nonterminals.values():
            first_set: typing.Set[TerminalSymbol] = set()
            self.first_sets[nonterminal] = first_set

            for production in nonterminal.productions:
                for symbol in production.rhs:
                    if isinstance(symbol, TerminalSymbol):
                        first_set.add(symbol)

                    if symbol not in self.epsilon_nonterminals:
                        break

        changed = True
        while changed:
            changed = False
            for nonterminal in self.nonterminals.values():
                first_set = self.first_sets[nonterminal]

                for production in nonterminal.productions:
                    for symbol in production.rhs:
                        if isinstance(symbol, NonterminalSymbol):
                            length = len(first_set)
                            first_set.update(self.first_sets[symbol])
                            changed |= length != len(first_set)

                        if symbol not in self.epsilon_nonterminals:
                            break

    def get_first_set(self, symbols: typing.List[Symbol]) -> typing.Set[TerminalSymbol]:
        result: typing.Set[TerminalSymbol] = set()

        for symbol in symbols:
            if isinstance(symbol, TerminalSymbol):
                result.add(symbol)
            else:
                result.update(self.first_sets[symbol])

            if symbol not in self.epsilon_nonterminals:
                break

        return result

    def compute_follow_set(self, follow: typing.Set[TerminalSymbol], symbol: Symbol) -> None:
        if (
            isinstance(symbol, NonterminalSymbol)
            and symbol.entrypoint
        ):
            follow.add(EOF)

        for nonterminal in self.nonterminals.values():
            for production in nonterminal.productions:
                if symbol not in production.rhs:
                    continue

                index = production.rhs.index(symbol)
                if len(production.rhs) > index + 1:
                    following_symbol = production.rhs[index + 1]
                    first_rhsi = self.get_first_set([following_symbol])

                    if EPSILON in first_rhsi:
                        first_rhsi.remove(EPSILON)
                        self.compute_follow_set(follow, nonterminal)

                    follow.update(first_rhsi)
                else:
                    self.compute_follow_set(follow, nonterminal)

    def compute_closure(self, items: typing.Set[ParserItem]) -> typing.Set[ParserItem]:
        # https://web.cecs.pdx.edu/~harry/compilers/slides/SyntaxPart3.pdf
        result = items.copy()

        changed = True
        while changed:
            changed = False
            for item in result.copy():
                current_symbol = item.current_symbol()
                if not isinstance(current_symbol, NonterminalSymbol):
                    continue

                for production in current_symbol.productions:
                    trailing_symbols = item.production.rhs[item.position + 1:]
                    trailing_symbols.append(item.lookahead)

                    first_lookahead = self.get_first_set(trailing_symbols)
                    for lookahead in first_lookahead:
                        inner_item = ParserItem(production=production, position=0, lookahead=lookahead)
                        length = len(result)
                        result.add(inner_item)
                        changed |= length != len(result)

        return result

    def compute_goto(self, closure: typing.Set[ParserItem], symbol: Symbol) -> typing.Set[ParserItem]:
        result: typing.Set[ParserItem] = set()

        for item in closure:
            current_symbol = item.current_symbol()
            if current_symbol is symbol:
                updated_item = ParserItem(
                    production=item.production,
                    position=item.position + 1,
                    lookahead=item.lookahead,
                )
                result.add(updated_item)

        return self.compute_closure(result)

    def create_state(self, items: typing.Set[ParserItem]) -> ParserState:
        state = ParserState(id=len(self.states), items=items)
        self.states.append(state)
        return state

    def get_equivalent_state(self, items: typing.Set[ParserItem]) -> typing.Optional[ParserState]:
        for state in self.states:
            if state.items == items:
                return state

    def dump_states(self) -> typing.List[str]:
        return [state.dump_state() for state in self.states]

    def compute_canonical_collection(self, entrypoint: typing.Set[ParserItem]) -> None:
        self.create_state(self.compute_closure(entrypoint))

        changed = True
        while changed:
            changed = False

            for state in self.states:
                for item in state.items:
                    current_symbol = item.current_symbol()
                    if current_symbol is None:
                        continue

                    tempoaray_closure = self.compute_goto(state.items, current_symbol)
                    equivalent_state = self.get_equivalent_state(tempoaray_closure)
                    if equivalent_state is None:
                        next_state = self.create_state(tempoaray_closure)
                        changed = True
                    else:
                        next_state = equivalent_state

                    if (current_symbol, state.id) in self.transitions:
                        assert self.transitions[current_symbol, state.id] == next_state.id

                    self.transitions[current_symbol, state.id] = next_state.id

    def compute_tables(self, entrypoint: ParserItem) -> None:
        self.compute_canonical_collection({entrypoint})

        for nonterminal in self.nonterminals.values():
            self.productions.extend(nonterminal.productions)

        for state in self.states:
            for item in state.items:
                current_symbol = item.current_symbol()
                if current_symbol is None:
                    if item.production.lhs.entrypoint:
                        self.table.add_accept(state.id)
                    else:
                        production_id = self.productions.index(item.production)
                        self.table.add_reduce(state.id, item.lookahead, production_id)

                if not isinstance(current_symbol, TerminalSymbol):
                    continue

                transition = self.transitions.get((current_symbol, state.id))
                if transition is not None:
                    self.table.add_shift(state.id, current_symbol, transition)
                else:
                    print(f'No transition exists for ({current_symbol}, {state.id})')

            for nonterminal in self.nonterminals.values():
                transition = self.transitions.get((nonterminal, state.id))
                if transition is not None:
                    self.table.add_goto(state.id, nonterminal, transition)

    def generate_symbols(self) -> None:
        self.initialize_nonterminals()
        self.initialize_productions()
