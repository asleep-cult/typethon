from __future__ import annotations

import attr
import enum
import typing
import logging
import io

from . import ast
from .frozen import (
    ActionKind,
    FrozenSymbolTable,
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
from ..syntax.tokens import StdTokenKind, TokenMap, KeywordMap, STD_TOKENS

logger = logging.getLogger(__name__)

TokenKindT = typing.TypeVar('TokenKindT', bound=enum.Enum)
KeywordKindT = typing.TypeVar('KeywordKindT', bound=enum.Enum)


InternedSymbol = int
InternedParserItem = int
LookaheadSet = int
InternedCanonicalCollection = int

ParserItem = typing.Tuple[
    Production[TokenKindT, KeywordKindT],
    int,
]
CanonicalCollection = typing.Tuple[
    typing.Tuple[InternedParserItem, ...],
    typing.Tuple[LookaheadSet, ...],
]


@attr.s(kw_only=True, slots=True)
class ParserState:
    items: typing.List[InternedParserItem] = attr.ib(factory=list)
    lookahead: typing.Dict[InternedParserItem, LookaheadSet] = attr.ib(factory=dict)


@attr.s(kw_only=True, slots=True)
class TableBuilder(typing.Generic[TokenKindT, KeywordKindT]):
    genereator: ParserTableGenerator[TokenKindT, KeywordKindT] = attr.ib()
    table: FrozenParserTable[TokenKindT, KeywordKindT] = attr.ib()

    def get_action_entry_note_message(
        self,
        which: str,
        entry: typing.Tuple[ActionKind, int],
    ) -> typing.Optional[str]:
        if entry[0] == ActionKind.SHIFT:
            dumped = self.genereator.dump_canonical_collection(entry[1])
            return f'The next state of the {which} entry is as follows: {dumped}'
        elif entry[0] == ActionKind.REDUCE:
            production = self.genereator.productions[entry[1]]
            return f'The existing entry reduced by the following procuction: {production}\n'

    def get_action_table_conflict_message(
        self,
        symbol: TerminalSymbol[TokenKindT, KeywordKindT],
        state_id: int,
        existing_entry: typing.Tuple[ActionKind, int],
        new_entry: typing.Tuple[ActionKind, int],
    ) -> str:      
        dumped = self.genereator.dump_canonical_collection(state_id)

        writer = io.StringIO()
        writer.write(
            f'Encountered a {existing_entry[0].name}/{new_entry[0].name} conflict '
            f'while trying to add an {new_entry[0].name} action for symbol {symbol.kind.name} '
            f'in #{state_id}. Note: The existing current is as follows:\n{dumped}'
        )

        note = self.get_action_entry_note_message('existing', existing_entry)
        if note is not None:
            writer.write(note)

        note = self.get_action_entry_note_message('new', new_entry)
        if note is not None:
            writer.write(note)

        return writer.getvalue()

    def add_accept(self, state_id: int, production: Production[TokenKindT, KeywordKindT]) -> None:
        new_entry = (ActionKind.ACCEPT, production.id)
        existing_entry = self.table.actions.get((state_id, EOF.id))
        if (
            existing_entry is not None
            and existing_entry != new_entry
        ):
            message = self.get_action_table_conflict_message(
                EOF,
                state_id,
                existing_entry,
                new_entry,
            )
            self.genereator.report_conflict(message)

        self.table.actions[state_id, EOF.id] = new_entry

    def add_shift(
        self,
        state_id: int,
        symbol: TerminalSymbol[TokenKindT, KeywordKindT],
        next_id: int,
    ) -> None:
        existing_entry = self.table.actions.get((state_id, symbol.id))
        new_entry = (ActionKind.SHIFT, next_id)
        if (
            existing_entry is not None
            and existing_entry != new_entry
        ):
            recoverable = existing_entry[0] is ActionKind.REDUCE
            message = self.get_action_table_conflict_message(
                symbol,
                state_id,
                existing_entry,
                new_entry,
            )
            self.genereator.report_conflict(message, recoverable=recoverable)

        self.table.actions[state_id, symbol.id] = new_entry

    def add_reduce(
        self,
        state_id: int,
        symbol: TerminalSymbol[TokenKindT, KeywordKindT],
        production: Production[TokenKindT, KeywordKindT],
    ) -> None:
        existing_entry = self.table.actions.get((state_id, symbol.id))
        new_entry = (ActionKind.REDUCE, production.id)
        if (
            existing_entry is not None
            and existing_entry != new_entry
        ):
            recoverable = existing_entry[0] is ActionKind.SHIFT
            message = self.get_action_table_conflict_message(
                symbol,
                state_id,
                existing_entry,
                new_entry
            )
            self.genereator.report_conflict(message, recoverable=recoverable)

        self.table.actions[state_id, symbol.id] = (ActionKind.REDUCE, production.id)

    def add_goto(
        self,
        state_id: int,
        symbol: NonterminalSymbol[TokenKindT, KeywordKindT],
        destination_id: int,
    ) -> None:
        existing_entry = self.table.gotos.get((state_id, symbol.id))
        if (
            existing_entry is not None
            and existing_entry != destination_id
        ):
            message = (
                'Encountered impossible conflict while trying to add '
                'an entry to add an entry to the goto table state #{0}, '
                'symbol {1}, destination: state #{2}: {3}'.format(
                    state_id,
                    symbol,
                    destination_id,
                    existing_entry,
                )
            )
            self.genereator.report_conflict(message)

        self.table.gotos[state_id, symbol.id] = destination_id


# Finally, the parser generator is quick and seems to work well.
class ParserTableGenerator(typing.Generic[TokenKindT, KeywordKindT]):
    def __init__(
        self,
        tokens: TokenMap[TokenKindT],
        keywords: KeywordMap[KeywordKindT],
        rules: typing.List[ast.RuleNode[TokenKindT, KeywordKindT]],
    ) -> None:
        self.terminal_kinds: typing.List[
            typing.Union[StdTokenKind, TokenKindT, KeywordKindT]
        ] = []
        self.terminal_kinds.extend(std_token for _, std_token in STD_TOKENS)
        self.terminal_kinds.extend(token for _, token in tokens)
        self.terminal_kinds.extend(keyword for _, keyword in keywords)

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
            LookaheadSet,
        ] = {}

        self.interned_items_lookup: typing.Dict[
            ParserItem[TokenKindT, KeywordKindT],
            InternedParserItem
        ] = {}
        self.interned_items: typing.List[ParserItem[TokenKindT, KeywordKindT]] = []

        self.interned_symbols: typing.List[Symbol[TokenKindT, KeywordKindT]] = []

        self.interned_canonical_collections_lookup: typing.Dict[
            CanonicalCollection, InternedCanonicalCollection
        ] = {}
        self.interned_canonical_collections: typing.List[CanonicalCollection] = []

        self.productions: typing.List[Production[TokenKindT, KeywordKindT]] = []
        self.transitions: typing.Dict[
            typing.Tuple[InternedCanonicalCollection, InternedSymbol],
            InternedCanonicalCollection,
        ] = {}

        self.precomputed_gotos: typing.Dict[
            typing.Tuple[InternedCanonicalCollection, InternedSymbol],
            InternedCanonicalCollection,
        ] = {}

    def report_conflict(
        self,
        message: str,
        *,
        recoverable: bool = False
    ) -> None:
        if not recoverable:
            raise ParserGeneratorError(message)

        logger.debug(message)

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
        for kind in self.terminal_kinds:
            symbol = TerminalSymbol(id=len(self.interned_symbols), kind=kind)
            self.interned_symbols.append(symbol)
            self.terminals[kind] = symbol

    def initialize_productions(self) -> None:
        for rule in self.rules:
            self.initialize_productions_for_rule(rule)

    def generate_symbols(self) -> None:
        self.initialize_terminals()
        self.initialize_nonterminals()
        self.initialize_productions()

    def generate_frozen_symbols(self) -> FrozenSymbolTable[TokenKindT, KeywordKindT]:
        symbol_table = FrozenSymbolTable(self.interned_symbols)

        for production in self.productions:
            frozen_production = symbol_table.create_frozen_production(
                production.lhs.id,
                len(production.rhs),
                tuple(production.captured),
            )
            if production.action is not None:
                symbol_table.add_production_action(
                    frozen_production.id,
                    production.action,
                )

        return symbol_table

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
            self.first_sets[nonterminal] = 0

            for production in nonterminal.productions:
                for symbol in production.rhs:
                    if isinstance(symbol, TerminalSymbol):
                        self.first_sets[nonterminal] |= 1 << symbol.id

                    if symbol not in self.epsilon_nonterminals:
                        break

        changed = True
        while changed:
            changed = False
            for nonterminal in self.nonterminals.values():
                bitset = self.first_sets[nonterminal]

                for production in nonterminal.productions:
                    for symbol in production.rhs:
                        if isinstance(symbol, NonterminalSymbol):
                            lookahead = self.first_sets[symbol]

                            changed = changed or (bitset & lookahead) != lookahead
                            self.first_sets[nonterminal] |= lookahead

                        if symbol not in self.epsilon_nonterminals:
                            break

    def iter_bitset(
        self,
        bitset: int
    ) -> typing.Iterator[TerminalSymbol[TokenKindT, KeywordKindT]]:
        return (
            typing.cast(
                TerminalSymbol[TokenKindT, KeywordKindT],
                self.interned_symbols[interned_symbol]
            )
            for interned_symbol in range(bitset.bit_length())
            if bitset & (1 << interned_symbol)
        )

    def get_first_set(
        self,
        symbols: typing.List[Symbol[TokenKindT, KeywordKindT]]
    ) -> LookaheadSet:
        result = 0

        for symbol in symbols:
            if isinstance(symbol, TerminalSymbol):
                result |= 1 << symbol.id
            else:
                result |= self.first_sets[symbol]

            if symbol not in self.epsilon_nonterminals:
                break

        return result

    def dump_canonical_collection(self, interned_collection: InternedCanonicalCollection) -> str:
        writer = io.StringIO()
        writer.write(f'<parser state dump #{interned_collection}>\n')

        interned_items, lookaheads = self.interned_canonical_collections[interned_collection]
        for i, (interned_item, lookahead) in enumerate(zip(interned_items, lookaheads)):
            production, position = self.interned_items[interned_item]

            string = ', '.join(
                lookahead.kind.name
                for lookahead in self.iter_bitset(lookahead)
            )
            writer.write(f'  ({i}., pos={position}, lookahead={{{string}}}):')
            writer.write(f' {production.lhs.name} ->')

            for j, symbol in enumerate(production.rhs):
                if j == position:
                    writer.write(' *')

                if isinstance(symbol, NonterminalSymbol):
                    writer.write(f' {symbol.name}')
                else:
                    writer.write(f' {str(symbol)!r}')

            if len(production.rhs) <= position:
                writer.write(' *')

            writer.write('\n')

        return writer.getvalue()

    def get_interned_item(self, item: ParserItem[TokenKindT, KeywordKindT]) -> InternedParserItem:
        interned_item = self.interned_items_lookup.get(item)
        if interned_item is not None:
            return interned_item

        interned_item = len(self.interned_items)
        self.interned_items.append(item)
        self.interned_items_lookup[item] = interned_item
        return interned_item

    def get_interned_canonical_collection(self, state: ParserState) -> InternedCanonicalCollection:
        interned_tuple = tuple(sorted(state.items))
        lookahead_tuple = tuple(state.lookahead[interned_item] for interned_item in interned_tuple)

        canonical_collection = interned_tuple, lookahead_tuple
        interned_collection = self.interned_canonical_collections_lookup.get(canonical_collection)
        if interned_collection is not None:
            return interned_collection

        interned_collection = len(self.interned_canonical_collections)
        self.interned_canonical_collections.append(canonical_collection)
        self.interned_canonical_collections_lookup[canonical_collection] = interned_collection

        return interned_collection

    def compute_closure(
        self,
        state: ParserState,
    ) -> InternedCanonicalCollection:
        changed = True
        while changed:
            changed = False

            for interned_item in state.items:
                production, position = self.interned_items[interned_item]
                if len(production.rhs) <= position:
                    continue

                current_symbol = production.rhs[position]
                if not isinstance(current_symbol, NonterminalSymbol):
                    continue

                lookahead = state.lookahead[interned_item]
                trailing_symbols = production.rhs[position + 1:]
                next_lookahead = self.get_first_set(trailing_symbols)

                if all(
                    trailing_symbol in self.epsilon_nonterminals
                    for trailing_symbol in trailing_symbols
                ):
                    next_lookahead |= lookahead

                for production in current_symbol.productions:
                    next_interned_item = self.get_interned_item((production, 0))

                    if next_interned_item not in state.items:
                        changed = True
                        state.items.append(next_interned_item)
                        state.lookahead[next_interned_item] = next_lookahead

                    elif (state.lookahead[next_interned_item] & next_lookahead) != next_lookahead:
                        changed = True
                        state.lookahead[next_interned_item] |= next_lookahead

        return self.get_interned_canonical_collection(state)

    def compute_goto(
        self,
        interned_collection: InternedCanonicalCollection,
        symbol: Symbol[TokenKindT, KeywordKindT],
    ) -> InternedCanonicalCollection:
        state = ParserState()
    
        interned_items, lookaheads = self.interned_canonical_collections[interned_collection]
        for interned_item, lookahead in zip(interned_items, lookaheads):
            production, position = self.interned_items[interned_item]

            if len(production.rhs) > position and production.rhs[position] == symbol:
                inner_interned_item = self.get_interned_item((production, position + 1))
                state.items.append(inner_interned_item)
                state.lookahead[inner_interned_item] = lookahead

        next_interned_collection = self.compute_closure(state)
        self.precomputed_gotos[interned_collection, symbol.id] = next_interned_collection

        return next_interned_collection

    def compute_canonical_collection(
        self,
        production: Production[TokenKindT, KeywordKindT]
    ) -> None:
        interned_item = self.get_interned_item((production, 0))
        entry_state = ParserState(
            items=[interned_item],
            lookahead={interned_item: 1 << EOF.id}
        )
        interned_collection = self.compute_closure(entry_state)

        changed = True
        while changed:
            changed = False
            logger.debug('Created %s states', len(self.interned_canonical_collections))

            for (interned_items, _), interned_collection in (
                tuple(self.interned_canonical_collections_lookup.items())
            ):
                for interned_item in interned_items:
                    production, position = self.interned_items[interned_item]
                    if len(production.rhs) <= position:
                        continue

                    current_symbol = production.rhs[position]
                    next_interned_collection = self.precomputed_gotos.get(
                        (interned_collection, current_symbol.id)
                    )
                    if next_interned_collection is None:
                        changed = True
                        next_interned_collection = self.compute_goto(interned_collection, current_symbol)

                    transition = self.transitions.get((interned_collection, current_symbol.id))
                    if (
                        transition is not None
                        and transition != next_interned_collection
                    ):
                        raise ParserGeneratorError(
                            'Encountered an impossible conflict while trying to '
                            'set transition state #{0}, symbol {1} to {2}. '
                            'The transition is already set to {3}.'.format(
                                interned_collection,
                                current_symbol,
                                next_interned_collection,
                                transition,
                            )
                        )

                    self.transitions[interned_collection, current_symbol.id] = next_interned_collection

        logger.info(
            'Finished generating %s states.',
            len(self.interned_canonical_collections),
        )

    def compute_tables(
        self,
        entrypoint: Production[TokenKindT, KeywordKindT],
    ) -> FrozenParserTable[TokenKindT, KeywordKindT]:
        symbol_table = self.generate_frozen_symbols()
        table = FrozenParserTable(frozen_symbols=symbol_table)
        builder = TableBuilder(genereator=self, table=table)
        self.compute_canonical_collection(entrypoint)

        for (interned_items, lookaheads), interned_collection in (
            self.interned_canonical_collections_lookup.items()
        ):
            for interned_item, lookahead in zip(interned_items, lookaheads):
                production, position = self.interned_items[interned_item]

                if len(production.rhs) <= position:
                    if production.lhs.entrypoint:
                        builder.add_accept(interned_collection, production)
                    else:
                        for lookahead_symbol in self.iter_bitset(lookahead):
                            builder.add_reduce(interned_collection, lookahead_symbol, production)
                
                    continue

                current_symbol = production.rhs[position]
                if not isinstance(current_symbol, TerminalSymbol):
                    continue

                transition = self.transitions.get((interned_collection, current_symbol.id))
                if transition is not None:
                    builder.add_shift(interned_collection, current_symbol, transition)

            for nonterminal in self.nonterminals.values():
                transition = self.transitions.get((interned_collection, nonterminal.id))
                if transition is not None:
                    builder.add_goto(interned_collection, nonterminal, transition)

        for interned_collection in self.interned_canonical_collections_lookup.values():
            if not any(state_id == interned_collection for state_id, _ in table.actions):
                raise ParserGeneratorError(f'State #{interned_collection} has no actions')

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
                table = self.compute_tables(production)
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
