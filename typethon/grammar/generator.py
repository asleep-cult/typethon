from __future__ import annotations

import attr
import enum
import typing
import io
import logging

from . import ast
from .frozen import FrozenSymbol, FrozenSymbolTable, FrozenSymbolKind
from .exceptions import ParserGeneratorError
from .symbols import (
    Production,
    TerminalSymbol,
    NonterminalSymbol,
    Symbol,
    EOF,
)
from .parser import GrammarParser
from ..syntax.tokens import StdTokenKind, TokenMap, KeywordMap

logger = logging.getLogger(__name__)

TokenKindT = typing.TypeVar('TokenKindT', bound=enum.Enum)
KeywordKindT = typing.TypeVar('KeywordKindT', bound=enum.Enum)
TerminalKindT = typing.TypeVar('TerminalKindT', bound=enum.Enum)
ExpressionT = typing.TypeVar('ExpressionT', bound=ast.ExpressionNode[typing.Any, typing.Any])


@attr.s(kw_only=True, slots=True, hash=True, eq=True)
class ParserItem(typing.Generic[TokenKindT, KeywordKindT]):
    production: Production[TokenKindT, KeywordKindT] = attr.ib()
    position: int = attr.ib()
    lookahead: TerminalSymbol[TokenKindT, KeywordKindT] = attr.ib()
    transition: typing.Optional[int] = attr.ib(eq=False, default=None)

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

    def current_symbol(self) -> typing.Optional[Symbol[TokenKindT, KeywordKindT]]:
        if len(self.production.rhs) > self.position:
            return self.production.rhs[self.position]


@attr.s(kw_only=True, slots=True)
class ParserState(typing.Generic[TokenKindT, KeywordKindT]):
    id: int = attr.ib()
    items: typing.Set[ParserItem[TokenKindT, KeywordKindT]] = attr.ib()

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


