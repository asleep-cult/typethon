
import re
import enum
import typing

from .tokens import (
    DedentToken,
    DirectiveToken,
    IdentifierToken,
    IndentToken,
    KeywordMap,
    NumberToken,
    NumberTokenFlags,
    StdTokenKind,
    StringToken,
    StringTokenFlags,
    Token,
    TokenData,
    TokenMap,
)

__all__ = ("Scanner",)

type TokenLookupTable[TokenKindT: enum.Enum] = dict[
    str, tuple[TokenLookupTable[TokenKindT], TokenKindT | None]
]

EOF = "\0"
TABSIZE = 8
ALTTABSIZE = 1


def is_whitespace(char: str) -> bool:
    return char in " \t\f\r"


def is_indent(char: str) -> bool:
    return char in " \t"


def is_blank(char: str) -> bool:
    return char == "#" or char == "\\" or char == "\n"


def is_identifier_start(char: str) -> bool:
    return "a" <= char <= "z" or "A" <= char <= "Z" or char == "_" or char >= "\x80"


def is_identifier(char: str) -> bool:
    return (
        "a" <= char <= "z"
        or "A" <= char <= "Z"
        or "0" <= char <= "9"
        or char == "_"
        or char >= "\x80"
    )


def is_digit(char: str) -> bool:
    return "0" <= char <= "9"


def is_hexadecimal(char: str) -> bool:
    return "a" <= char <= "f" or "A" <= char <= "F" or "0" <= char <= "9"


def is_octal(char: str) -> bool:
    return "0" <= char <= "7"


def is_binary(char: str) -> bool:
    return char in "01"


