from common.errors import TranslationError
from translator.parser import Symbol, Parser


class Reader:
    def __init__(self, data: str) -> None:
        self.symbols: list[Symbol] = Parser(data).result
        print(self.symbols)
        self.position: int = 0

    def has_next(self) -> bool:
        return self.position < len(self.symbols)

    def current_or_none(self) -> Symbol | None:
        if self.has_next():
            return self.symbols[self.position]
        return None

    def current_or_closing(self) -> Symbol:
        result = self.current_or_none()
        if result is None:
            raise IndexError
        return result

    def current(self) -> Symbol:
        result = self.current_or_closing()
        if result.is_closing:
            raise TranslationError("Unexpected closing symbol")
        return result

    def next_or_none(self) -> Symbol:
        result = self.current_or_none()
        self.position += 1
        return result

    def next_or_closing(self) -> Symbol:
        result = self.current_or_closing()
        self.position += 1
        return result

    def next(self) -> Symbol:
        result = self.next_or_closing()
        if result.is_closing:
            raise TranslationError("Unexpected closing symbol")
        return result

    def next_closing(self) -> None:
        if not self.next_or_closing().is_closing:
            raise TranslationError("Missing closing bracket")

    def next_expression(self) -> Symbol:
        result = self.next()
        if not result.is_expression:
            raise TranslationError("An expression was expected")
        return result

    def back(self) -> None:
        self.position -= 1
