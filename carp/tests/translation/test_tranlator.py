import json
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
from pytest_golden.plugin import (  # type: ignore
    GoldenTestFixtureFactory,
    GoldenTestFixture,
)

from common.constants import INPUT_ADDRESS, OUTPUT_ADDRESS
from common.errors import TranslationError
from common.operations import OPERATOR_TO_CODE, BinaryOperation, Value
from translator.comparators import SYMBOL_TO_COMPARATOR
from translator.parser import Symbol
from translator.reader import Reader
from translator.translator import Translator


# hack for mypy's typization
@dataclass
class FixtureRequest:
    param: int


@pytest.fixture(params=[pytest.param(i, id=f"line_{i}") for i in range(3)])
def line(request: FixtureRequest) -> int:
    return request.param


@pytest.fixture(params=[pytest.param(i, id=f"char_{i}") for i in range(3)])
def char(request: FixtureRequest) -> int:
    return request.param


@pytest.fixture
def position(line: int, char: int) -> dict[str, int]:
    return {"line": line, "char": char}


@pytest.fixture
def reader() -> Reader:
    return Reader("")


@pytest.fixture
def translator(reader: Reader) -> Translator:
    result = Translator(reader)
    result.variables.register(THE_VARIABLE)
    return result


@pytest.fixture
def assert_debug_symbol(
    position: dict[str, int], reader: Reader
) -> Callable[[str], None]:
    def assert_debug_symbol_inner(expected_text: str) -> None:
        reader.back()
        debug_symbol: Symbol = reader.current_or_closing()
        assert debug_symbol.line == position["line"]
        assert debug_symbol.char == position["char"]
        assert debug_symbol.text == expected_text

    return assert_debug_symbol_inner


THE_INTEGER = 1
THE_VARIABLE = "var"

translated_arguments: dict[str, tuple[list[str], dict[str, Any]]] = {
    "integer": (
        [f"{THE_INTEGER}"],
        {
            "code": "mov",
            "right": {"type": "registry", "code": "A"},
            "left": {"type": "value", "value": THE_INTEGER},
        },
    ),
    "variable": (
        [THE_VARIABLE],
        {
            "code": "load",
            "right": {"type": "registry", "code": "A"},
            "address": 16,
        },
    ),
    "expression": (
        ["(input", ")"],
        {
            "code": "load",
            "right": {"type": "registry", "code": "A"},
            "address": INPUT_ADDRESS,
        },
    ),
}


@pytest.mark.parametrize(
    ("symbols", "expected"),
    [
        pytest.param(symbols, expected, id=key)
        for key, (symbols, expected) in translated_arguments.items()
    ],
)
def test_arguments(
    translator: Translator, symbols: list[str], expected: dict[str, Any]
) -> None:
    translator.reader.symbols = [
        Symbol(text=symbol_text, line=0, char=0) for symbol_text in symbols
    ]

    additional_operation = BinaryOperation(
        code=BinaryOperation.Code.MOVE_DATA,
        left=Value(value=THE_INTEGER),
    )
    translator.translate_argument(operation=additional_operation)

    real = translator.result
    assert len(real) == 2
    assert json.loads(real[0].json()) == expected
    assert real[1] == additional_operation


def test_deny_strings(
    translator: Translator,
    position: dict[str, int],
    assert_debug_symbol: Callable[[str], None],
) -> None:
    symbol_text: str = '"hello"'
    translator.reader.symbols = [Symbol(text=symbol_text, **position)]
    with pytest.raises(TranslationError) as e:
        translator.translate_argument()
    assert str(e.value) == "Argument can't be a string"
    assert_debug_symbol(symbol_text)


