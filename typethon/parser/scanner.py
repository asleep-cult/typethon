import typing

from ..tokens import (
    DirectiveToken,
    Token,
    TokenType,
    IndentToken,
    DedentToken,
    IdentifierToken,
    StringToken,
    StringTokenFlags,
    NumberToken,
    NumberTokenFlags,
)

EOF = '\0'
TABSIZE = 8
ALTTABSIZE = 1


def is_whitespace(char: str) -> bool:
    return char in ' \t\f\r'


def is_indent(char: str) -> bool:
    return char in ' \t'


def is_blank(char: str) -> bool:
    return char == '#' or char == '\\' or char == '\n'


def is_identifier_start(char: str) -> bool:
    return (
        'a' <= char <= 'z'
        or 'A' <= char <= 'Z'
        or char == '_'
        or char >= '\x80'
    )


def is_identifier(char: str) -> bool:
    return (
        'a' <= char <= 'z'
        or 'A' <= char <= 'Z'
        or '0' <= char <= '9'
        or char == '_'
        or char >= '\x80'
    )


def is_digit(char: str) -> bool:
    return '0' <= char <= '9'


def is_hexadecimal(char: str) -> bool:
    return (
        'a' <= char <= 'f'
        or 'A' <= char <= 'F'
        or '0' <= char <= '9'
    )


def is_octal(char: str) -> bool:
    return '0' <= char <= '7'


def is_binary(char: str) -> bool:
    return char in '01'


