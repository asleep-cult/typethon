from __future__ import annotations

import typing
import enum

from .symbols import TerminalSymbol, NonterminalSymbol, Production
from ..syntax.scanner import Scanner
from ..syntax.tokens import Token

KeywordT = typing.TypeVar('KeywordT', bound=enum.IntEnum)


class ActionKind(enum.IntEnum):
    SHIFT = enum.auto()
    REDUCE = enum.auto()
    ACCEPT = enum.auto()
    REJECT = enum.auto()


class ParserAutomaton(typing.Generic[KeywordT]):
    # https://www.cs.uaf.edu/~chappell/class/2023_spr/cs331/lect/cs331-20230220-shiftred.pdf
    def __init__(
        self,
        scanner: Scanner[KeywordT],
        productions: typing.List[Production],
        action_table: typing.List[typing.Dict[TerminalSymbol, typing.Tuple[ActionKind, int]]],
        goto_table: typing.List[typing.Dict[NonterminalSymbol, int]],
    ) -> None:
        self.scanner = scanner
        self.productions = productions
        self.action_table = action_table
        self.goto_table = goto_table

        self.lookahead: typing.Optional[TerminalSymbol] = None
        self.stack: typing.List[
            typing.Tuple[typing.Union[TerminalSymbol, NonterminalSymbol], int]
        ] = []

    def current_state(self) -> int:
        return self.stack[-1][1]

    def next_terminal_symbol(self) -> TerminalSymbol:        
        token = self.scanner.scan()
        return TerminalSymbol(kind=token.kind)

    def next_action(self) -> None:
        current_state = self.current_state()

        if self.lookahead is not None:
            terminal_symbol = self.lookahead
        else:
            terminal_symbol = self.next_terminal_symbol()

        action, number = self.action_table[current_state][terminal_symbol]

        match action:
            case ActionKind.SHIFT:
                self.lookahead = None
                self.stack.append((terminal_symbol, number))

            case ActionKind.REDUCE:
                production = self.productions[number]

                del self.stack[len(production.rhs):]
                current_state = self.current_state()

                next_state = self.goto_table[current_state][production.lhs]
                self.stack.append((production.lhs, next_state))

            case ActionKind.ACCEPT:
                print('Accepted')

            case ActionKind.REJECT:
                raise ValueError(f'Invalid syntax: {terminal_symbol!r}')
