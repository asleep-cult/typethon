from __future__ import annotations

import attr
import enum
import typing
import logging
import functools
import io
import itertools
from collections import defaultdict

from . import ast
from .frozen import (
    ActionKind,
    FrozenSymbolTable,
    FrozenSymbolKind,
    FrozenParserTable,
)
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


ParserItem = typing.Tuple[
    Production[TokenKindT, KeywordKindT],
    int,
    typing.FrozenSet[TerminalSymbol[TokenKindT, KeywordKindT]]
]
InternedParserItem = int


class ItemSet(typing.Generic[TokenKindT, KeywordKindT]):
    def __init__(
        self,
        interned_items: typing.List[ParserItem[TokenKindT, KeywordKindT]],
        interned_items_lookup: typing.Dict[ParserItem[TokenKindT, KeywordKindT], int],
        interned_symbols: typing.List[Symbol[TokenKindT, KeywordKindT]],
    ) -> None:
        self.interned_items_lookup = interned_items_lookup
        self.interned_items = interned_items
        self.interned_symbols = interned_symbols
        self.nonterminal_items: typing.Dict[int, typing.Set[InternedParserItem]] = defaultdict(set)
        self.terminal_items: typing.Dict[int, typing.Set[InternedParserItem]] = defaultdict(set)
        self.completed_items: typing.Set[InternedParserItem] = set()
        self.all_interned_items: typing.Set[InternedParserItem] = set()

    def __eq__(self, other: object) -> bool:
        return (
            isinstance(other, ItemSet)
            and other.all_interned_items == self.all_interned_items
            and other.nonterminal_items == self.nonterminal_items
            and other.terminal_items == self.terminal_items
            and other.completed_items == self.completed_items
        )

    def get_intern_items(self) -> typing.Tuple[InternedParserItem, ...]:
        return tuple(self.all_interned_items)

    def iter_interned_items(
        self,
        items: typing.Iterable[InternedParserItem],
    ) -> typing.Iterator[ParserItem[TokenKindT, KeywordKindT]]:
        return (self.interned_items[item] for item in items)

    def iter_symbols(self) -> typing.Iterator[Symbol[TokenKindT, KeywordKindT]]:
        return itertools.chain(
            (self.interned_symbols[symbol] for symbol in self.nonterminal_items.keys()),
            (self.interned_symbols[symbol] for symbol in  self.terminal_items.keys()),
        )

    def iter_nonterminal_items_with_symbol(self) -> typing.Iterator[
        typing.Tuple[
            NonterminalSymbol[TokenKindT, KeywordKindT],
            ParserItem[TokenKindT, KeywordKindT]
        ]
    ]:
        return (
            (self.interned_symbols[nonterminal], self.interned_items[item])
            for (nonterminal, items) in self.nonterminal_items.items()
            for item in items
        )

    def iter_terminal_items_with_symbol(self) -> typing.Iterator[
        typing.Tuple[
            TerminalSymbol[TokenKindT, KeywordKindT],
            ParserItem[TokenKindT, KeywordKindT]
        ]
    ]:
        return (
            (self.interned_symbols[terminal], self.interned_items[item])
            for (terminal, items) in self.terminal_items.items()
            for item in items
        )

    def iter_items_with_symbol(self) -> typing.Iterator[
        typing.Tuple[Symbol[TokenKindT, KeywordKindT], ParserItem[TokenKindT, KeywordKindT]]
    ]:
        return itertools.chain(
            self.iter_nonterminal_items_with_symbol(),
            self.iter_nonterminal_items_with_symbol()
        )

    def iter_nonterminal_items(self) -> typing.Iterable[ParserItem[TokenKindT, KeywordKindT]]:
        return (
            self.interned_items[item]
            for items in self.nonterminal_items.values()
            for item in items
        )

    def iter_terminal_items(self) -> typing.Iterable[ParserItem[TokenKindT, KeywordKindT]]:
        return (
            self.interned_items[item]
            for items in self.terminal_items.values()
            for item in items
        )

    def iter_completed_items(self) -> typing.Iterable[ParserItem[TokenKindT, KeywordKindT]]:
        return self.iter_interned_items(self.completed_items)

    def iter(self) -> typing.Iterable[ParserItem[TokenKindT, KeywordKindT]]:
        return itertools.chain(
            self.iter_nonterminal_items(),
            self.iter_terminal_items(),
            self.iter_completed_items(),
        )

    def add_item(
        self,
        item: ParserItem[TokenKindT, KeywordKindT],
    ) -> bool:
        interned_item = self.interned_items_lookup.get(item)
        if interned_item is None:
            interned_item = len(self.interned_items)
            self.interned_items.append(item)
            self.interned_items_lookup[item] = interned_item

        if len(item[0].rhs) > item[1]:
            current_symbol = item[0].rhs[item[1]]

            if isinstance(current_symbol, NonterminalSymbol):
                container = self.nonterminal_items[current_symbol.id]
            else:
                container = self.terminal_items[current_symbol.id]
        else:
            container = self.completed_items

        length = len(container)
        container.add(interned_item)
        changed = len(container) != length
        if changed:
            self.all_interned_items.add(interned_item)

        return changed


