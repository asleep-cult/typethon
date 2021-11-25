from __future__ import annotations

from typing import Callable, Iterable, Union


class EOFType(str):
    def __new__(cls):
        return str.__new__(cls, '\0')

    def __repr__(self):
        return '<EOF>'


EOF = EOFType()


class StringReader:
    def __init__(self, source: str) -> None:
        self.source = source
        self._position = 0

    def at_eof(self) -> bool:
        return self._position >= len(self.source)

    def tell(self) -> int:
        return self._position

    def advance(self, amount: int = 1) -> int:
        if not self.at_eof():
            self._position += amount
        return self._position

    def peek(self, offset: int = 0) -> str:
        try:
            return self.source[self._position + offset]
        except IndexError:
            return EOF

    def skip(self, chars: Iterable[str]) -> int:
        while self.peek() in chars:
            self.advance()

        return self._position

    def skip_to_eof(self) -> int:
        return self.advance(len(self.source) - self.tell())

    def skip_whitespace(self, *, newlines: bool = False) -> int:
        if newlines:
            return self.skip((' ', '\t', '\n', '\r', '\f'))
        else:
            return self.skip((' ', '\t', '\f'))

    def skip_expect(self, strings: Union[str, Iterable[str]]) -> bool:
        if isinstance(strings, str):
            strings = (strings,)

        for string in strings:
            index = self.source.find(string, self._position)
            if index != -1:
                self._position = index + len(string)
                return True

        return False

    def expect(self, chars: Iterable[str], times: int = 1) -> bool:
        for i in range(times):
            if self.peek(i) not in chars:
                return False

        self.advance(times)
        return True

    def accumulate(self, func: Callable[[str], bool]) -> str:
        startpos = self.tell()
        while func(self.peek()):
            self.advance()

        endpos = self.tell()
        return self.source[startpos:endpos]

    @staticmethod
    def is_whitespace(char: str) -> bool:
        return (
            char == ' '
            or char == '\t'
            or char == '\f'
            or char == '\r'
            or char == '\n'
        )

    @staticmethod
    def is_newline(char: str) -> bool:
        return char == '\n'

    @staticmethod
    def is_blank(char: str) -> bool:
        return (
            StringReader.is_comment(char)
            or StringReader.is_escape(char)
            or StringReader.is_newline(char)
        )

    @staticmethod
    def is_identifier_start(char: str) -> bool:
        return (
            'a' <= char <= 'z'
            or 'A' <= char <= 'Z'
            or char == '_'
            or char >= '\x80'
        )

    @staticmethod
    def is_identifier(char: str) -> bool:
        return (
            'a' <= char <= 'z'
            or 'A' <= char <= 'Z'
            or '0' <= char <= '9'
            or char == '_'
            or char >= '\x80'
        )

    @staticmethod
    def is_digit(char: str) -> bool:
        return '0' <= char <= '9'

    @staticmethod
    def is_hexadecimal(char: str) -> bool:
        return (
            'a' <= char <= 'f'
            or 'A' <= char <= 'F'
            or '0' <= char <= '9'
        )

    @staticmethod
    def is_octal(char: str) -> bool:
        return '0' <= char <= '7'

    @staticmethod
    def is_binary(char: str) -> bool:
        return char == '0' or char == '1'

    @staticmethod
    def is_terminator(char: str) -> bool:
        return char == '\'' or char == '\"'

    @staticmethod
    def is_escape(char: str) -> bool:
        return char == '\\'

    @staticmethod
    def is_comment(char: str) -> bool:
        return char == '#'
