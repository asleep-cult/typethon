from __future__ import annotations

import attr
import typing
import enum

from .frozen import (
    FrozenSymbol,
    ActionKind,
    FrozenParserTable,
    UNSET_ACTION,
    UNSET_GOTO,
)
from .exceptions import (
    ParserAutomatonError,
    UnexpectedTokenError,
    StackUnderflowError,
    DeadlockError,
)
from ..syntax.scanner import Scanner
from ..syntax.tokens import Token


T = typing.TypeVar('T')
TokenKindT = typing.TypeVar('TokenKindT', bound=enum.Enum)
KeywordKindT = typing.TypeVar('KeywordKindT', bound=enum.Enum)
NodeT = typing.TypeVar('NodeT', bound='NodeItem[typing.Any, typing.Any]')
ItemT = typing.TypeVar('ItemT', bound='NodeItem[typing.Any, typing.Any]')


class NodeLike(typing.Protocol):
    @property
    def start(self) -> int: ...

    @property
    def end(self) -> int: ...


@attr.s(kw_only=True, slots=True)
class Node(typing.Generic[TokenKindT, KeywordKindT]):
    start: int = attr.ib()
    end: int = attr.ib()
    items: typing.List[NodeItem[TokenKindT, KeywordKindT]] = attr.ib()


@attr.s(kw_only=True, slots=True)
class SequenceNode(typing.Generic[NodeT]):
    start: int = attr.ib()
    end: int = attr.ib()
    items: typing.List[NodeT] = attr.ib()


@attr.s(kw_only=True, slots=True)
class OptionNode(typing.Generic[NodeT]):
    start: int = attr.ib()
    end: int = attr.ib()
    item: typing.Optional[NodeT] = attr.ib(default=None)

    def map(self, fn: typing.Callable[[NodeT], T]) -> typing.Optional[T]:
        if self.item is not None:
            return fn(self.item)

    def sequence(self: OptionNode[SequenceNode[ItemT]]) -> SequenceNode[ItemT]:
        # get the flattened node or create an empty one
        if self.item is None:
            return SequenceNode[ItemT](start=self.start, end=self.end, items=[])

        assert isinstance(self.item, SequenceNode)
        return self.item


NodeItem = typing.Union[
    NodeLike,
    SequenceNode['NodeItem[TokenKindT, KeywordKindT]'],
    OptionNode['NodeItem[TokenKindT, KeywordKindT]'],
    Token[TokenKindT, KeywordKindT],
]


@attr.s(kw_only=True, slots=True)
class Transformer(typing.Generic[TokenKindT, KeywordKindT]):
    name: str = attr.ib()
    callback: typing.Callable[..., NodeItem[TokenKindT, KeywordKindT]] = attr.ib()

    def transform(
        self,
        span: typing.Tuple[int, int],
        items: typing.List[NodeItem[TokenKindT, KeywordKindT]],
    ) -> NodeItem[TokenKindT, KeywordKindT]:
        return self.callback(span, *items)

    @classmethod
    def from_function(
        cls,
        function: typing.Callable[..., NodeItem[TokenKindT, KeywordKindT]]
    ) -> Transformer[TokenKindT, KeywordKindT]:
        return cls(name=function.__name__, callback=function)