@attr.s(kw_only=True, slots=True)
class ParserState(typing.Generic[TokenKindT, KeywordKindT]):
    id: int = attr.ib()
    items: ItemSet[TokenKindT, KeywordKindT] = attr.ib()

    def dump_state(self) -> str:
        writer = io.StringIO()
        writer.write(f'<parser state #{self.id}>\n')

        for i, (production, position, lookahead) in enumerate(self.items.iter()):
            writer.write(f'  ({i}., pos={position}, lookahead={lookahead}): ')
            writer.write(f'{production.lhs.name} -> ')

            for j, symbol in enumerate(production.rhs):
                if j == position:
                    writer.write(f'* ')

                if isinstance(symbol, NonterminalSymbol):
                    writer.write(f'{symbol.name} ')
                else:
                    writer.write(f'{str(symbol)!r} ')

            writer.write('\n')

        return writer.getvalue()


@attr.s(kw_only=True, slots=True)
class TableBuilder(typing.Generic[TokenKindT, KeywordKindT]):
    table: FrozenParserTable[TokenKindT, KeywordKindT] = attr.ib()

    def add_accept(self, state_id: int) -> None:
        assert EOF.kind is StdTokenKind.EOF
        frozen_eof = self.table.frozen_symbols.get_frozen_terminal(EOF.kind)

        existing_entry = self.table.actions.get((state_id, frozen_eof))
        if (
            existing_entry is not None
            and existing_entry != (ActionKind.ACCEPT, -1)
        ):
            raise ParserGeneratorError(
                'Encountered an impossible conflict while trying to add '
                'an ACCEPT action for state #{0}: {1}'.format(state_id, existing_entry)
            )

        self.table.actions[state_id, frozen_eof] = (ActionKind.ACCEPT, -1)

    def add_shift(
        self,
        state_id: int,
        symbol: TerminalSymbol[TokenKindT, KeywordKindT],
        next_id: int,
    ) -> None:
        frozen_symbol = self.table.frozen_symbols.get_frozen_terminal(symbol.kind)
        assert frozen_symbol.kind is FrozenSymbolKind.TERMINAL

        existing_entry = self.table.actions.get((state_id, frozen_symbol))
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

        self.table.actions[state_id, frozen_symbol] = (ActionKind.SHIFT, next_id)

    def add_reduce(
        self,
        state_id: int,
        symbol: TerminalSymbol[TokenKindT, KeywordKindT],
        production_id: int,
    ) -> None:
        frozen_symbol = self.table.frozen_symbols.get_frozen_terminal(symbol.kind)
        assert frozen_symbol.kind is FrozenSymbolKind.TERMINAL

        existing_entry = self.table.actions.get((state_id, frozen_symbol))
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

        self.table.actions[state_id, frozen_symbol] = (ActionKind.REDUCE, production_id)

    def add_goto(
        self,
        state_id: int,
        symbol: NonterminalSymbol[TokenKindT, KeywordKindT],
        destination_id: int,
    ) -> None:
        frozen_symbol = self.table.frozen_symbols.get_frozen_nonterminal(symbol.name)
        assert frozen_symbol.kind is FrozenSymbolKind.NONTERMINAL

        existing_entry = self.table.gotos.get((state_id, frozen_symbol))
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

        self.table.gotos[state_id, frozen_symbol] = destination_id


