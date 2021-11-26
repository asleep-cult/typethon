from __future__ import annotations


class TextRange:
    __slots__ = ('startpos', 'endpos', 'startlineno', 'endlineno')

    def __init__(self, startpos: int, endpos: int, startlineno: int, endlineno: int) -> None:
        self.startpos = startpos
        self.endpos = endpos
        self.startlineno = startlineno
        self.endlineno = endlineno

    def __eq__(self, other) -> bool:
        if not isinstance(other, TextRange):
            return NotImplemented

        return (
            self.startpos == other.startpos
            and self.endpos == other.endpos
            and self.startlineno == other.endlineno
            and self.endlineno == other.endlineno
        )

    def __repr__(self):
        if self.startlineno == self.endlineno:
            return f'{self.startlineno}:{self.startpos}:{self.endpos}'
        else:
            return f'{self.startlineno}-{self.endpos}:{self.startpos}:{self.endpos}'

    def extend(self, range: TextRange) -> None:
        self.startpos = min(self.startpos, range.startpos)
        self.startlineno = min(self.startlineno, range.startlineno)

        self.endpos = max(self.startpos, range.endpos)
        self.endlineno = max(self.endlineno, range.endlineno)

    def copy(self) -> TextRange:
        return TextRange(self.startpos, self.endpos, self.startlineno, self.endlineno)
