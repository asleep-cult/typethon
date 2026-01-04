from __future__ import annotations

import attr
import typing
import enum

from .frozen import FrozenSymbol
from .exceptions import (
    ParserAutomatonError,
    UnexpectedTokenError,
    StackUnderflowError,
    DeadlockError,
    TokenRejectedError,
)
from .generator import ActionKind, ParserTable
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
class FlattenNode(typing.Generic[NodeT]):
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

    def flatten(self: OptionNode[FlattenNode[ItemT]]) -> FlattenNode[ItemT]:
        # get the flattened node or create an empty one
        if self.item is None:
            return FlattenNode[ItemT](start=self.start, end=self.end, items=[])

        assert isinstance(self.item, FlattenNode)
        return self.item


NodeItem = typing.Union[
    NodeLike,
    FlattenNode['NodeItem[TokenKindT, KeywordKindT]'],
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
        table: ParserTable[TokenKindT, KeywordKindT],
        transformers: typing.Iterable[Transformer[TokenKindT, KeywordKindT]],
        *,
        deadlock_threshold: int = 10,
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

        self.transformers['@flatten_star'] = Transformer.from_function(self.transform_flatten_star)
        # Call it prepend
        self.transformers['@flatten_plus'] = Transformer.from_function(self.transform_flatten_plus)
        self.transformers['@option'] = Transformer.from_function(self.transform_option)

    def current_state(self) -> int:
        if not self.stack:
            raise StackUnderflowError(
                'Automaton attempted to access current state with an empty stack'
            )

        return self.stack[-1][1]

    def current_symbol(self) -> FrozenSymbol:
        if self.tokens:
            token = self.tokens[0]
        else:
            token = self.scanner.scan()
            self.tokens.append(token)

        return self.table.frozen_symbols.get_frozen_terminal(token.kind)

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

    def transform_flatten_star(
        self,
        span: typing.Tuple[int, int],
        *items: NodeItem[TokenKindT, KeywordKindT],
    ) -> NodeItem[TokenKindT, KeywordKindT]:
        if not items:
            return FlattenNode[typing.Any](start=span[0], end=span[1], items=[])

        first_item = items[0]
        assert isinstance(first_item, FlattenNode)

        first_item.items.extend(items[1:])
        first_item.start, first_item.end = span
        return first_item

    def transform_flatten_plus(
        self,
        span: typing.Tuple[int, int],
        first_item: NodeItem[TokenKindT, KeywordKindT],
        star_item: FlattenNode[typing.Any],
    ) -> NodeItem[TokenKindT, KeywordKindT]:
        star_item.items.insert(0, first_item)
        return star_item

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

        entry = self.table.get_action(current_state, terminal_symbol)
        if entry is None:
            token = self.table.frozen_symbols.terminals[terminal_symbol.id]
            raise UnexpectedTokenError(
                f'Automaton encountered an unexpected token {token!r} in state #{current_state}'
            )

        action = entry[0]
        match action:
            case ActionKind.SHIFT:
                token = self.advance()
                next_state = entry[1]
                self.stack.append((token, next_state))

            case ActionKind.REDUCE:
                production_id = entry[1]
                frozen_production = self.table.frozen_symbols.frozen_productions[production_id]

                items = self.pop_stack(frozen_production.rhs_length, frozen_production.captured)

                action = self.table.frozen_symbols.get_frozen_action(frozen_production)
                if action is not None:
                    transformer = self.transformers[action]
                    node = transformer.transform(self.get_item_span(items), items)
                else:
                    node = self.create_default_node(items)

                current_state = self.current_state()

                frozen_lhs = frozen_production.get_lhs()
                next_state = self.table.get_goto(current_state, frozen_lhs)
                if next_state is None:
                    nonterminal_name = 'unknown'
                    for name, nonterminal in self.table.frozen_symbols.frozen_nonterminals.items():
                        if nonterminal.id == production_id:
                            nonterminal_name = name

                    raise ParserAutomatonError(
                        f'Automaton found no GOTO for {nonterminal_name} in {current_state}'
                    )

                self.stack.append((node, next_state))

            case ActionKind.ACCEPT:
                items = self.pop_stack(len(self.stack) - 1)
                return self.create_default_node(items)

            case ActionKind.REJECT:
                token = self.table.frozen_symbols.terminals[terminal_symbol.id]
                raise TokenRejectedError(
                    f'Automaton encountered a rejected token {token!r}'
                )

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