class Scanner:
    def __init__(self, source: str) -> None:
        self.source = source
        self.position = 0

        self.is_newline = False
        self.parenstack: typing.List[TokenType] = []
        self.indentstack: typing.List[typing.Tuple[int, int]] = [(0, 0)]
        self.indents: typing.List[typing.Union[IndentToken, DedentToken]] = []

    def is_eof(self) -> bool:
        return self.position >= len(self.source)

    def char_at(self, index: int) -> str:
        if index >= len(self.source):
            return EOF

        return self.source[index]

    def peek_char(self, skip: int = 0) -> str:
        return self.char_at(self.position + skip)

    def consume_char(self, skip: int = 1) -> str:
        char = self.char_at(self.position)

        if not self.is_eof():
            self.position += skip

        return char

    def consume_while(self, predicate: typing.Callable[[str], bool]) -> bool:
        start = self.position

        while not self.is_eof() and predicate(self.peek_char()):
            self.consume_char()

        return self.position != start

    def string_prefix_flag(self, char: str) -> typing.Optional[StringTokenFlags]:
        if char == 'r':
            return StringTokenFlags.RAW
        elif char == 'b':
            return StringTokenFlags.BYTES
        elif char == 'f':
            return StringTokenFlags.FORMAT

    def string_terminated(self, terminator: str, multiline: bool) -> bool:
        if not multiline:
            return self.consume_char() == terminator

        char = self.consume_char()
        assert char == terminator

        if self.peek_char() == self.peek_char(1) == terminator:
            self.consume_char(2)
            return True

        return False

    def scan_indentation(self) -> None:
        start = self.position

        indent = 0
        altindent = 0

        while is_indent(self.peek_char()):
            char = self.consume_char()

            if char == ' ':
                indent += 1
                altindent += 1
            elif char == '\t':
                indent += ((indent // TABSIZE) + 1) * TABSIZE
                altindent += ((indent // ALTTABSIZE) + 1) * ALTTABSIZE

        if is_blank(self.peek_char()):
            return

        last_indent, last_altindent = self.indentstack[-1]

        if indent == last_indent:
            if altindent != last_altindent:
                self.indents.append(
                    IndentToken(start=start, end=self.position, inconsistent=True)
                )
        elif indent > last_indent:
            if altindent <= last_altindent:
                self.indents.append(
                    IndentToken(start=start, end=self.position, inconsistent=True)
                )
            else:
                self.indents.append(IndentToken(start=start, end=self.position))

            self.indentstack.append((indent, altindent))
        else:
            while indent < self.indentstack[-2][0]:
                self.indentstack.pop()
                self.indents.append(DedentToken(start=start, end=self.position))

            self.indentstack.pop()
            last_indent, last_altindent = self.indentstack[-1]

            if indent == last_indent:
                if altindent != last_altindent:
                    self.indents.append(
                        DedentToken(start=start, end=self.position, inconsistent=True)
                    )
                else:
                    self.indents.append(DedentToken(start=start, end=self.position))
            else:
                inconsistent = indent == last_indent and altindent != last_altindent
                self.indents.append(
                    DedentToken(
                        start=start, end=self.position, inconsistent=inconsistent, diverges=True
                    )
                )

        self.is_newline = False

    def identifier_or_string(self) -> Token:
        start = self.position

        char = self.consume_char()
        assert is_identifier_start(char)

        self.consume_while(is_identifier)
        content = self.source[start:self.position]

        if self.peek_char() in '\'\"':
            flags = StringTokenFlags.NONE

            for char in content.lower():
                flag = self.string_prefix_flag(char)
                if flag is None:
                    return IdentifierToken(start=start, end=self.position, content=content)

                if flags & flag:
                    flags |= StringTokenFlags.DUPLICATE_PREFIX

                flags |= flag

            return self.string(flags=flags)

        token = IdentifierToken(start=start, end=self.position, content=content)

        type = token.get_keyword()
        if type is not None:
            token = Token(type=type, start=start, end=self.position)

        return token

    def scan_number(self, predicate: typing.Callable[[str], bool]) -> NumberTokenFlags:
        flags = NumberTokenFlags.NONE

        while predicate(self.peek_char()) or self.peek_char() == '_':
            char = self.consume_char()

            if char == '_' and self.peek_char() == '_':
                self.consume_char()
                flags |= NumberTokenFlags.CONSECUTIVE_UNDERSCORES

        if self.peek_char(-1) == '_':
            flags |= NumberTokenFlags.TRAILING_UNDERSCORE

        return flags

    def number(self) -> NumberToken:
        start = self.position

        char = self.peek_char()
        assert char == '.' or is_digit(char)

        flags = NumberTokenFlags.NONE

        if char == '0':
            self.consume_char()
            char = self.peek_char()

            if char in 'Xx':
                self.consume_char()
                flags |= NumberTokenFlags.HEXADECIMAL | self.scan_number(is_hexadecimal)

            elif char in 'Oo':
                self.consume_char()
                flags |= NumberTokenFlags.OCTAL | self.scan_number(is_octal)

            elif char in 'Bb':
                self.consume_char()
                flags |= NumberTokenFlags.BINARY | self.scan_number(is_binary)

            if flags != NumberTokenFlags.NONE:
                if self.position <= start + 2:
                    flags |= NumberTokenFlags.EMPTY

                content = self.source[start:self.position]
                return NumberToken(start=start, end=self.position, content=content, flags=flags)

        flags |= self.scan_number(is_digit)

        content = self.source[start:self.position]
        if char == '0' and content.count('0') != len(content):
            flags |= NumberTokenFlags.LEADING_ZERO

        if self.peek_char() == '.':
            self.consume_char()
            flags |= NumberTokenFlags.FLOAT | self.scan_number(is_digit)

        if self.peek_char() in 'Ee':
            self.consume_char()

            if self.peek_char() in '+-':
                self.consume_char()

            if not is_digit(self.peek_char()):
                flags |= NumberTokenFlags.INVALID_EXPONENT

            flags |= NumberTokenFlags.FLOAT | self.scan_number(is_digit)

        if self.peek_char() in 'Jj':
            self.consume_char()
            flags |= NumberTokenFlags.IMAGINARY

        content = self.source[start:self.position]
        return NumberToken(start=start, end=self.position, content=content, flags=flags)

    def newline(self) -> typing.Optional[Token]:
        start = self.position

        char = self.consume_char()
        assert char == '\n'

        if self.is_newline:
            return None

        self.is_newline = True
        return Token(type=TokenType.NEWLINE, start=start, end=self.position)

    def string(self, *, flags: StringTokenFlags = StringTokenFlags.NONE) -> StringToken:
        start = self.position

        terminator = self.consume_char()
        multiline = False
        assert terminator in '\'\"'

        if self.peek_char() == terminator:
            self.consume_char()

            if self.peek_char() == terminator:
                self.consume_char()
                multiline = True
            else:
                return StringToken(start=start, end=self.position, content='', flags=flags)

        terminator_size = 3 if multiline else 1

        while flags & StringTokenFlags.UNTERMINATED == 0:
            char = self.peek_char()

            if char == terminator:
                if self.string_terminated(terminator, multiline):
                    content = self.source[start + terminator_size:self.position - terminator_size]
                    return StringToken(start=start, end=self.position, content=content, flags=flags)

            elif char == '\\':
                self.consume_char()

            elif char == EOF or char == '\n' and not multiline:
                flags |= StringTokenFlags.UNTERMINATED

            self.consume_char()

        content = self.source[start + terminator_size:]
        return StringToken(start=start, end=self.position, content=content, flags=flags)

    def comment(self) -> typing.Optional[DirectiveToken]:
        start = self.position

        char = self.consume_char()
        assert char == '#'

        self.consume_while(lambda char: char != '\n')
        comment = self.source[start + 1:self.position]

        directive_start = comment.find('[')
        directive_end = comment.find(']')

        if directive_start != 0 or directive_end == -1:
            return None

        content = comment[directive_start + 1:directive_end]
        return DirectiveToken(start=start, end=self.position, content=content)

    def token(self) -> TokenType:
        char = self.consume_char()

        if char == '(':
            self.parenstack.append(TokenType.OPENPAREN)
            return TokenType.OPENPAREN

        elif char == ')':
            if not self.parenstack or self.parenstack.pop() is not TokenType.OPENPAREN:
                return TokenType.EUNMATCHED

            return TokenType.CLOSEPAREN

        elif char == '[':
            self.parenstack.append(TokenType.OPENBRACKET)
            return TokenType.OPENBRACKET

        elif char == ']':
            if not self.parenstack or self.parenstack.pop() is not TokenType.OPENBRACKET:
                return TokenType.EUNMATCHED

            return TokenType.CLOSEBRACKET

        elif char == '{':
            self.parenstack.append(TokenType.OPENBRACE)
            return TokenType.OPENBRACE

        elif char == '}':
            if not self.parenstack or self.parenstack.pop() is not TokenType.OPENBRACE:
                return TokenType.EUNMATCHED

            return TokenType.CLOSEBRACE

        elif char == ':':
            if self.peek_char() == '=':
                self.consume_char()
                return TokenType.COLONEQUAL

            return TokenType.COLON

        elif char == ',':
            return TokenType.COMMA

        elif char == ';':
            return TokenType.SEMICOLON

        elif char == '.':
            if self.peek_char() == '.':
                self.consume_char()

                if self.peek_char() == '.':
                    self.consume_char()
                    return TokenType.ELLIPSIS

            return TokenType.DOT

        elif char == '+':
            if self.peek_char() == '=':
                self.consume_char()
                return TokenType.PLUSEQUAL

            return TokenType.PLUS

        elif char == '-':
            if self.peek_char() == '=':
                self.consume_char()
                return TokenType.MINUSEQUAL

            elif self.peek_char() == '>':
                self.consume_char()
                return TokenType.RARROW

            return TokenType.MINUS

        elif char == '*':
            if self.peek_char() == '*':
                self.consume_char()

                if self.peek_char() == '=':
                    self.consume_char()
                    return TokenType.DOUBLESTAREQUAL

                return TokenType.DOUBLESTAR

            elif self.peek_char() == '=':
                self.consume_char()
                return TokenType.STAREQUAL

            return TokenType.STAR

        elif char == '@':
            if self.peek_char() == '=':
                self.consume_char()
                return TokenType.ATEQUAL

            return TokenType.AT

        elif char == '/':
            if self.peek_char() == '/':
                self.consume_char()

                if self.peek_char() == '=':
                    self.consume_char()
                    return TokenType.DOUBLESLASHEQUAL

                return TokenType.DOUBLESLASH

            elif self.peek_char() == '=':
                self.consume_char()
                return TokenType.SLASHEQUAL

            return TokenType.SLASH

        elif char == '|':
            if self.peek_char() == '=':
                self.consume_char()
                return TokenType.VERTICALBAREQUAL

            return TokenType.VERTICALBAR

        elif char == '&':
            if self.peek_char() == '=':
                self.consume_char()
                return TokenType.AMPERSANDEQUAL

            return TokenType.AMPERSAND

        elif char == '<':
            if self.peek_char() == '<':
                self.consume_char()

                if self.peek_char() == '=':
                    self.consume_char()
                    return TokenType.DOUBLELTHANEQUAL

                return TokenType.DOUBLELTHAN

            elif self.peek_char() == '=':
                self.consume_char()
                return TokenType.LTHANEQ

            return TokenType.LTHAN

        elif char == '>':
            if self.peek_char() == '>':
                self.consume_char()

                if self.consume_char() == '=':
                    self.consume_char()
                    return TokenType.DOUBLEGTHANEQUAL

                return TokenType.DOUBLEGTHAN

            elif self.peek_char() == '=':
                self.consume_char()
                return TokenType.GTHANEQ

            return TokenType.GTHAN

        elif char == '=':
            if self.peek_char() == '=':
                self.consume_char()
                return TokenType.EQEQUAL

            return TokenType.EQUAL

        elif char == '!':
            if self.peek_char() == '=':
                self.consume_char()
                return TokenType.NOTEQUAL

        elif char == '%':
            if self.peek_char() == '=':
                self.consume_char()
                return TokenType.PERCENTEQUAL

            return TokenType.PERCENT

        elif char == '~':
            return TokenType.TILDE

        elif char == '^':
            if self.peek_char() == '=':
                self.consume_char()
                return TokenType.CIRCUMFLEXEQUAL

            return TokenType.CIRCUMFLEX

        return TokenType.EINVALID

    def scan(self) -> Token:
        while True:
            if self.is_newline:
                self.scan_indentation()

            if self.indents:
                return self.indents.pop(0)

            self.consume_while(is_whitespace)

            if self.is_eof():
                return Token(type=TokenType.EOF, start=self.position, end=self.position)

            start = self.position
            char = self.peek_char()

            if is_identifier_start(char):
                return self.identifier_or_string()

            elif is_digit(char):
                return self.number()

            elif char in '\'\"':
                return self.string()

            elif char == '\n':
                token = self.newline()
                if token is None:
                    continue

                return token

            elif char == '#':
                token = self.comment()
                if token is None:
                    continue

                return token

            elif char == '.':
                char = self.peek_char(1)
                if is_digit(char):
                    return self.number()

            type = self.token()
            if type is TokenType.EINVALID:
                self.consume_while(lambda char: not is_whitespace(char))

            return Token(type=type, start=start, end=self.position)
