import random
from collections.abc import Iterator

import pytest

from translator.parser import Symbol, ParserError
from translator.reader import Parser


def _randomize_spaces(string: str) -> Iterator[str]:
    in_quotes: bool = False
    for character in string:
        if character == '"':
            in_quotes = not in_quotes
        if character in " \n\t)" and not in_quotes:
            length: int = random.randint(1, 10)
            yield from (" \n\t"[random.randint(0, 2)] for _ in range(length))
        yield character


def randomize_spaces(string: str) -> str:
    return "".join(_randomize_spaces(string))


@pytest.mark.parametrize(
    "random_spaces",
    (True, False),
    ids=("spaces-normal", "spaces-random"),
)
@pytest.mark.parametrize(
    ("source", "expected"),
    [
        pytest.param("hello", ["hello"], id="no_splits"),
        pytest.param("hello world", ["hello", "world"], id="simple_split"),
        pytest.param("(output 1)", ["(output", "1", ")"], id="bracket_split"),
        pytest.param('"hello world))"', ['"hello world))"'], id="quoted"),
        pytest.param(
            "(+ (* 3 2) 5)", ["(+", "(*", "3", "2", ")", "5", ")"], id="nested_bracket"
        ),
        pytest.param(
            "(print (input))", ["(print", "(input", ")", ")"], id="repeating_bracket"
        ),
    ]
)
def test_parsing_splits(random_spaces: bool, source: str, expected: list[str]):
    if random_spaces:
        source = randomize_spaces(source)
    real: list[Symbol] = Parser(source).result
    assert len(real) == len(expected)
    for i, symbol in enumerate(real):
        assert symbol.text == expected[i]


@pytest.mark.parametrize(
    ("symbol_text", "expression", "quoted", "closing"),
    [
        pytest.param("1", False, False, False, id="simple"),
        pytest.param("(input", True, False, False, id="expression"),
        pytest.param('"hello"', False, True, False, id="quoted"),
        pytest.param(")", False, False, True, id="closing"),
    ]
)
def test_symbols(symbol_text: str, expression: bool, quoted: bool, closing: bool):
    symbol = Symbol(text=symbol_text, line=0, char=0)
    assert symbol.is_expression == expression
    assert symbol.is_quoted == quoted
    assert symbol.is_closing == closing
    assert str(symbol) == symbol_text


@pytest.mark.parametrize(
    ("source", "exception_text"),
    (
        pytest.param(
            '"hey',
            'Parsing error occurred: Missing closing quotation mark',
            id="missing_quotation",
        ),
    )
)
def test_errors(source: str, exception_text: str):
    with pytest.raises(ParserError) as e:
        Parser(source)

    assert str(e.value) == exception_text
