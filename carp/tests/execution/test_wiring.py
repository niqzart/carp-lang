from collections.abc import Callable
from dataclasses import dataclass
from random import randint
from typing import Any

import pytest
from pydantic import parse_obj_as

from common.constants import IO_DEVICE_COUNT, INPUT_ADDRESS, OUTPUT_ADDRESS
from common.operations import Operation, BinaryOperation, Registry, RB
from executor.alu import ALUOperation
from executor.wiring import DataPath

MAX_MEMORY_ADDRESS: int = 100


def create_data_path(
    instruction_memory: list[Operation] | None = None,
    input_data: list[int] | None = None,
) -> DataPath:
    return DataPath(
        data_memory_size=MAX_MEMORY_ADDRESS,
        instruction_memory=instruction_memory or [],
        input_data=input_data or [],
    )


operations: list[Operation] = parse_obj_as(
    list[Operation],
    [
        BinaryOperation(code=BinaryOperation.Code.MOVE_DATA, left=RB),
        BinaryOperation(code=BinaryOperation.Code.MATH_ADD, left=RB),
    ],
)


@pytest.mark.parametrize(
    "operations",
    [
        pytest.param([], id="no_operations"),
        pytest.param(operations[:1], id="one_operation"),
        pytest.param(operations[:2], id="two_operations"),
    ],
)
def test_read_command(operations: list[Operation]) -> None:
    dp: DataPath = create_data_path(instruction_memory=operations)
    for operation in operations:
        assert dp.read_command()
        assert dp.command_data == operation
        dp.instruction_pointer += 1
    assert not dp.read_command()


# hack for mypy's typization
@dataclass
class RequestRegistryCode:
    param: Registry.Code


@pytest.fixture(
    params=[
        pytest.param(code, id=code.value.lower())
        for code in Registry.Code.__members__.values()
    ]
)
def registry_code(request: RequestRegistryCode) -> Registry.Code:
    return request.param


# hack for mypy's typization
@dataclass
class RequestBool:
    param: bool


@pytest.fixture(
    params=[
        pytest.param(False, id="memory"),
        pytest.param(True, id="stack"),
    ],
)
def stack(request: RequestBool) -> bool:
    return request.param


@pytest.mark.parametrize(
    ("method", "error_text"),
    [
        pytest.param(DataPath.memory_read, "read from outside", id="read"),
        pytest.param(DataPath.memory_write, "write to outside", id="write"),
    ],
)
@pytest.mark.parametrize("address", [MAX_MEMORY_ADDRESS, -2], ids=["huge", "negative"])
def test_memory_fails(
    method: Callable[[DataPath, Registry.Code, bool], None],
    error_text: str,
    registry_code: Registry.Code,
    stack: bool,
    address: int,
) -> None:
    dp: DataPath = create_data_path()
    if stack:
        dp.stack_pointer = address + 1
    else:
        dp.memory_pointer = address

    with pytest.raises(IndexError) as e:
        method(dp, registry_code, stack)

    assert e.value.args[0] == f"An attempt to {error_text} the memory"


def test_memory_and_stack(registry_code: Registry.Code, stack: bool) -> None:
    value: int = randint(1, 100)
    address: int = randint(IO_DEVICE_COUNT + 1, MAX_MEMORY_ADDRESS - 1)

    dp: DataPath = create_data_path()
    dp.general_registries[registry_code] = value
    if stack:
        dp.stack_pointer = address
    else:
        dp.memory_pointer = address

    dp.memory_write(registry_code, stack=stack)
    assert dp.data_memory[address] == value
    assert dp.general_registries[registry_code] == value

    if stack:
        dp.stack_pointer += 1
    dp.general_registries[registry_code] = -value

    dp.memory_read(registry_code, stack=stack)
    assert not dp.alu.zero
    assert not dp.alu.negative
    assert dp.data_memory[address] == value
    assert dp.general_registries[registry_code] == value

    if registry_code is Registry.Code.ACCUMULATOR:
        assert dp.accumulator == value
    else:
        assert dp.buffer == value


