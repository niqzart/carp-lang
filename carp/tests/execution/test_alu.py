from collections.abc import Callable

import pytest

from common.constants import WORD_MAX_VALUE, WORD_MIN_VALUE
from executor.alu import ALU, ALUOperation


@pytest.fixture
def alu() -> ALU:
    return ALU()


@pytest.mark.parametrize(
    ("operation", "function"),
    [pytest.param(e.value, ALU.operations[e.value], id=e.name) for e in ALUOperation],
)
@pytest.mark.parametrize(("left", "right"), [(WORD_MAX_VALUE, 2), (WORD_MIN_VALUE, 4)])
def test_alu(
    alu,
    operation: ALUOperation,
    function: Callable[[int, int], int],
    left: int,
    right: int,
):
    alu.left = left
    alu.right = right
    alu.execute(operation)

    result = function(left, right)
    if result > WORD_MAX_VALUE:
        result %= WORD_MAX_VALUE + 1
    elif result < WORD_MIN_VALUE:
        result %= WORD_MIN_VALUE

    assert alu.result == result
    assert alu.zero == (result == 0)
    assert alu.negative == (result < 0)
