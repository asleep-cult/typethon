from typing import Callable, Iterable, Optional, Union

from ..util import singletoniter

EOF = str()


class StringReader:
    __slots__ = ('source', '_position')

    def __init__(self, source: str) -> None:
        self.source = source
        self._position = 0

    def tell(self) -> int:
        return self._position

    def at(self, position: Optional[int] = None) -> str:
        if position is None:
            position = self._position
        try:
            return self.source[position]
        except IndexError:
            return EOF

    def advance(self, by: int = 1) -> int:
        self._position += by
        return self._position

    def skip(self, chars: Iterable[str]) -> None:
        while self.at() in chars:
            self.advance()

    def skipws(self, *, newlines: bool = False) -> None:
        if newlines:
            self.skip((' ', '\t', '\f', '\n', '\r'))
        else:
            self.skip((' ', '\t', '\f'))

    def skipspaces(self):
        self.skip((' ', '\t'))

    def skipuntil(self, chars: Iterable[str]) -> None:
        while self.at() in chars:
            self.advance()

    def skipfind(self, strings: Union[str, Iterable[str]]) -> bool:
        if isinstance(strings, str):
            strings = singletoniter(strings)

        for string in strings:
            index = self.source.find(string, self._position)
            if index != -1:
                self._position = index + len(string)
                return True

        return False

    def expect(self, chars: Iterable[str]) -> bool:
        try:
            return self.at() in chars
        finally:
            self.advance()

    def peek(self, offset: int) -> str:
        return self.at(self._position + offset)

    def next(self) -> str:
        try:
            return self.at()
        finally:
            self.advance()

    def accumulate(self, func: Callable[[str], bool]) -> str:
        string = ''
        while True:
            char = self.at()
            if func(char):
                string += char
                self.advance()
            else:
                return string