@pytest.mark.parametrize("input_len", list(range(3)))
def test_input(input_len: int, registry_code: Registry.Code) -> None:
    data = [randint(1, 100), randint(101, 200)][:input_len]
    dp: DataPath = create_data_path(input_data=data)
    dp.memory_pointer = INPUT_ADDRESS

    for value in data:
        dp.general_registries[registry_code] = -value
        dp.memory_read(registry_code)
        assert dp.general_registries[registry_code] == value
        assert dp.last_io[INPUT_ADDRESS] == value
        assert not dp.alu.zero
        assert not dp.alu.negative

    dp.general_registries[registry_code] = -randint(1, 100)
    dp.memory_read(registry_code)
    assert dp.general_registries[registry_code] == 0
    assert dp.last_io[INPUT_ADDRESS] == 0
    assert dp.alu.zero
    assert not dp.alu.negative


@pytest.mark.parametrize("input_len", list(range(3)))
def test_output(input_len: int, registry_code: Registry.Code) -> None:
    data = [randint(1, 100), randint(101, 200)][:input_len]
    dp: DataPath = create_data_path()
    dp.memory_pointer = OUTPUT_ADDRESS

    for value in data:
        dp.general_registries[registry_code] = value
        dp.memory_write(registry_code)
        assert dp.last_io[OUTPUT_ADDRESS] == value

    assert dp.get_output() == data


@pytest.mark.parametrize(
    "device",
    [i for i in range(IO_DEVICE_COUNT) if i not in {INPUT_ADDRESS, OUTPUT_ADDRESS}],
)
@pytest.mark.parametrize(
    "method",
    [DataPath.memory_read, DataPath.memory_write],
    ids=["read", "write"],
)
def test_device_fails(
    method: Callable[[DataPath, Registry.Code], None],
    registry_code: Registry.Code,
    device: int,
) -> None:
    dp: DataPath = create_data_path()
    dp.memory_pointer = device

    with pytest.raises(RuntimeError) as e:
        method(dp, registry_code)

    assert e.value.args[0] == f"Device {device} not connected"


@pytest.mark.parametrize(
    ("zero", "negative"),
    [
        pytest.param(True, False, id="zero"),
        pytest.param(False, False, id="positive"),
        pytest.param(False, True, id="negative"),
    ],
)
@pytest.mark.parametrize(
    "flags",
    [True, False],
    ids=["with_flags", "no_flags"],
)
def test_alu(
    zero: bool,
    negative: bool,
    flags: bool,
) -> None:
    value: int = 0 if zero else randint(1, 100) * (-1 if negative else 1)

    dp: DataPath = create_data_path()
    dp.alu.zero = not zero
    dp.alu.negative = not negative

    result = dp.alu_execute(ALUOperation.LEFT, left=value, right=0, flags=flags)

    assert result == value
    assert dp.alu.result == value

    if flags:
        assert dp.alu.zero == zero
        assert dp.alu.negative == negative
    else:
        assert dp.alu.zero != zero
        assert dp.alu.negative != negative


def test_logging() -> None:
    data: dict[str, Any] = {
        "registries": {
            "accumulator": randint(1, 100),
            "buffer": randint(1, 100),
            "memory_pointer": randint(1, 100),
            "stack_pointer": randint(1, 100),
            "instruction_pointer": randint(1, 100),
            "command_data": None,
        },
        "flags": {"zero": bool(randint(0, 1)), "negative": bool(randint(0, 1))},
        "input_data": randint(1, 100),
        "output_data": randint(1, 100),
    }

    dp: DataPath = create_data_path()

    dp.general_registries[Registry.Code.ACCUMULATOR] = data["registries"]["accumulator"]
    dp.general_registries[Registry.Code.BUFFER] = data["registries"]["buffer"]
    dp.memory_pointer = data["registries"]["memory_pointer"]
    dp.stack_pointer = data["registries"]["stack_pointer"]
    dp.instruction_pointer = data["registries"]["instruction_pointer"]

    dp.alu.zero = data["flags"]["zero"]
    dp.alu.negative = data["flags"]["negative"]

    dp.last_io = {
        INPUT_ADDRESS: data["input_data"],
        OUTPUT_ADDRESS: data["output_data"],
    }

    state = dp.record_state()
    assert len(dp.last_io) == 0
    assert state.dict() == data