class Scanner[TokenKindT: enum.Enum, KeywordKindT: enum.Enum]:
    def __init__(
        self,
        source: str,
        *,
        tokens: TokenMap[TokenKindT],
        keywords: KeywordMap[KeywordKindT],
        matched_tokens: dict[TokenKindT, TokenKindT],
    ) -> None:
        self.source = source
        self.scanned = False

        self.token_map = dict(tokens)
        self.keywords = dict(keywords)

        self.matched_tokens = matched_tokens
        self.matched_tokens_inverse: dict[TokenKindT, TokenKindT] = {}
        for opening_token, closing_token in matched_tokens.items():
            self.matched_tokens_inverse[closing_token] = opening_token

        self.is_newline = False
        self.match_stack: list[TokenKindT] = []
        self.indent_stack: list[tuple[int, int]] = [(0, 0)]
        self.tokens: list[Token[TokenKindT, KeywordKindT]] = []

        self.match_stack_bottom = 0
        self.indentation_nesting_stack: list[tuple[int, tuple[int, int]]] = []

    def is_match_stack_effectively_empty(self) -> bool:
        return len(self.match_stack) - self.match_stack_bottom <= 0

    def start_nested_indentation(self) -> None:
        self.indentation_nesting_stack.append(
            (self.match_stack_bottom, self.indent_stack[-1])
        )
        self.match_stack_bottom = len(self.match_stack)

    def stop_nested_indentation(self) -> None:
        self.match_stack_bottom, _ = self.indentation_nesting_stack.pop()

    def string_prefix_flag(self, char: str) -> StringTokenFlags | None:
        if char == "r":
            return StringTokenFlags.RAW
        elif char == "b":
            return StringTokenFlags.BYTES
        elif char == "f":
            return StringTokenFlags.FORMAT

    def add_pending_indentation(self, start: int, position: int, indent: int, altindent: int) -> None:
        last_indent, last_altindent = self.indent_stack[-1]

        if indent == last_indent:
            if altindent != last_altindent:
                self.tokens.append(
                    IndentToken(start=start, end=position, inconsistent=True)
                )
        elif indent > last_indent:
            if altindent <= last_altindent:
                self.tokens.append(
                    IndentToken(start=start, end=position, inconsistent=True)
                )
            else:
                self.tokens.append(IndentToken(start=start, end=position))

            self.indent_stack.append((indent, altindent))
        else:
            while indent < self.indent_stack[-2][0]:
                self.indent_stack.pop()
                self.tokens.append(DedentToken(start=start, end=position))

            self.indent_stack.pop()
            last_indent, last_altindent = self.indent_stack[-1]

            if indent == last_indent:
                if altindent != last_altindent:
                    self.tokens.append(
                        DedentToken(start=start, end=position, inconsistent=True)
                    )
                else:
                    self.tokens.append(
                        DedentToken(start=start, end=position)
                    )
            else:
                inconsistent = indent == last_indent and altindent != last_altindent
                self.tokens.append(
                    DedentToken(
                        start=start,
                        end=position,
                        inconsistent=inconsistent,
                        diverges=True,
                    )
                )

        self.is_newline = False        

    def newline(self, position: int) -> None:
        if self.is_newline or not self.is_match_stack_effectively_empty():
            return

        self.is_newline = True
        token = TokenData(kind=StdTokenKind.NEWLINE, start=position - 1, end=position)
        self.tokens.append(token)

    def string(self, position: int, source: str, *, flags: StringTokenFlags = StringTokenFlags.NONE) -> int:
        start = position - 1
        source_len = len(source)

        multiline = False
        if source_len > position and source[position] == "\"":
            position += 1

            if source_len > position and source[position] == "\"":
                position += 1
                multiline = True
            else:
                token = StringToken(start=start, end=position, content="", flags=flags)
                self.tokens.append(token)

        if multiline:
            end = source.find("\"\"\"", position)
            # XXX: COULD BE ESCAPED
            if end == -1:
                flags |= StringTokenFlags.UNTERMINATED
                content = source[start + 3:]
                end = source_len
            else:
                content = source[start + 3 : end]
                end = end + 3

            token = StringToken(start=start, end=end, content=content, flags=flags)
            self.tokens.append(token)
            return end
        else:
            end = source.find("\"", position)
            if end == -1:
                flags |= StringTokenFlags.UNTERMINATED
                end = source.find("\n")

            if end == -1:
                content = source[start + 1:]
                end = source_len
            else:
                content = source[start + 1 : end]
                end = end + 1

            token = StringToken(start=start, end=end, content=content, flags=flags)
            self.tokens.append(token)
            return end        

    def scan_source(self) -> list[Token[TokenKindT, KeywordKindT]]:
        self.scanned = True
        token_group = "|".join(re.escape(token) for token in self.token_map)

        if "'" in self.token_map:
            string_group = "\""
        else:
            string_group = "'|\""

        base_re = (
            "(?P<identifier>[a-zA-Z_][a-zA-Z0-9_]*)"
            "|(?P<hexadecimal>0x|X[0-9_]+)"
            "|(?P<binary>0b|B[0-9_]+)"
            "|(?P<octal>0o|O[0-7_]+)"
            "|(?P<float>[0-9][0-9_]*\\.[0-9_]+)"
            "|(?P<integer>[0-9][0-9_]*+)"
            "|(?P<newline>\n)"
            "|(?P<comment>#)"
            "|(?P<escape>\\\\)"
            f"|(?P<string>{string_group})"
            f"|(?P<token>{token_group})"
        )
        indent_re = re.compile(base_re + "|(?P<indent>[\t ]+)")
        normal_re = re.compile(base_re + "|(?P<whitespace>[ \t\f\r]+)")

        position = 0
        source = self.source
        source_len = len(source)
        tokens = self.tokens

        while True:
            start = position
            if self.is_newline:
                active_pattern = indent_re
            else:
                active_pattern = normal_re

            result = active_pattern.match(source, position)
            if self.is_newline:
                if result is not None:
                    position = result.end()
                    matched_indentation = result.lastgroup == "indent"
                    found_blank = result.lastgroup in ("newline", "comment", "escape")
                    # ^^ Fallthrough to match result.lastgroup
                else:
                    matched_indentation = False
                    found_blank = False

                if not found_blank and position < source_len and is_blank(source[position]):
                    # Here it must have matched the indent but the next character is blank anyways
                    found_blank = True

                if not found_blank:
                    if result is not None and matched_indentation:
                        position = result.end()

                        content = result.group()
                        indent = content.count(" ")
                        altindent = indent

                        tab_count = content.count("\t")
                        if tab_count:
                            indent = ((indent + TABSIZE) // TABSIZE) * TABSIZE
                            indent += (tab_count - 1) * TABSIZE

                            altindent = ((indent + ALTTABSIZE) // ALTTABSIZE) * ALTTABSIZE
                            altindent += (tab_count - 1) * ALTTABSIZE
                    else:
                        indent = 0
                        altindent = 0
                        # Fallthrough to match result.lastgroup

                    self.add_pending_indentation(start, position, indent, altindent)
                    if matched_indentation:
                        continue

            if position >= source_len:
                token = TokenData(kind=StdTokenKind.EOF, start=position, end=position)
                tokens.append(token)
                return tokens

            assert result is not None

            content = result.group()
            position = result.end()
            match result.lastgroup:
                case "identifier":
                    keyword = self.keywords.get(content)
                    if keyword is not None:
                        token = TokenData(kind=keyword, start=start, end=position)
                    else:
                        token = IdentifierToken(start=start, end=position, content=content)

                    tokens.append(token)

                case "hexadecimal":
                    token = NumberToken(start=start, end=position, content=content, flags=NumberTokenFlags.HEXADECIMAL)
                    tokens.append(token)

                case "binary":
                    token = NumberToken(start=start, end=position, content=content, flags=NumberTokenFlags.BINARY)
                    tokens.append(token)

                case "octal":
                    token = NumberToken(start=start, end=position, content=content, flags=NumberTokenFlags.OCTAL)
                    tokens.append(token)

                case "float":
                    token = NumberToken(start=start, end=position, content=content, flags=NumberTokenFlags.FLOAT)
                    tokens.append(token)

                case "integer":
                    token = NumberToken(start=start, end=position, content=content, flags=NumberTokenFlags.INTEGER)
                    tokens.append(token)

                case "token":
                    if content == "'":
                        end = position
                        flags = StringTokenFlags.CHARACTER
                        source_len = len(source)

                        if source_len > position and source[position] == "'":
                            end = position + 1
                            token = StringToken(start=position, end=end, content="", flags=flags)
                            self.tokens.append(token)
                            position = end
                            continue

                        # XXX: COULD BE AN ESCAPED CHARACTER
                        elif source_len >= position + 1 and source[position + 1] == "'":
                            end = position + 2
                            token = StringToken(
                                start=position, end=end, content=source[position], flags=flags
                            )
                            self.tokens.append(token)
                            position = end
                            continue

                    token_kind = self.token_map[content]

                    if token_kind in self.matched_tokens:
                        self.match_stack.append(token_kind)
                    elif token_kind in self.matched_tokens_inverse:
                        if (
                            self.is_match_stack_effectively_empty()
                            and self.indentation_nesting_stack
                        ):
                            self.tokens.append(
                                TokenData(kind=StdTokenKind.NEWLINE, start=0, end=0)
                            )

                            indent, altindent = self.indentation_nesting_stack[-1][1]
                            self.add_pending_indentation(position, position, indent, altindent)

                        if not self.match_stack:
                            token_kind = StdTokenKind.EUNMATCHED
                        else:
                            opening_token = self.match_stack[-1]
                            if opening_token is not self.matched_tokens_inverse[token_kind]:
                                token_kind = StdTokenKind.EUNMATCHED

                            del self.match_stack[-1]

                    token = TokenData(kind=token_kind, start=start, end=position)
                    tokens.append(token)

                case "newline":
                    self.newline(position)

                case "comment":
                    end = source.find("\n", position)
                    if end == -1:
                        end = len(source)

                    comment = self.source[position + 1 : end]

                    directive_start = comment.find("[")
                    directive_end = comment.find("]")

                    if directive_start == 0 and directive_end == -1:
                        content = comment[directive_start + 1 : directive_end]
                        self.tokens.append(DirectiveToken(start=position, end=end, content=content))

                    position = end + 1

                case "string":
                    position = self.string(position, source)

    def scan(self) -> Token[TokenKindT, KeywordKindT]:
        if not self.scanned:
            self.scan_source()

        if self.tokens:
            return self.tokens.pop(0)

        return TokenData(kind=StdTokenKind.EOF, start=0, end=0)
