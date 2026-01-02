from __future__ import annotations

import typing
import enum
import logging

from .frozen import FrozenSymbol
from .generator import ActionKind, ParserTable
from ..syntax.scanner import Scanner
from ..syntax.tokens import Token

logger = logging.getLogger(__name__)

TokenKindT = typing.TypeVar('TokenKindT', bound=enum.Enum)
KeywordKindT = typing.TypeVar('KeywordKindT', bound=enum.Enum)

# TODO: Add a way to create an AST using the grammar
# Reimplement parsers with new grammar


class ParserAutomaton(typing.Generic[TokenKindT, KeywordKindT]):
    # https://www.cs.uaf.edu/~chappell/class/2023_spr/cs331/lect/cs331-20230220-shiftred.pdf
    def __init__(
        self,
        scanner: Scanner[TokenKindT, KeywordKindT],
        table: ParserTable[TokenKindT, KeywordKindT],
    ) -> None:
        self.scanner = scanner
        self.table = table

        self.accepted = False
        self.tokens: typing.List[Token[TokenKindT, KeywordKindT]] = []
        self.stack: typing.List[
            typing.Tuple[typing.Optional[FrozenSymbol], int]
        ] = [(None, 0)]

    def current_state(self) -> int:
        return self.stack[-1][1]

    def current_symbol(self) -> FrozenSymbol:
        if self.tokens:
            token = self.tokens[0]
        else:
            token = self.scanner.scan()
            self.tokens.append(token)

        return self.table.frozen_symbols.get_frozen_terminal(token.kind)

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
                frozen_production = self.table.frozen_symbols.frozen_productions[production_id]

                del self.stack[-frozen_production.rhs_length:]
                current_state = self.current_state()
                logger.debug('REDUCE BY %s, STACK STATE: %s', frozen_production.id, current_state)

                frozen_lhs = frozen_production.get_lhs()
                next_state = self.table.get_goto(current_state, frozen_lhs)
                if next_state is None:
                    assert False, f'<Goto table has no entry for ({current_state}, {frozen_production})>'

                logger.debug('GOTO %s', next_state)
                self.stack.append((frozen_lhs, next_state))

            case ActionKind.ACCEPT:
                self.accepted = True

            case ActionKind.REJECT:
                assert False, 'Unused'

    def parse(self) -> None:
        while not self.accepted:
            self.next_action()
