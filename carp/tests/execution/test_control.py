from collections.abc import Callable
from random import randint

import pytest
from tests.execution.test_wiring import create_data_path, operations

from common.operations import (
    Operation,
    Registry,
    Value,
    RA,
    RB,
    BinaryOperation,
    JumpOperation,
    MemoryOperation,
    StackOperation,
    OperationBase,
)
from executor.control import ControlUnit


def create_control_unit(
    instruction_memory: list[Operation] | None = None,
    input_data: list[int] | None = None,
) -> ControlUnit:
    return ControlUnit(create_data_path(instruction_memory, input_data))


@pytest.mark.parametrize("count", range(3))
def test_fetch(count: int) -> None:
    cu: ControlUnit = create_control_unit(instruction_memory=operations[:count])

    i: int = 0
    operation: Operation | None = None
    assert cu.data_path.instruction_pointer == i
    assert cu.data_path.command_data is None

    for i, operation in enumerate(operations[:count], start=1):
        cu.fetch_instruction()
        assert cu.data_path.command_data == operation
        assert cu.data_path.instruction_pointer == i

    for _ in range(2):
        cu.fetch_instruction()
        assert cu.data_path.command_data == operation
        assert cu.data_path.instruction_pointer == i
        assert cu.finished
        cu.execute_instruction()


@pytest.fixture
def cu() -> ControlUnit:
    return create_control_unit()


THE_VALUE: int = 10


@pytest.mark.parametrize(
    "source", [RB, Value(value=-THE_VALUE)], ids=["registry", "value"]
)
@pytest.mark.parametrize(
    ("code", "output", "result"),
    [
        pytest.param(
            BinaryOperation.Code.COMPARE,
            THE_VALUE + THE_VALUE,
            THE_VALUE,
            id="cmp",
        ),
        pytest.param(
            BinaryOperation.Code.COMPARE_REVERSE,
            -THE_VALUE - THE_VALUE,
            THE_VALUE,
            id="pmc",
        ),
        pytest.param(
            BinaryOperation.Code.MATH_ADD,
            0,
            0,
            id="add",
        ),
    ],
)
def test_binary_operations(
    cu: ControlUnit,
    source: Registry | Value,
    code: BinaryOperation.Code,
    output: int,
    result: int,
) -> None:
    cu.data_path.general_registries[Registry.Code.ACCUMULATOR] = THE_VALUE
    cu.data_path.general_registries[Registry.Code.BUFFER] = -THE_VALUE

    operation = BinaryOperation(code=code, right=RA, left=source)
    cu.data_path.command_data = Operation.parse_obj(operation)
    cu.execute_instruction()

    assert cu.data_path.general_registries[Registry.Code.ACCUMULATOR] == result
    assert cu.data_path.general_registries[Registry.Code.BUFFER] == -THE_VALUE

    assert cu.data_path.alu.zero == (output == 0)
    assert cu.data_path.alu.negative == (output < 0)


@pytest.mark.parametrize(
    ("zero", "negative"),
    [
        pytest.param(False, False, id="positive"),
        pytest.param(True, False, id="zero"),
        pytest.param(False, True, id="negative"),
    ],
)
@pytest.mark.parametrize(
    ("code", "check"),
    [
        pytest.param(
            JumpOperation.Code.JUMP_BECAUSE,
            lambda z, n: True,
            id="jb",
        ),
        pytest.param(
            JumpOperation.Code.JUMP_ZERO,
            lambda z, n: z,
            id="jz",
        ),
        pytest.param(
            JumpOperation.Code.JUMP_NEGATIVE,
            lambda z, n: n,
            id="jn",
        ),
    ],
)
def test_jump_operations(
    cu: ControlUnit,
    code: JumpOperation.Code,
    check: Callable[[bool, bool], bool],
    zero: bool,
    negative: bool,
) -> None:
    cu.data_path.alu.zero = zero
    cu.data_path.alu.negative = negative

    ip: int = cu.data_path.instruction_pointer
    offset: int = randint(-100, 100)

    operation = JumpOperation(code=code, offset=offset)
    cu.data_path.command_data = Operation.parse_obj(operation)
    cu.execute_instruction()

    if check(zero, negative):
        ip += offset
    assert cu.data_path.instruction_pointer == ip
    assert cu.data_path.alu.zero is zero
    assert cu.data_path.alu.negative is negative


def test_memory_execute(cu: ControlUnit) -> None:
    cu.data_path.command_data = Operation.parse_obj(
        MemoryOperation(code=MemoryOperation.Code.LOAD_MEMORY, address=THE_VALUE)
    )
    cu.execute_instruction()
    assert cu.data_path.memory_pointer == THE_VALUE


@pytest.mark.parametrize(
    ("code", "delta"),
    [
        pytest.param(StackOperation.Code.PUSH, -1, id="push"),
        pytest.param(StackOperation.Code.GRAB, 1, id="grab"),
    ],
)
def test_stack_execute(cu: ControlUnit, code: StackOperation.Code, delta: int) -> None:
    # Impossible flags to check their persistence
    cu.data_path.alu.zero = True
    cu.data_path.alu.negative = True

    sp: int = cu.data_path.stack_pointer
    cu.data_path.command_data = Operation.parse_obj(StackOperation(code=code))
    cu.execute_instruction()
    assert cu.data_path.stack_pointer == sp + delta

    assert cu.data_path.alu.zero
    assert cu.data_path.alu.negative


THE_ADDRESS: int = 25


@pytest.mark.parametrize(
    ("operation", "read", "write"),
    [
        (None, False, False),
        (
            MemoryOperation(code=MemoryOperation.Code.SAVE_MEMORY, address=THE_ADDRESS),
            False,
            True,
        ),
        (
            MemoryOperation(code=MemoryOperation.Code.LOAD_MEMORY, address=THE_ADDRESS),
            True,
            False,
        ),
        (StackOperation(code=StackOperation.Code.PUSH), False, True),
        (StackOperation(code=StackOperation.Code.GRAB), True, False),
        (JumpOperation(), False, False),
    ],
    ids=["none", "save", "load", "push", "grab", "other"],
)
def test_memory_fetch(
    cu: ControlUnit,
    operation: OperationBase | None,
    read: bool,
    write: bool,
) -> None:
    op: Operation | None = None if operation is None else Operation.parse_obj(operation)
    cu.data_path.command_data = op
    cu.data_path.memory_pointer = THE_ADDRESS
    cu.data_path.stack_pointer = THE_ADDRESS

    if read:
        cu.data_path.data_memory[THE_ADDRESS - 1] = THE_VALUE
        cu.data_path.data_memory[THE_ADDRESS] = THE_VALUE
    cu.data_path.general_registries[Registry.Code.ACCUMULATOR] = -THE_VALUE

    cu.memory_fetch()

    if read:
        assert cu.data_path.general_registries[Registry.Code.ACCUMULATOR] == THE_VALUE
    elif write:
        assert cu.data_path.data_memory[THE_ADDRESS] == -THE_VALUE
    else:
        assert cu.data_path.data_memory[THE_ADDRESS] == 0
        assert cu.data_path.general_registries[Registry.Code.ACCUMULATOR] == -THE_VALUE


@pytest.mark.parametrize("count", range(3))
def test_logs(count: int) -> None:
    cu: ControlUnit = create_control_unit(operations[:count])
    cu.main()
    assert len(cu.log) == count + 1
    assert cu.finished
