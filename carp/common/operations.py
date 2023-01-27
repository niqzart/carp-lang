from enum import Enum
from typing import Literal

from pydantic import BaseModel


class Operand(BaseModel):
    type: str  # noqa: A003 VNE003


class Registry(Operand):
    class Code(str, Enum):
        ACCUMULATOR = "A"
        BUFFER = "B"

    type: Literal["registry"] = "registry"  # noqa: A003 VNE003
    code: Code


RA: Registry = Registry(code=Registry.Code.ACCUMULATOR)
RB: Registry = Registry(code=Registry.Code.BUFFER)


class Value(Operand):
    type: Literal["value"] = "value"  # noqa: A003 VNE003
    value: int


class OperationBase(BaseModel):
    code: str


class BinaryOperation(OperationBase):
    class Code(str, Enum):
        MOVE_DATA = "mov"
        COMPARE = "cmp"
        COMPARE_REVERSE = "pmc"
        MATH_ADD = "add"
        MATH_SUB = "sub"
        MATH_MUL = "mul"
        MATH_DIV = "div"
        MATH_MOD = "mod"

    code: Code
    right: Registry = RA
    left: Registry | Value


OPERATOR_TO_CODE: dict[str, BinaryOperation.Code] = {
    "+": BinaryOperation.Code.MATH_ADD,
    "-": BinaryOperation.Code.MATH_SUB,
    "*": BinaryOperation.Code.MATH_MUL,
    "/": BinaryOperation.Code.MATH_DIV,
    "%": BinaryOperation.Code.MATH_MOD,
}


class StackOperation(OperationBase):
    class Code(str, Enum):
        GRAB = "grab"
        PUSH = "push"

    code: Code
    right: Registry = RA


class JumpOperation(OperationBase):
    class Code(str, Enum):
        JUMP_ZERO = "jz"
        JUMP_NEGATIVE = "jn"
        JUMP_BECAUSE = "jb"

    code: Code = Code.JUMP_BECAUSE
    offset: int = 1


class MemoryOperation(OperationBase):
    class Code(str, Enum):
        LOAD_MEMORY = "load"
        SAVE_MEMORY = "save"

    code: Code
    right: Registry = RA
    address: int


class Operation(BaseModel):
    __root__: BinaryOperation | StackOperation | JumpOperation | MemoryOperation
