from __future__ import annotations

import enum
import typing
from collections.abc import Sequence

import attr

from ..syntax.scanner import Scanner
from ..syntax.tokens import Token, StdTokenKind, TokenData
from .exceptions import (
    ParserAutomatonError,
    UnexpectedTokenError,
)
from .frozen import (
    UNSET_ACTION,
    UNSET_GOTO,
    ActionKind,
    FrozenParserTable,
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


class ParserAutomaton[TokenKindT: enum.Enum, KeywordKindT: enum.Enum]:
    # https://www.cs.uaf.edu/~chappell/class/2023_spr/cs331/lect/cs331-20230220-shiftred.pdf
    def __init__(
        self,
        scanner: Scanner[TokenKindT, KeywordKindT],
        table: FrozenParserTable[TokenKindT, KeywordKindT],
        transformers: typing.Iterable[typing.Callable[..., NodeLike]],
        *,
        deadlock_threshold: int = 500,
    ) -> None:
        self.scanner = scanner
        self.table = table
        self.transformers = {
            transformer.__name__: transformer for transformer in transformers
        }
        self.deadlock_threshold = deadlock_threshold

        self.state_stack: list[int] = [0]
        self.item_stack: list[NodeItem[TokenKindT, KeywordKindT]] = [OptionNode(start=0, end=0, item=None)]

        self.transformers["@prepend"] = self.transform_prepend
        self.transformers["@flatten"] = self.transform_flatten
        self.transformers["@sequence"] = self.transform_sequence
        self.transformers["@option"] = self.transform_option

    def create_default_node(
        self,
        span: tuple[int, int],
        items: list[NodeItem[TokenKindT, KeywordKindT]]
    ) -> NodeItem[TokenKindT, KeywordKindT]:
        if len(items) == 1:
            return items[0]

        return Node(start=span[0], end=span[1], items=items)

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
        sequence = SequenceNode(
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
            return OptionNode(start=span[0], end=span[1])

        list_items = list(items)
        return OptionNode(
            start=span[0], end=span[1], item=self.create_default_node(span, list_items)
        )

    def parse(self) -> NodeItem[TokenKindT, KeywordKindT]:
        # Optimizations to avoid attribute lookup in the loop.
        # This makes the parser loop 20-50% faster.
        # There is significant overhead in the scanner.
        tokens = self.scanner.scan()
        tokens_len = len(tokens)
        index = 0

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
        end_stack = [0]
        effective_end = 0

        SHIFT = ActionKind.SHIFT.value
        REDUCE = ActionKind.REDUCE.value
        ACCEPT = ActionKind.ACCEPT.value

        ignore_end = (StdTokenKind.INDENT, StdTokenKind.DEDENT, StdTokenKind.NEWLINE)

        while True:
            if current_token is None:
                current_token = tokens[index]
                current_terminal = terminals[current_token.kind.name]

                if tokens_len > index + 1:
                    index += 1
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
                    current_token.start - 20 : current_token.end + 20
                ]
                raise UnexpectedTokenError(
                    f"Automaton encountered an unexpected token {current_token.kind.name!r} in state #{current_state}. "
                    f"The next token should have been one of the following: {string}. ({source!r})"
                )

            action = (entry & 0xC000) >> 14
            number = entry & 0x3FFF
            if action == SHIFT:
                item_stack.append(current_token)
                state_stack.append(number)
                end_stack.append(effective_end)
                current_token = None

            elif action == REDUCE:
                frozen_production = frozen_symbols.get_frozen_production(number)
                rhs_length = frozen_production.rhs_length
                captured = frozen_production.captured

                items = ()
                if rhs_length:
                    start = item_stack[-rhs_length].start

                    end = start
                    for item in reversed(item_stack):
                        if not isinstance(item, TokenData) or item.kind not in ignore_end:
                            end = item.end
                            break

                    if captured:
                        items = [
                            item_stack[i - rhs_length] for i in range(rhs_length) if i in captured
                        ]

                    del item_stack[-rhs_length:]
                    del state_stack[-rhs_length:]
                else:
                    # Epsilon production... really has no span
                    # Just use the end of the last item so the next reduction has the proper start position
                    start = item_stack[-1].end
                    end = item_stack[-1].end

                action = frozen_symbols.get_frozen_action(frozen_production.id)

                if action is not None:
                    transformer = transformers[action]
                    node = transformer((start, end), *items)
                else:
                    if len(items) == 1:
                        node, = items
                    else:
                        start = item_stack[-1].end
                        node = self.create_default_node((start, end), items)

                current_state = state_stack[-1]
                symbol_id = frozen_production.lhs - terminals_size
                next_state = goto_table[(current_state * nonterminals_size) + symbol_id]
                if next_state == UNSET_GOTO:
                    nonterminal = frozen_symbols.get_frozen_symbol(frozen_production.lhs)
                    raise ParserAutomatonError(f"Automaton found no GOTO for {nonterminal} in {current_state}")

                state_stack.append(next_state - 1)
                item_stack.append(node)

            elif action == ACCEPT:
                index = len(self.item_stack) - 1
                if index:
                    items = item_stack[-index:]
                    del item_stack[-index:]
                    del state_stack[-index:]

                action = frozen_symbols.get_frozen_action(number)
                if action is not None:
                    transformer = transformers[action]
                    return transformer((0, current_token.end), *items)
                else:
                    if len(items) == 1:
                        return items[0]

                    return self.create_default_node((0, current_token.end), items)
