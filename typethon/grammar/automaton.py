from __future__ import annotations

import enum
import typing
from collections.abc import Sequence
from types import FunctionType

import attr

from ..syntax.scanner import Scanner
from ..syntax.tokens import Token
from .exceptions import (
    DeadlockError,
    ParserAutomatonError,
    StackUnderflowError,
    UnexpectedTokenError,
)
from .frozen import (
    UNSET_ACTION,
    UNSET_GOTO,
    ActionKind,
    FrozenParserTable,
    FrozenSymbol,
    InternedFrozenSymbol,
)


class NodeLike(typing.Protocol):
    @property
    def start(self) -> int: ...

    @property
    def end(self) -> int: ...


@attr.s(kw_only=True, slots=True)
class Node[TokenKindT: enum.Enum, KeywordKindT: enum.Enum]:
    start: int = attr.ib()
    end: int = attr.ib()
    items: list[NodeItem[TokenKindT, KeywordKindT]] = attr.ib()


@attr.s(kw_only=True, slots=True)
class SequenceNode[NodeT]:
    start: int = attr.ib()
    end: int = attr.ib()
    items: list[NodeT] = attr.ib()


@attr.s(kw_only=True, slots=True)
class OptionNode[NodeT]:
    start: int = attr.ib()
    end: int = attr.ib()
    item: NodeT | None = attr.ib(default=None)

    def map[T](self, fn: typing.Callable[[NodeT], T]) -> T | None:
        if self.item is not None:
            return fn(self.item)

    def sequence[ItemT](self: OptionNode[SequenceNode[ItemT]]) -> SequenceNode[ItemT]:
        # get the flattened node or create an empty one
        if self.item is None:
            return SequenceNode(start=self.start, end=self.end, items=[])

        assert isinstance(self.item, SequenceNode)
        return self.item


type NodeItem[TokenKindT: enum.Enum, KeywordKindT: enum.Enum] = (
    NodeLike
    | SequenceNode[NodeItem[TokenKindT, KeywordKindT]]
    | OptionNode[NodeItem[TokenKindT, KeywordKindT]]
    | Token[TokenKindT, KeywordKindT]
)


@attr.s(kw_only=True, slots=True)
class Transformer[TokenKindT: enum.Enum, KeywordKindT: enum.Enum]:
    name: str = attr.ib()
    callback: typing.Callable[..., NodeItem[TokenKindT, KeywordKindT]] = attr.ib()

    @classmethod
    def from_function(
        cls, function: FunctionType[..., NodeItem[TokenKindT, KeywordKindT]]
    ) -> Transformer[TokenKindT, KeywordKindT]:
        return cls(name=function.__name__, callback=function)