class ParserTable(typing.Generic[TokenKindT, KeywordKindT]):
    def __init__(self, frozen_symbols: FrozenSymbolTable[TokenKindT, KeywordKindT]) -> None:
        self.frozen_symbols = frozen_symbols
        self.actions: typing.Dict[
            typing.Tuple[int, FrozenSymbol], typing.Tuple[ActionKind, int]
        ] = {}
        self.gotos: typing.Dict[typing.Tuple[int, FrozenSymbol], int] = {}

    def add_accept(self, state_id: int) -> None:
        assert EOF.kind is StdTokenKind.EOF
        frozen_eof = self.frozen_symbols.get_frozen_terminal(EOF.kind)

        existing_entry = self.actions.get((state_id, frozen_eof))
        if (
            existing_entry is not None
            and existing_entry != (ActionKind.ACCEPT, -1)
        ):
            raise ParserGeneratorError(
                'Encountered an impossible conflict while trying to add '
                'an ACCEPT action for state #{0}: {1}'.format(state_id, existing_entry)
            )

        self.actions[state_id, frozen_eof] = (ActionKind.ACCEPT, -1)

    def add_shift(
        self,
        state_id: int,
        symbol: TerminalSymbol[TokenKindT, KeywordKindT],
        next_id: int,
    ) -> None:
        frozen_symbol = self.frozen_symbols.get_frozen_terminal(symbol.kind)
        assert frozen_symbol.kind is FrozenSymbolKind.TERMINAL

        existing_entry = self.actions.get((state_id, frozen_symbol))
        if (
            existing_entry is not None
            and existing_entry != (ActionKind.SHIFT, next_id)
        ):
            if existing_entry[0] is ActionKind.REDUCE:
                logger.info(
                    'Encountered a SHIFT/REDUCE conflict while adding '
                    'a SHIFT to state #%s in state #%s, symbol %s. Replacing '
                    'the REDUCE action. NOTE: The REDUCE action was for '
                    'a production with the id %s.',
                    next_id,
                    state_id,
                    symbol,
                    existing_entry[1],
                )
            else:
                raise ParserGeneratorError(
                    'Encountered an impossible conflict while trying to add '
                    'a SHIFT to state {0} in state #{1}, symbol {2}: {3}'
                    .format(
                        next_id,
                        state_id,
                        symbol,
                        existing_entry,
                    )
                )

        self.actions[state_id, frozen_symbol] = (ActionKind.SHIFT, next_id)

    def add_reduce(
        self,
        state_id: int,
        symbol: TerminalSymbol[TokenKindT, KeywordKindT],
        production_id: int,
    ) -> None:
        frozen_symbol = self.frozen_symbols.get_frozen_terminal(symbol.kind)
        assert frozen_symbol.kind is FrozenSymbolKind.TERMINAL

        existing_entry = self.actions.get((state_id, frozen_symbol))
        if (
            existing_entry is not None
            and existing_entry != (ActionKind.REDUCE, production_id)
        ):
            if existing_entry[0] is ActionKind.SHIFT:
                logger.info(
                    'Encountered a SHIFT/REDUCE conflict while adding '
                    'a REDUCE for a production with the id %s in state '
                    '#%s, symbol %s. Defaulting to SHIFT instead. NOTE: '
                    'The SHIFT action goes to state #%s',
                    production_id,
                    state_id,
                    symbol,
                    existing_entry[1],
                )
                return
            else:
                raise ParserGeneratorError(
                    'Encountered an impossible conflict while trying to add '
                    'a REDUCE action for a production with the id {0} in '
                    'state #{1}, symbol {2}: {3}'.format(
                        production_id,
                        state_id,
                        symbol,
                        existing_entry,
                    )
                )

        self.actions[state_id, frozen_symbol] = (ActionKind.REDUCE, production_id)

    def add_goto(
        self,
        state_id: int,
        symbol: NonterminalSymbol[TokenKindT, KeywordKindT],
        destination_id: int,
    ) -> None:
        frozen_symbol = self.frozen_symbols.get_frozen_nonterminal(symbol.name)
        assert frozen_symbol.kind is FrozenSymbolKind.NONTERMINAL

        existing_entry = self.gotos.get((state_id, frozen_symbol))
        if (
            existing_entry is not None
            and existing_entry != destination_id
        ):
            raise ParserGeneratorError(
                'Encountered impossible conflict while trying to add '
                'an entry to add an entry to the goto table state #{0}, '
                'symbol {1}, destination: state #{2}: {3}'.format(
                    state_id,
                    symbol,
                    destination_id,
                    existing_entry,
                )
            )

        self.gotos[state_id, frozen_symbol] = destination_id

    def get_action(self, state_id: int, symbol: FrozenSymbol) -> typing.Optional[
        typing.Tuple[ActionKind, int]
    ]:
        return self.actions.get((state_id, symbol))

    def get_goto(self, state_id: int, symbol: FrozenSymbol) -> typing.Optional[int]:
        return self.gotos.get((state_id, symbol))

    def dump_table(
        self,
        productions: typing.List[Production[TokenKindT, KeywordKindT]]
    ) -> str:
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
                        production = productions[number]
                        writer.write(f'[production: {production}]')
                
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