# Despite my efforts, the parser table generator is fairly slow.
# Tracing seems to add a huge overhead so the results in 
# README are not that useful for determing the overall speed.
# On CPython, the average speed seems to be around 8.5 seconds
# for the (currently incomplete) grammar. PyPy gets this down
# to around 4.5. I don't think there is much more I can do to meaningfully
# optimize this besides. Cache misses have a negligible performance impact
# and I an not sure its possible to prevent them anyways.
# I will consider working with third party data structures that might help
# with performance. Otherwise, I'll call it good enough.
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
        self.terminals: typing.Dict[
            typing.Union[TokenKindT, KeywordKindT, StdTokenKind],
            TerminalSymbol[TokenKindT, KeywordKindT],
        ] = {}
        self.epsilon_nonterminals: typing.Set[
            NonterminalSymbol[TokenKindT, KeywordKindT]
        ] = set()
        self.first_sets: typing.Dict[
            NonterminalSymbol[TokenKindT, KeywordKindT],
            typing.Set[TerminalSymbol[TokenKindT, KeywordKindT]]
        ] = {}

        self.interned_items_lookup: typing.Dict[ParserItem[TokenKindT, KeywordKindT], int] = {}
        self.interned_items: typing.List[ParserItem[TokenKindT, KeywordKindT]] = []
        self.interned_symbols: typing.List[Symbol[TokenKindT, KeywordKindT]] = []

        self.frozen_symbols = FrozenSymbolTable(tokens, keywords)
        self.states: typing.List[ParserState[TokenKindT, KeywordKindT]] = []
        self.productions: typing.List[Production[TokenKindT, KeywordKindT]] = []
        self.transitions: typing.Dict[typing.Tuple[int, int], int] = {}

        self.precomputed_gotos: typing.Dict[
            typing.Tuple[int, int],
            ParserState[TokenKindT, KeywordKindT],
        ] = {}
        self.precomputed_closures: typing.Dict[
            InternedParserItem,
            typing.List[
                typing.Tuple[
                    NonterminalSymbol[TokenKindT, KeywordKindT],
                    typing.FrozenSet[TerminalSymbol[TokenKindT, KeywordKindT]]
                ]
            ]
        ] = {}
        self.precomputed_states: typing.Dict[
            typing.Tuple[InternedParserItem, ...],
            ParserState[TokenKindT, KeywordKindT],
        ] = {}
        self.precomputed_state_hits = 0
        self.precomputed_state_misses = 0

    def create_item_set(self) -> ItemSet[TokenKindT, KeywordKindT]:
        return ItemSet(
            interned_items=self.interned_items,
            interned_items_lookup=self.interned_items_lookup,
            interned_symbols=self.interned_symbols,
        )

    def create_nonterminal_symbol(
        self,
        *,
        name: str,
        entrypoint: bool = False
    ) -> NonterminalSymbol[TokenKindT, KeywordKindT]:
        symbol = NonterminalSymbol[TokenKindT, KeywordKindT](
            id=len(self.interned_symbols),
            name=name,
            entrypoint=entrypoint,
        )
        self.nonterminals[symbol.name] = symbol
        self.interned_symbols.append(symbol)
        return symbol

    def initialize_nonterminals(self) -> None:
        for rule in self.rules:
            self.create_nonterminal_symbol(
                name=rule.name,
                entrypoint=rule.entrypoint,
            )

    def initialize_terminals(self) -> None:
        for terminal in self.frozen_symbols.terminals:
            symbol = TerminalSymbol(id=len(self.interned_symbols), kind=terminal)
            self.interned_symbols.append(symbol)
            self.terminals[terminal] = symbol

    def initialize_productions(self) -> None:
        for rule in self.rules:
            self.initialize_productions_for_rule(rule)

    def generate_symbols(self) -> None:
        self.initialize_terminals()
        self.initialize_nonterminals()
        self.initialize_productions()

    def generate_frozen_symbols(self) -> None:
        for nonterminal in self.nonterminals.values():
            frozen_nonterminal = self.frozen_symbols.create_frozen_nonterminal(nonterminal.name)

        for production in self.productions:
            frozen_nonterminal = self.frozen_symbols.get_frozen_nonterminal(production.lhs.name)

            frozen_production = self.frozen_symbols.create_frozen_production(
                frozen_nonterminal, len(production.rhs), tuple(production.captured)
            )
            if production.action is not None:
                self.frozen_symbols.add_production_action(frozen_production, production.action)

    def should_capture_uninlined_expression(
        self,
        nonterminal: NonterminalSymbol[TokenKindT, KeywordKindT],
    ) -> bool:
        return any(production.captured for production in nonterminal.productions)

    def create_production(
        self,
        *,
        lhs: NonterminalSymbol[TokenKindT, KeywordKindT],
        action: typing.Optional[str] = None,
    ) -> Production[TokenKindT, KeywordKindT]:
        production = Production(id=len(self.productions), lhs=lhs, action=action)
        self.productions.append(production)
        return production

    def initialize_productions_for_rule(
        self,
        rule: ast.RuleNode[TokenKindT, KeywordKindT]
    ) -> None:
        nonterminal = self.nonterminals[rule.name]

        for item in rule.items:
            production = self.create_production(lhs=nonterminal, action=item.action)
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
        nonterminal = self.create_nonterminal_symbol(name=name)
        self.nonterminals[nonterminal.name] = nonterminal
        # | epsilon
        temporary_production = self.create_production(lhs=nonterminal)
        temporary_production.action = '@sequence'
        nonterminal.productions.append(temporary_production)
        # | nonterminal expr
        temporary_production = self.create_production(lhs=nonterminal)
        temporary_production.action = '@sequence'
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
                nonterminal = self.create_nonterminal_symbol(
                    name=f'plus-{expression.start}-{expression.end}'
                )
                self.nonterminals[nonterminal.name] = nonterminal
                # | expr plus-a:b@star
                temporary_production = self.create_production(lhs=nonterminal)
                temporary_production.action = '@prepend'
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
                nonterminal = self.create_nonterminal_symbol(
                    name=f'optional-{expression.start}-{expression.end}'
                )
                self.nonterminals[nonterminal.name] = nonterminal
                # | epsilon
                temporary_production = self.create_production(lhs=nonterminal)
                temporary_production.action = '@option'
                nonterminal.productions.append(temporary_production)
                # | expr
                temporary_production = self.create_production(lhs=nonterminal)
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
                nonterminal = self.create_nonterminal_symbol(
                    name=f'alternative-{expression.start}-{expression.end}'
                )
                self.nonterminals[nonterminal.name] = nonterminal
                # | lhs
                temporary_production = self.create_production(lhs=nonterminal)
                self.add_symbols_for_expression(
                    temporary_production,
                    expression.lhs,
                    capture=capture,
                )
                nonterminal.productions.append(temporary_production)
                # | rhs
                temporary_production = self.create_production(lhs=nonterminal)
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
                production.add_symbol(self.terminals[expression.keyword], capture)

            case ast.TokenNode():
                production.add_symbol(self.terminals[expression.kind], capture)

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

    @functools.cache
    def get_first_set(
        self,
        symbols: typing.Tuple[Symbol[TokenKindT, KeywordKindT]]
    ) -> typing.FrozenSet[TerminalSymbol[TokenKindT, KeywordKindT]]:
        result: typing.Set[TerminalSymbol[TokenKindT, KeywordKindT]] = set()

        for symbol in symbols:
            if isinstance(symbol, TerminalSymbol):
                result.add(symbol)
            else:
                result.update(self.first_sets[symbol])

            if symbol not in self.epsilon_nonterminals:
                break

        return frozenset(result)

    def compute_closure(
        self,
        items: ItemSet[TokenKindT, KeywordKindT]
    ) -> ParserState[TokenKindT, KeywordKindT]:
        precomputed_key = items.get_intern_items()
        precomputed_state = self.precomputed_states.get(precomputed_key)
        if precomputed_state is not None:
            self.precomputed_state_hits += 1
            return precomputed_state

        changed = True
        while changed:
            changed = False

            first_sets: typing.List[
                typing.Tuple[
                    NonterminalSymbol[TokenKindT, KeywordKindT],
                    typing.FrozenSet[TerminalSymbol[TokenKindT, KeywordKindT]]
                ],
            ] = []
            computed_closures: typing.Dict[
                InternedParserItem,
                typing.List[
                    typing.Tuple[
                        NonterminalSymbol[TokenKindT, KeywordKindT],
                        typing.FrozenSet[TerminalSymbol[TokenKindT, KeywordKindT]]
                    ]
                ]
            ] = {}
        
            for interned_symbol, interned_items in items.nonterminal_items.items():
                symbol = self.interned_symbols[interned_symbol]
                assert isinstance(symbol, NonterminalSymbol)

                for interned_item in interned_items:
                    precomputed_closure = self.precomputed_closures.get(interned_item)
                    if precomputed_closure is not None:
                        first_sets.extend(precomputed_closure)
                        continue

                    if interned_item not in computed_closures:
                        computed_closure = computed_closures[interned_item] = []
                    else:
                        computed_closure = computed_closures[interned_item]

                    (production, position, lookahead) = self.interned_items[interned_item]
                    trailing_symbols = production.rhs[position + 1:]

                    for lookahead_symbol in lookahead:
                        first_set = self.get_first_set(
                            (*trailing_symbols, lookahead_symbol)
                        )
                        if first_set:
                            computed_closure.append((symbol, first_set))
                            first_sets.append((symbol, first_set))

            self.precomputed_closures.update(computed_closures)

            for symbol, first_set in first_sets:
                for production in symbol.productions:
                    added = items.add_item((production, 0, first_set))
                    if added:
                        changed = changed or added

        next_state = None
        for state in self.states:
            if state.items == items:
                next_state = state

        if next_state is None:
            next_state = self.create_state(items)
        else:
            self.precomputed_state_misses += 1

        self.precomputed_states[precomputed_key] = next_state
        return next_state

    def compute_goto(
        self,
        state: ParserState[TokenKindT, KeywordKindT],
        symbol: Symbol[TokenKindT, KeywordKindT],
    ) -> ParserState[TokenKindT, KeywordKindT]:
        result = self.create_item_set()

        if isinstance(symbol, NonterminalSymbol):
            mapping = state.items.nonterminal_items
        else:
            mapping = state.items.terminal_items

        for production, position, lookahead in state.items.iter_interned_items(mapping[symbol.id]):
            result.add_item((production, position + 1, lookahead))

        next_state = self.compute_closure(result)
        self.precomputed_gotos[state.id, symbol.id] = next_state
        return next_state

    def create_state(
        self,
        items: ItemSet[TokenKindT, KeywordKindT],
    ) -> ParserState[TokenKindT, KeywordKindT]:
        state = ParserState(id=len(self.states), items=items)
        self.states.append(state)
        return state

    def dump_states(self) -> typing.List[str]:
        return [state.dump_state() for state in self.states]

    def get_equivalent_state(
        self,
        items: ItemSet[TokenKindT, KeywordKindT]
    ) -> typing.Optional[ParserState[TokenKindT, KeywordKindT]]:
        for state in self.states:
            if state.items == items:
                return state        

    def compute_canonical_collection(self, entrypoint: ParserItem[TokenKindT, KeywordKindT]) -> None:
        items: ItemSet[TokenKindT, KeywordKindT] = self.create_item_set()
        items.add_item(entrypoint)
        self.compute_closure(items)

        changed = True
        while changed:
            changed = False
            logger.debug('Created %s states', len(self.states))

            for state in self.states:
                for symbol in state.items.iter_symbols():
                    next_state = self.precomputed_gotos.get((state.id, symbol.id))
                    if next_state is None:
                        next_state = self.compute_goto(state, symbol)
                        changed = True

                    transition = self.transitions.get((state.id, symbol.id))
                    if (
                        transition is not None
                        and transition != next_state.id
                    ):
                        raise ParserGeneratorError(
                            'Encountered an impossible conflict while trying to '
                            'set transition state #{0}, symbol {1} to {2}. '
                            'The transition is already set to {3}.'.format(
                                state.id,
                                symbol,
                                next_state.id,
                                transition,
                            )
                        )

                    self.transitions[state.id, symbol.id] = next_state.id

                if changed:
                    break

        logger.info(
            'Finished generating %s states. [State cache hits: %s, state cache misses: %s]',
            len(self.states),
            self.precomputed_state_hits,
            self.precomputed_state_misses,
        )

    def compute_tables(
        self,
        entrypoint: ParserItem[TokenKindT, KeywordKindT],
    ) -> FrozenParserTable[TokenKindT, KeywordKindT]:
        table = FrozenParserTable(frozen_symbols=self.frozen_symbols)
        builder = TableBuilder(table=table)
        self.compute_canonical_collection(entrypoint)

        for state in self.states:
            for (production, _, lookahed) in state.items.iter_completed_items():
                if production.lhs.entrypoint:
                    builder.add_accept(state.id)
                else:
                    for lookahead_symbol in lookahed:
                        builder.add_reduce(state.id, lookahead_symbol, production.id)

            for symbol, (production, _, lookahed) in state.items.iter_terminal_items_with_symbol():
                transition = self.transitions.get((state.id, symbol.id))
                if transition is not None:
                    builder.add_shift(state.id, symbol, transition)

            for nonterminal in self.nonterminals.values():
                transition = self.transitions.get((state.id, nonterminal.id))
                if transition is not None:
                    builder.add_goto(state.id, nonterminal, transition)

        for state in self.states:
            if not any(state_id == state.id for state_id, _ in table.actions):
                raise ParserGeneratorError(f'State #{state.id} has no actions')

        return table

    def generate(self) -> typing.Dict[str, FrozenParserTable[TokenKindT, KeywordKindT]]:
        self.generate_symbols()
        self.generate_frozen_symbols()
        self.compute_epsilon_nonterminals()
        self.compute_first_sets()

        tables: typing.Dict[str, FrozenParserTable[TokenKindT, KeywordKindT]] = {}
        for nonterminal in self.nonterminals.values():
            if nonterminal.entrypoint:
                if len(nonterminal.productions) != 1:
                    raise ParserGeneratorError(
                        f'Grammar entrypoint {nonterminal.name!r} has more than one production'
                    )
            
                production = nonterminal.productions[0]
                table = self.compute_tables((production, 0, frozenset((EOF,))))
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
    ) -> typing.Dict[str, FrozenParserTable[TokenKindT, KeywordKindT]]:
        rules = GrammarParser[TokenKindT, KeywordKindT].parse_from_source(grammar, tokens, keywords)
        instance = cls(tokens, keywords, rules)
        return instance.generate()