class ParserAutomaton(typing.Generic[TokenKindT, KeywordKindT]):
    # https://www.cs.uaf.edu/~chappell/class/2023_spr/cs331/lect/cs331-20230220-shiftred.pdf
    def __init__(
        self,
        scanner: Scanner[TokenKindT, KeywordKindT],
        table: FrozenParserTable[TokenKindT, KeywordKindT],
        transformers: typing.Iterable[Transformer[TokenKindT, KeywordKindT]],
        *,
        deadlock_threshold: int = 500,
    ) -> None:
        self.scanner = scanner
        self.table = table
        self.transformers = {transformer.name: transformer for transformer in transformers}
        self.deadlock_threshold = deadlock_threshold

        self.tokens: typing.List[Token[TokenKindT, KeywordKindT]] = []
        self.stack: typing.List[
            typing.Tuple[
                # typing.Optional[FrozenSymbol],
                typing.Optional[NodeItem[TokenKindT, KeywordKindT]],
                int
            ]
        ] = [(None, 0)]

        self.transformers['@prepend'] = Transformer.from_function(self.transform_prepend)
        self.transformers['@flatten'] = Transformer.from_function(self.transform_flatten)
        self.transformers['@sequence'] = Transformer.from_function(self.transform_sequence)
        self.transformers['@option'] = Transformer.from_function(self.transform_option)

    def current_state(self) -> int:
        if not self.stack:
            raise StackUnderflowError(
                'Automaton attempted to access current state with an empty stack'
            )

        return self.stack[-1][1]

    def peek_token(self, amount: int) -> Token[TokenKindT, KeywordKindT]:
        # Infinite lookahead for disambiguation in user-defined transformers
        while len(self.tokens) < amount:
            self.tokens.append(self.scanner.scan())

        return self.tokens[amount - 1]

    def current_symbol(self) -> FrozenSymbol:
        if self.tokens:
            token = self.tokens[0]
        else:
            token = self.scanner.scan()
            self.tokens.append(token)

        return token.kind.name

    def advance(self) -> Token[TokenKindT, KeywordKindT]:
        if not self.tokens:
            raise ParserAutomatonError('Automaton called advance with no items on stack')

        return self.tokens.pop(0)

    def pop_stack(
        self,
        index: int,
        captured: typing.Optional[typing.Tuple[int, ...]] = None,
    ) -> typing.List[NodeItem[TokenKindT, KeywordKindT]]:
        items: typing.List[NodeItem[TokenKindT, KeywordKindT]] = []

        if index:
            for i, (item, _) in enumerate(self.stack[-index:]):
                assert item is not None
                if captured is None or i in captured:
                    items.append(item)

            del self.stack[-index:]

        return items

    def get_item_span(
        self,
        items: typing.List[NodeItem[TokenKindT, KeywordKindT]],
    ) -> typing.Tuple[int, int]:
        if not items:
            return (0, 0)
        
        return (items[0].start, items[-1].end)

    def create_default_node(
        self,
        items: typing.List[NodeItem[TokenKindT, KeywordKindT]]
    ) -> NodeItem[TokenKindT, KeywordKindT]:
        if len(items) == 1:
            return items[0]

        start, end = self.get_item_span(items)
        return Node(start=start, end=end, items=items)

    def transform_prepend(
        self,
        span: typing.Tuple[int, int],
        first_item: ItemT,
        star_item: SequenceNode[ItemT],
    ) -> SequenceNode[ItemT]:
        star_item.items.insert(0, first_item)
        return star_item

    def flatten_recursive(
        self,
        sequence: SequenceNode[NodeItem[TokenKindT, KeywordKindT]],
        item: NodeItem[TokenKindT, KeywordKindT],
    ) -> None:
        if isinstance(item, SequenceNode):
            for inner_item in item.items:
                self.flatten_recursive(sequence, inner_item)
        else:
            sequence.items.append(item)

    def transform_flatten(
        self,
        span: typing.Tuple[int, int],
        *items: NodeItem[TokenKindT, KeywordKindT],
    ) -> NodeItem[TokenKindT, KeywordKindT]:
        sequence = SequenceNode[NodeItem[TokenKindT, KeywordKindT]](
            start=span[0], end=span[1], items=[]
        )
        for item in items:
            self.flatten_recursive(sequence, item)

        return sequence

    def transform_sequence(
        self,
        span: typing.Tuple[int, int],
        *items: NodeItem[TokenKindT, KeywordKindT],
    ) -> NodeItem[TokenKindT, KeywordKindT]:
        if not items:
            return SequenceNode[NodeItem[TokenKindT, KeywordKindT]](
                start=span[0], end=span[1], items=[]
            )

        first_item = items[0]
        if not isinstance(first_item, SequenceNode):
            assert len(items) == 1

            first_item = SequenceNode(
                start=span[0],
                end=span[1],
                items=[first_item]
            )

        first_item.items.extend(items[1:])
        first_item.start, first_item.end = span
        return first_item

    def transform_option(
        self,
        span: typing.Tuple[int, int],
        *items: NodeItem[TokenKindT, KeywordKindT],
    ) -> NodeItem[TokenKindT, KeywordKindT]:
        if not items:
            return OptionNode[typing.Any](start=-1, end=-1)

        list_items = list(items)
        return OptionNode(
            start=span[0],
            end=span[1],
            item=self.create_default_node(list_items)
        )

    def next_action(self) -> typing.Optional[NodeItem[TokenKindT, KeywordKindT]]:
        current_state = self.current_state()
        terminal_symbol = self.current_symbol()

        interned_symbol = self.table.frozen_symbols.get_interned_terminal(terminal_symbol)
        entry = self.table.get_action(current_state, interned_symbol)
        if entry == UNSET_ACTION:
            symbols = [
                self.table.frozen_symbols.get_frozen_symbol(i)
                for i, entry in enumerate(self.table.actions[current_state])
                if entry != UNSET_ACTION
            ]
            string = ', '.join(symbols)
            raise UnexpectedTokenError(
                f'Automaton encountered an unexpected token {terminal_symbol!r} in state #{current_state}. '
                f'The next token should have been one of the following: {string}. ({self.scanner.position})'
            )

        action = entry[0]
        match action:
            case ActionKind.SHIFT:
                token = self.advance()
                next_state = entry[1]
                self.stack.append((token, next_state))

            case ActionKind.REDUCE:
                production_id = entry[1]
                frozen_production = self.table.frozen_symbols.get_frozen_production(production_id)

                items = self.pop_stack(frozen_production.rhs_length, frozen_production.captured)

                action = self.table.frozen_symbols.get_frozen_action(frozen_production.id)
                if action is not None:
                    transformer = self.transformers[action]
                    node = transformer.transform(self.get_item_span(items), items)
                else:
                    node = self.create_default_node(items)

                current_state = self.current_state()

                next_state = self.table.get_goto(current_state, frozen_production.lhs)
                if next_state == UNSET_GOTO:
                    nonterminal = self.table.frozen_symbols.get_frozen_symbol(frozen_production.lhs)
                    raise ParserAutomatonError(
                        f'Automaton found no GOTO for {nonterminal} in {current_state}'
                    )

                self.stack.append((node, next_state))

            case ActionKind.ACCEPT:
                production_id = entry[1]
                items = self.pop_stack(len(self.stack) - 1)

                action = self.table.frozen_symbols.get_frozen_action(production_id)
                if action is not None:
                    transformer = self.transformers[action]
                    return transformer.transform(self.get_item_span(items), items)
                else:
                    return self.create_default_node(items)

    def parse(self) -> NodeItem[TokenKindT, KeywordKindT]:
        position = self.scanner.position
        stagnant_iterations = 0

        while True:
            result = self.next_action()
            if result is not None:
                return result

            if self.scanner.position == position:
                stagnant_iterations += 1
            else:
                position = self.scanner.position
                stagnant_iterations = 0

            if stagnant_iterations > self.deadlock_threshold:
                raise DeadlockError(
                    f'Automaton has been stagnant for {stagnant_iterations} iterations'
                )