class ParserTableGenerator(typing.Generic[TokenKindT, KeywordKindT]):
    def __init__(
        self,
        tokens: TokenMap[TokenKindT],
        keywords: KeywordMap[KeywordKindT],
        rules: typing.List[ast.RuleNode[TokenKindT, KeywordKindT]],
    ) -> None:
        self.rules = rules
        self.nonterminals: typing.Dict[
            str, NonterminalSymbol[TokenKindT, KeywordKindT]
        ] = {}
        self.epsilon_nonterminals: typing.Set[
            NonterminalSymbol[TokenKindT, KeywordKindT]
        ] = set()
        self.first_sets: typing.Dict[
            NonterminalSymbol[TokenKindT, KeywordKindT],
            typing.Set[TerminalSymbol[TokenKindT, KeywordKindT]]
        ] = {}

        self.frozen_symbols = FrozenSymbolTable(tokens, keywords)
        self.productions: typing.List[Production[TokenKindT, KeywordKindT]] = []
        self.states: typing.List[ParserState[TokenKindT, KeywordKindT]] = []

    def initialize_nonterminals(self) -> None:
        for rule in self.rules:
            self.nonterminals[rule.name] = NonterminalSymbol(name=rule.name, entrypoint=rule.entrypoint)

    def initialize_productions(self) -> None:
        for rule in self.rules:
            self.initialize_productions_for_rule(rule)

    def generate_symbols(self) -> None:
        self.initialize_nonterminals()
        self.initialize_productions()

    def generate_frozen_symbols(self) -> None:
        for nonterminal in self.nonterminals.values():
            frozen_nonterminal = self.frozen_symbols.create_frozen_nonterminal(nonterminal.name)

            for production in nonterminal.productions:
                self.productions.append(production)
                # productions.index(production) must be the id of the frozen production

                frozen_production = self.frozen_symbols.create_frozen_production(
                    frozen_nonterminal, len(production.rhs), tuple(production.captured)
                )
                if production.action is not None:
                    self.frozen_symbols.add_production_action(
                        frozen_production, production.action,
                    )

    def should_capture_uninlined_expression(
        self,
        nonterminal: NonterminalSymbol[TokenKindT, KeywordKindT],
    ) -> bool:
        return any(production.captured for production in nonterminal.productions)

    def initialize_productions_for_rule(
        self,
        rule: ast.RuleNode[TokenKindT, KeywordKindT]
    ) -> None:
        nonterminal = self.nonterminals[rule.name]

        for item in rule.items:
            production = Production(lhs=nonterminal, action=item.action)
            self.add_symbols_for_expression(production, item.expression)
            nonterminal.productions.append(production)

    def add_new_star_expression(
        self,
        name: str,
        production: Production[TokenKindT, KeywordKindT],
        expression: ast.ExpressionNode[TokenKindT, KeywordKindT],
        *,
        capture: bool = False,
    ) -> None:
        # star-a:b = nonterminal
        nonterminal = NonterminalSymbol[TokenKindT, KeywordKindT](name=name)
        self.nonterminals[nonterminal.name] = nonterminal
        # | epsilon
        temporary_production = Production(lhs=nonterminal)
        temporary_production.action = '@flatten_star'
        nonterminal.productions.append(temporary_production)
        # | nonterminal expr
        temporary_production = Production(lhs=nonterminal)
        temporary_production.action = '@flatten_star'
        self.add_symbols_for_expression(
            temporary_production,
            expression,
            capture=capture,
        )
        nonterminal.productions.append(temporary_production)

        if not capture:
            capture = self.should_capture_uninlined_expression(nonterminal)

        # We insert the nonterminal after calling add_symbols_for_expression
        # because whether expr captures any symbols determines if the nonterminal
        # needs to be captured as well
        temporary_production.insert_symbol(0, nonterminal, capture)
        production.add_symbol(nonterminal, capture)

    def add_symbols_for_expression(
        self,
        production: Production[TokenKindT, KeywordKindT],
        expression: ast.ExpressionNode[TokenKindT, KeywordKindT],
        *,
        capture: bool = False,
    ) -> None:
        match expression:
            case ast.StarNode():
                self.add_new_star_expression(
                    f'star-{expression.start}:{expression.end}',
                    production,
                    expression.expression,
                    capture=capture
                )

            case ast.PlusNode():
                # plus-a:b = nonterminal
                nonterminal = NonterminalSymbol[TokenKindT, KeywordKindT](
                    name=f'plus-{expression.start}-{expression.end}'
                )
                self.nonterminals[nonterminal.name] = nonterminal
                # | expr plus-a:b@star
                temporary_production = Production(lhs=nonterminal)
                temporary_production.action = '@flatten_plus'
                self.add_symbols_for_expression(
                    temporary_production,
                    expression.expression,
                    capture=capture,
                )
                nonterminal.productions.append(temporary_production)

                self.add_new_star_expression(
                    f'plus-{expression.start}-{expression.end}@star',
                    temporary_production,
                    expression.expression,
                    capture=capture,
                )

                if not capture:
                    capture = self.should_capture_uninlined_expression(nonterminal)

                production.add_symbol(nonterminal, capture)

            case ast.OptionalNode():
                # optional-a:b = nonterminal
                nonterminal = NonterminalSymbol[TokenKindT, KeywordKindT](
                    name=f'optional-{expression.start}-{expression.end}'
                )
                self.nonterminals[nonterminal.name] = nonterminal
                # | epsilon
                temporary_production = Production(lhs=nonterminal)
                temporary_production.action = '@option'
                nonterminal.productions.append(temporary_production)
                # | expr
                temporary_production = Production(lhs=nonterminal)
                temporary_production.action = '@option'
                self.add_symbols_for_expression(
                    temporary_production,
                    expression.expression,
                    capture=capture,
                )
                nonterminal.productions.append(temporary_production)

                if not capture:
                    capture = self.should_capture_uninlined_expression(nonterminal)

                production.add_symbol(nonterminal, capture)

            case ast.CaptureNode():
                self.add_symbols_for_expression(production, expression.expression, capture=True)

            case ast.AlternativeNode():
                # plus-a:b = nonterminal
                nonterminal = NonterminalSymbol[TokenKindT, KeywordKindT](
                    name=f'alternative-{expression.start}-{expression.end}'
                )
                self.nonterminals[nonterminal.name] = nonterminal
                # | lhs
                temporary_production = Production(lhs=nonterminal)
                self.add_symbols_for_expression(
                    temporary_production,
                    expression.lhs,
                    capture=capture,
                )
                nonterminal.productions.append(temporary_production)
                # | rhs
                temporary_production = Production(lhs=nonterminal)
                self.add_symbols_for_expression(
                    temporary_production,
                    expression.rhs,
                    capture=capture,
                )
                nonterminal.productions.append(temporary_production)

                if not capture:
                    capture = self.should_capture_uninlined_expression(nonterminal)

                production.add_symbol(nonterminal, capture)

            case ast.GroupNode():
                for expression in expression.expressions:
                    self.add_symbols_for_expression(production, expression, capture=capture)

            case ast.KeywordNode():
                production.add_symbol(TerminalSymbol(kind=expression.keyword), capture)

            case ast.TokenNode():
                production.add_symbol(TerminalSymbol(kind=expression.kind), capture)

            case ast.NameNode():
                if expression.value not in self.nonterminals:
                    raise ValueError(f'{expression.value!r} is not a valid nonterminal symbol')

                production.add_symbol(self.nonterminals[expression.value], capture)

    def compute_epsilon_nonterminals(self) -> None:
        # First, add every nonterminal with at least one production containing epsilon
        for nonterminal in self.nonterminals.values():
            if any(not production.rhs for production in nonterminal.productions):
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
            first_set: typing.Set[TerminalSymbol[TokenKindT, KeywordKindT]] = set()
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

    def get_first_set(
        self,
        symbols: typing.List[Symbol[TokenKindT, KeywordKindT]]
    ) -> typing.Set[TerminalSymbol[TokenKindT, KeywordKindT]]:
        result: typing.Set[TerminalSymbol[TokenKindT, KeywordKindT]] = set()

        for symbol in symbols:
            if isinstance(symbol, TerminalSymbol):
                result.add(symbol)
            else:
                result.update(self.first_sets[symbol])

            if symbol not in self.epsilon_nonterminals:
                break

        return result

    def compute_closure(
        self,
        items: typing.Set[ParserItem[TokenKindT, KeywordKindT]]
    ) -> typing.Set[ParserItem[TokenKindT, KeywordKindT]]:
        # https://web.cecs.pdx.edu/~harry/compilers/slides/SyntaxPart3.pdf
        # Given a set of items, this function creates a new set of items such that
        # all items whose current state is at a nonterminal symbol has a new item
        # for each production in that nonterminal
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
                        inner_item = ParserItem(
                            production=production,
                            position=0,
                            lookahead=lookahead,
                        )
                        length = len(result)
                        result.add(inner_item)
                        changed |= length != len(result)

        return result

    def compute_goto(
        self,
        closure: typing.Set[ParserItem[TokenKindT, KeywordKindT]],
        symbol: Symbol[TokenKindT, KeywordKindT],
    ) -> typing.Set[ParserItem[TokenKindT, KeywordKindT]]:
        result: typing.Set[ParserItem[TokenKindT, KeywordKindT]] = set()

        for item in closure:
            current_symbol = item.current_symbol()
            if current_symbol == symbol:
                updated_item = ParserItem(
                    production=item.production,
                    position=item.position + 1,
                    lookahead=item.lookahead,
                )
                result.add(updated_item)

        return self.compute_closure(result)

    def create_state(
        self,
        items: typing.Set[ParserItem[TokenKindT, KeywordKindT]]
    ) -> ParserState[TokenKindT, KeywordKindT]:
        state = ParserState(id=len(self.states), items=items)
        self.states.append(state)
        return state

    def get_equivalent_state(
        self,
        items: typing.Set[ParserItem[TokenKindT, KeywordKindT]],
    ) -> typing.Optional[ParserState[TokenKindT, KeywordKindT]]:
        for state in self.states:
            if state.items == items:
                return state

    def dump_states(self) -> typing.List[str]:
        return [state.dump_state() for state in self.states]

    def compute_canonical_collection(self, entrypoint: ParserItem[TokenKindT, KeywordKindT]) -> None:
        self.create_state(self.compute_closure({entrypoint}))

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

                    if (
                        item.transition is not None
                        and item.transition != next_state.id
                    ):
                        raise ParserGeneratorError(
                            'Encountered an impossible conflict while trying to '
                            'set transition state #{0}, symbol {1} to {2}. '
                            'The transition is already set to {3}.'.format(
                                state.id,
                                current_symbol,
                                next_state.id,
                                item.transition,
                            )
                        )

                    item.transition = next_state.id

    def compute_tables(
        self,
        entrypoint: ParserItem[TokenKindT, KeywordKindT],
    ) -> ParserTable[TokenKindT, KeywordKindT]:
        table = ParserTable(frozen_symbols=self.frozen_symbols)
        self.compute_canonical_collection(entrypoint)

        for state in self.states:
            for item in state.items:
                current_symbol = item.current_symbol()
                if current_symbol is None:
                    if item.production.lhs.entrypoint:
                        table.add_accept(state.id)
                    else:
                        production_id = self.productions.index(item.production)
                        table.add_reduce(state.id, item.lookahead, production_id)

                if not isinstance(current_symbol, TerminalSymbol):
                    continue

                if item.transition is not None:
                    table.add_shift(state.id, current_symbol, item.transition)

            for nonterminal in self.nonterminals.values():
                for item in state.items:
                    if item.current_symbol() == nonterminal and item.transition is not None:
                        table.add_goto(state.id, nonterminal, item.transition)

        for state in self.states:
            if not any(state_id == state.id for state_id, _ in table.actions):
                raise ParserGeneratorError(f'State #{state.id} has no actions')

        return table

    def generate(self) -> typing.Dict[str, ParserTable[TokenKindT, KeywordKindT]]:
        self.generate_symbols()
        self.generate_frozen_symbols()
        self.compute_epsilon_nonterminals()
        self.compute_first_sets()

        tables: typing.Dict[str, ParserTable[TokenKindT, KeywordKindT]] = {}
        for nonterminal in self.nonterminals.values():
            if nonterminal.entrypoint:
                if len(nonterminal.productions) != 1:
                    raise ParserGeneratorError(
                        f'Grammar entrypoint {nonterminal.name!r} has more than one production'
                    )
            
                production = nonterminal.productions[0]
                item = ParserItem(production=production, position=0, lookahead=EOF)
                table = self.compute_tables(item)
                tables[nonterminal.name] = table

        if not tables:
            raise ParserGeneratorError('The grammar has no entrypoint')

        return tables

    @classmethod
    def generate_from_grammar(
        cls,
        grammar: str,
        tokens: TokenMap[TokenKindT],
        keywords: KeywordMap[KeywordKindT],
    ) -> typing.Dict[str, ParserTable[TokenKindT, KeywordKindT]]:
        rules = GrammarParser[TokenKindT, KeywordKindT].parse_from_source(grammar, tokens, keywords)
        instance = cls(tokens, keywords, rules)
        return instance.generate()
