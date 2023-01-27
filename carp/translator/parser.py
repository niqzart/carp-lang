from typing import Iterator

from pydantic import BaseModel


class Symbol(BaseModel):
    """
    Simple model to describe a 'symbol'. Symbols can be represented as
    either space-less strings or quoted sequences of any characters.

    Symbol's position is also contained in this model
    (see :py:attr:`line` and :py:attr:`char` for line and column numbers)
    """

    text: str
    line: int
    char: int

    @property
    def is_expression(self) -> bool:
        return self.text.startswith("(")

    @property
    def is_quoted(self) -> bool:
        return self.text.startswith('"')

    @property
    def is_closing(self) -> bool:
        return self.text == ")"

    def __str__(self) -> str:
        return self.text


class ParserError(Exception):
    def __init__(self, text: str):
        self.text: str = text

    def __str__(self) -> str:
        return f"Parsing error occurred: {self.text}"


class Parser:
    """
    Class to parse a string, containing the source code, into a
    list of :py:class:`Symbol`. Used in :py:class:`translator.reader.Reader`
    """

    def __init__(self, data: str):
        self.data: str = data
        self.result: list[Symbol] = []

        self.position: int = 0
        self.line_number: int = 1
        self.char_number: int = 0

        self.started_position: int | None = None
        self.started_line_number: int = 0
        self.started_char_number: int = 0

        self.in_quotes: bool = False
        self.back_brackets: int = 0

        self.parse_all()

    def iterate_chars(self) -> Iterator[str]:
        for self.position, char in enumerate(self.data):
            if not self.in_quotes:
                if char == ")":
                    self.back_brackets += 1
                yield char
            self.in_quotes = self.in_quotes != (char == '"')

            self.char_number += 1
            if char == "\n":
                self.line_number += 1
                self.char_number = 0

        self.position += 1
        if self.in_quotes:
            raise ParserError("Missing closing quotation mark")

    def end_symbol(self) -> None:
        symbol: Symbol = Symbol(
            text=self.data[self.started_position:self.position].strip(")"),
            line=self.started_line_number,
            char=self.started_char_number,
        )
        if symbol.text != "":
            self.result.append(symbol)

    def save_brackets(self) -> None:
        if self.back_brackets:
            self.result.extend(
                Symbol(text=")", line=self.line_number, char=self.char_number - i + 1)
                for i in range(self.back_brackets, 0, -1)
            )
            self.back_brackets = 0

    def parse_all(self) -> None:
        in_spaces: bool
        prev_in_spaces: bool = True

        for char in self.iterate_chars():
            in_spaces = char in [" ", "\n", "\t"]
            if prev_in_spaces and not in_spaces:
                self.started_position = self.position
                self.started_line_number = self.line_number
                self.started_char_number = self.char_number
            elif in_spaces and not prev_in_spaces:
                self.end_symbol()
                self.save_brackets()
            prev_in_spaces = in_spaces

        if not prev_in_spaces:
            self.end_symbol()
        self.save_brackets()
