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


TokenKindT = typing.TypeVar('TokenKindT', bound=enum.Enum)
KeywordKindT = typing.TypeVar('KeywordKindT', bound=enum.Enum)

# TODO: Allow the use of custom nodes instead
# Reimplement parsers with new grammar


@attr.s(kw_only=True, slots=True)
class Leaf(typing.Generic[TokenKindT, KeywordKindT]):
    token: Token[TokenKindT, KeywordKindT] = attr.ib()


NodeItem = typing.Union['Node[TokenKindT, KeywordKindT]', Leaf[TokenKindT, KeywordKindT]]

@attr.s(kw_only=True, slots=True)
class Node(typing.Generic[TokenKindT, KeywordKindT]):
    items: typing.List[NodeItem[TokenKindT, KeywordKindT]] = attr.ib()


# TODO: Add a method for transforming Nodes

class ParserAutomaton(typing.Generic[TokenKindT, KeywordKindT]):
    # https://www.cs.uaf.edu/~chappell/class/2023_spr/cs331/lect/cs331-20230220-shiftred.pdf
    def __init__(
        self,
        scanner: Scanner[TokenKindT, KeywordKindT],
        table: ParserTable[TokenKindT, KeywordKindT],
        *,
        deadlock_threshold: int = 10,
    ) -> None:
        self.scanner = scanner
        self.table = table

        self.accepted = False
        self.deadlock_threshold = deadlock_threshold
        self.tokens: typing.List[Token[TokenKindT, KeywordKindT]] = []
        self.stack: typing.List[
            typing.Tuple[
                # typing.Optional[FrozenSymbol],
                typing.Optional[NodeItem[TokenKindT, KeywordKindT]],  # None for epsilon
                int
            ]
        ] = [(None, 0)]

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

    def create_node(
        self,
        index: int,
        captured: typing.Optional[typing.Tuple[int, ...]] = None,
    ) -> Node[TokenKindT, KeywordKindT]:
        items: typing.List[NodeItem[TokenKindT, KeywordKindT]] = []

        if index:
            for i, (item, _) in enumerate(self.stack[-index:]):
                assert item is not None
                if captured is None or i in captured:
                    items.append(item)

            del self.stack[-index:]

        return Node(items=items)

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
                self.stack.append((Leaf(token=token), next_state))

            case ActionKind.REDUCE:
                production_id = entry[1]
                frozen_production = self.table.frozen_symbols.frozen_productions[production_id]

                node = self.create_node(frozen_production.rhs_length, frozen_production.captured)
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
                return self.create_node(len(self.stack) - 1)

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