@pytest.mark.parametrize("operator", list(OPERATOR_TO_CODE))
@pytest.mark.parametrize("stack", [True, False], ids=["stack", "top"])
@pytest.mark.parametrize(
    ("second_arg_symbol", "second_arg_expected"),
    [
        pytest.param(
            translated_arguments["integer"][0],
            [
                {
                    "right": {"type": "registry", "code": "B"},
                    "left": {"type": "value", "value": THE_INTEGER},
                    "code": "mov",
                },
                {
                    "right": {"type": "registry", "code": "A"},
                    "left": {"type": "registry", "code": "B"},
                },
            ],
            id="second_arg_integer",
        ),
        pytest.param(
            translated_arguments["variable"][0],
            [
                {
                    "code": "load",
                    "right": {"type": "registry", "code": "B"},
                    "address": 16,
                },
                {
                    "right": {"type": "registry", "code": "A"},
                    "left": {"type": "registry", "code": "B"},
                },
            ],
            id="second_arg_variable",
        ),
        pytest.param(
            translated_arguments["expression"][0],
            [
                {
                    "code": "load",
                    "right": {"type": "registry", "code": "B"},
                    "address": INPUT_ADDRESS,
                },
                {
                    "right": {"type": "registry", "code": "A"},
                    "left": {"type": "registry", "code": "B"},
                },
            ],
            id="second_arg_expression",
        ),
    ],
)
def test_operators(
    translator: Translator,
    operator: str,
    stack: bool,
    second_arg_symbol: list[str],
    second_arg_expected: list[dict[str, Any]],
) -> None:
    translator.reader.symbols = [
        Symbol(text=symbol_text, line=0, char=0)
        for symbol_text in ("(" + operator, str(THE_INTEGER), *second_arg_symbol, ")")
    ]
    translator.translate_valuable(stack=stack)

    real = [json.loads(operation.json()) for operation in translator.result]

    if stack:
        common = {"type": "registry", "code": "B"}
        assert real.pop(1) == {"code": "push", "right": common}
        assert real.pop() == {"code": "grab", "right": common}

    assert len(real) == 1 + len(second_arg_expected)

    assert real[0] == translated_arguments["integer"][1]
    for i in range(len(second_arg_expected)):
        expected = second_arg_expected[i].copy()
        expected.setdefault("code", OPERATOR_TO_CODE[operator].value)
        assert real[i + 1] == expected


@pytest.mark.parametrize(
    ("command", "address"),
    [
        pytest.param(["(print", THE_VARIABLE, ")"], OUTPUT_ADDRESS, id="print-var"),
        pytest.param(["(print", '"h"', ")"], OUTPUT_ADDRESS, id="print-str"),
        pytest.param(["(assign", THE_VARIABLE, str(THE_INTEGER), ")"], 16, id="assign"),
    ],
)
def test_commands(translator: Translator, command: list[str], address: int) -> None:
    translator.reader.symbols = [
        Symbol(text=symbol_text, line=0, char=0) for symbol_text in command
    ]
    translator.translate_valuable()

    real = [json.loads(operation.json()) for operation in translator.result]
    assert len(real) == 2
    assert real[1] == {
        "code": "save",
        "right": {"type": "registry", "code": "A"},
        "address": address,
    }


def test_output(golden: GoldenTestFixtureFactory, translator: Translator) -> None:
    gold: GoldenTestFixture = golden.open(Path("output.yml"))

    translator.reader.symbols = [
        Symbol(text=symbol_text, line=0, char=0)
        for symbol_text in ("(output", THE_VARIABLE, ")")
    ]
    translator.translate_valuable()

    real = [json.loads(operation.json()) for operation in translator.result]
    assert real == gold.out["output"]


@pytest.mark.parametrize(
    ("name", "comparison"),
    [
        pytest.param(
            "var",
            [THE_VARIABLE],
            id="var",
        ),
    ]
    + [
        pytest.param(
            name,
            ["(" + name, str(THE_INTEGER), str(THE_INTEGER), ")"],
            id=name,
        )
        for name, comparator in SYMBOL_TO_COMPARATOR.items()
    ],
)
@pytest.mark.parametrize("construct", ("if", "loop"))
def test_constructs(
    golden: GoldenTestFixtureFactory,
    translator: Translator,
    construct: str,
    comparison: list[str],
    name: str,
) -> None:
    gold: GoldenTestFixture = golden.open(Path("constructs.yml"))

    translator.reader.symbols = [
        Symbol(text=symbol_text, line=0, char=0)
        for symbol_text in ("(" + construct, *comparison, str(THE_VARIABLE), ")")
    ]
    translator.translate_valuable(stack=False)

    real = [operation.json() for operation in translator.result]
    assert real == gold.out[f"{name}-{construct}"]


def test_unknown_header(
    translator: Translator,
    position: dict[str, int],
    assert_debug_symbol: Callable[[str], None],
) -> None:
    operator: str = "!"
    translator.reader.symbols = [Symbol(text="(" + operator, **position)]
    with pytest.raises(TranslationError) as e:
        translator.translate_valuable()
    assert str(e.value) == f"Unknown operation: '{operator}'"
    assert_debug_symbol("(" + operator)


def test_blocks(
    translator: Translator,
    position: dict[str, int],
    assert_debug_symbol: Callable[[str], None],
) -> None:
    translator.translate_blocks()
    assert len(translator.result) == 0

    translator.reader.symbols = [Symbol(text=")", **position)]
    translator.translate_blocks(allow_quit=True)
    with pytest.raises(TranslationError) as e:
        translator.translate_blocks()
    assert str(e.value) == "Unexpected closing symbol"
    assert_debug_symbol(")")
