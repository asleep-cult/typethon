from __future__ import annotations

import typing
import enum
import logging

from .generator import ActionKind, ParserTable
from .symbols import (
    TerminalSymbol,
    NonterminalSymbol,
    Production,
    EPSILON,
)
from ..syntax.scanner import Scanner
from ..syntax.tokens import Token, TokenKind

logger = logging.getLogger(__name__)

KeywordT = typing.TypeVar('KeywordT', bound=enum.IntEnum)

# TODO: Add a way to create an AST using the grammar
# Reimplement parsers with new grammar


class ParserAutomaton(typing.Generic[KeywordT]):
    # https://www.cs.uaf.edu/~chappell/class/2023_spr/cs331/lect/cs331-20230220-shiftred.pdf
    def __init__(
        self,
        scanner: Scanner[KeywordT],
        productions: typing.List[Production],
        table: ParserTable,
    ) -> None:
        self.scanner = scanner
        self.productions = productions
        self.table = table

        self.accepted = False
        self.tokens: typing.List[Token[KeywordT]] = []
        self.stack: typing.List[
            typing.Tuple[typing.Union[TerminalSymbol, NonterminalSymbol], int]
        ] = [(EPSILON, 0)]

    def current_state(self) -> int:
        return self.stack[-1][1]

    def current_symbol(self) -> TerminalSymbol:
        if self.tokens:
            token = self.tokens[0]
        else:
            token = self.scanner.scan()
            self.tokens.append(token)

        kind = token.keyword if token.kind is TokenKind.KEYWORD else token.kind
        return TerminalSymbol(kind=kind)

    def advance(self) -> None:
        if not self.tokens:
            assert False, f'<there are no tokens>'

        self.tokens.pop(0)

    def next_action(self) -> None:
        current_state = self.current_state()
        terminal_symbol = self.current_symbol()

        entry = self.table.get_action(current_state, terminal_symbol)
        if entry is None:
            assert False, f'<Action table has no entry for ({current_state, terminal_symbol})>'

        logging.debug('FOUND %s FOR %s, %s', entry, current_state, terminal_symbol)

        action = entry[0]
        match action:
            case ActionKind.SHIFT:
                self.advance()
                next_state = entry[1]
                logger.debug('SHIFT TO %s', next_state)
                self.stack.append((terminal_symbol, next_state))

            case ActionKind.REDUCE:
                production_id = entry[1]
                production = self.productions[production_id]

                del self.stack[-len(production.rhs):]
                current_state = self.current_state()
                logger.debug('REDUCE BY %s, STACK STATE: %s', production, current_state)

                next_state = self.table.get_goto(current_state, production.lhs)
                if next_state is None:
                    assert False, f'<Goto table has no entry for ({current_state}, {production.lhs.name})>'

                logger.debug('GOTO %s', next_state)
                self.stack.append((production.lhs, next_state))

            case ActionKind.ACCEPT:
                self.accepted = True

            case ActionKind.REJECT:
                assert False, 'Unused'

    def parse(self) -> None:
        while not self.accepted:
            self.next_action()