class ParserAutomaton[TokenKindT: enum.Enum, KeywordKindT: enum.Enum]:
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
        self.transformers = {
            transformer.name: transformer for transformer in transformers
        }
        self.deadlock_threshold = deadlock_threshold

        self.state_stack: list[int] = [0]
        self.item_stack: list[NodeItem[TokenKindT, KeywordKindT]] = [OptionNode(start=0, end=0, item=None)]

        self.transformers["@prepend"] = Transformer.from_function(
            self.transform_prepend
        )
        self.transformers["@flatten"] = Transformer.from_function(
            self.transform_flatten
        )
        self.transformers["@sequence"] = Transformer.from_function(
            self.transform_sequence
        )
        self.transformers["@option"] = Transformer.from_function(self.transform_option)

    def get_item_span(
        self,
        items: Sequence[NodeItem[TokenKindT, KeywordKindT]],
    ) -> tuple[int, int]:
        if not items:
            return (0, 0)

        return (items[0].start, items[-1].end)

    def create_default_node(
        self, items: list[NodeItem[TokenKindT, KeywordKindT]]
    ) -> NodeItem[TokenKindT, KeywordKindT]:
        if len(items) == 1:
            return items[0]

        start, end = self.get_item_span(items)
        return Node(start=start, end=end, items=items)

    def transform_prepend[ItemT](
        self,
        span: tuple[int, int],
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
        span: tuple[int, int],
        *items: NodeItem[TokenKindT, KeywordKindT],
    ) -> SequenceNode[NodeItem[TokenKindT, KeywordKindT]]:
        sequence = SequenceNode[NodeItem[TokenKindT, KeywordKindT]](
            start=span[0], end=span[1], items=[]
        )
        for item in items:
            self.flatten_recursive(sequence, item)

        return sequence

    def transform_sequence(
        self,
        span: tuple[int, int],
        *items: NodeItem[TokenKindT, KeywordKindT],
    ) -> NodeItem[TokenKindT, KeywordKindT]:
        if not items:
            return SequenceNode[NodeItem[TokenKindT, KeywordKindT]](
                start=span[0], end=span[1], items=[]
            )

        first_item = items[0]
        if not isinstance(first_item, SequenceNode):
            assert len(items) == 1

            first_item = SequenceNode(start=span[0], end=span[1], items=[first_item])

        first_item.items.extend(items[1:])
        first_item.start, first_item.end = span
        return first_item

    def transform_option(
        self,
        span: tuple[int, int],
        *items: NodeItem[TokenKindT, KeywordKindT],
    ) -> NodeItem[TokenKindT, KeywordKindT]:
        if not items:
            return OptionNode(start=-1, end=-1)

        list_items = list(items)
        return OptionNode(
            start=span[0], end=span[1], item=self.create_default_node(list_items)
        )

    def parse(self) -> NodeItem[TokenKindT, KeywordKindT]:
        # Optimizations to avoid attribute lookup in the loop.
        # This makes the parser loop 20-50% faster.
        # There is significant overhead in the scanner.
        scan_fn = self.scanner.scan

        frozen_symbols = self.table.frozen_symbols
        transformers = self.transformers

        state_stack = self.state_stack
        item_stack = self.item_stack

        terminals = frozen_symbols.interned_terminal_lookup
        terminals_size = len(terminals)

        nonterminals = frozen_symbols.interned_nonterminal_lookup
        nonterminals_size = len(nonterminals)

        action_table = self.table.actions
        goto_table = self.table.gotos

        current_token = None
        current_terminal = None

        while True:
            if current_token is None:
                current_token = scan_fn()
                current_terminal = terminals[current_token.kind.name]
            else:
                assert current_terminal is not None

            current_state = state_stack[-1]

            entry = action_table[(current_state * terminals_size) + current_terminal]
            if entry == UNSET_ACTION:
                symbols = [
                    self.table.frozen_symbols.get_frozen_symbol(i)
                    for i, entry in enumerate(self.table.all_actions(current_state))
                    if entry != UNSET_ACTION
                ]
                string = ", ".join(symbols)
                source = self.scanner.source[
                    self.scanner.position - 20 : self.scanner.position + 20
                ]
                raise UnexpectedTokenError(
                    f"Automaton encountered an unexpected token {current_token.kind.name!r} in state #{current_state}. "
                    f"The next token should have been one of the following: {string}. ({source!r})"
                )

            action = (entry & 0xC000) >> 14
            number = entry & 0x3FFF
            match action:
                case ActionKind.SHIFT:
                    item_stack.append(current_token)
                    state_stack.append(number)
                    current_token = None

                case ActionKind.REDUCE:
                    frozen_production = frozen_symbols.get_frozen_production(number)
                    rhs_length = frozen_production.rhs_length
                    captured = frozen_production.captured

                    if rhs_length:
                        items = [
                            item_stack[i - rhs_length] for i in range(rhs_length) if i in captured
                        ]

                        del item_stack[-rhs_length:]
                        del state_stack[-rhs_length:]
                    else:
                        items = ()

                    action = frozen_symbols.get_frozen_action(
                        frozen_production.id
                    )
                    if action is not None:
                        transformer = transformers[action]
                        node = transformer.callback(self.get_item_span(items), *items)
                    else:
                        if len(items) == 1:
                            node, = items
                        else:
                            node = self.create_default_node(items)

                    current_state = state_stack[-1]
                    symbol_id = frozen_production.lhs - terminals_size
                    next_state = goto_table[(current_state * nonterminals_size) + symbol_id]
                    if next_state == UNSET_GOTO:
                        nonterminal = frozen_symbols.get_frozen_symbol(frozen_production.lhs)
                        raise ParserAutomatonError(f"Automaton found no GOTO for {nonterminal} in {current_state}")

                    state_stack.append(next_state - 1)
                    item_stack.append(node)

                case ActionKind.ACCEPT:
                    index = len(self.item_stack) - 1
                    if index:
                        items = item_stack[-index:]
                        del item_stack[-index:]
                        del state_stack[-index:]

                    action = frozen_symbols.get_frozen_action(number)
                    if action is not None:
                        transformer = transformers[action]
                        return transformer.callback(self.get_item_span(items), *items)
                    else:
                        if len(items) == 1:
                            return items[1]

                        return self.create_default_node(items)
