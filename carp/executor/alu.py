from enum import Enum, auto
from typing import Protocol

from common.constants import WORD_MAX_VALUE, WORD_MIN_VALUE


class ALUOperation(int, Enum):
    ADD = auto()
    SUB = auto()
    MUL = auto()
    DIV = auto()
    MOD = auto()
    LEFT = auto()
    RIGHT = auto()


class ALU:
    class OperationProtocol(Protocol):
        def __call__(self, left: int, right: int) -> int:
            pass

    operations: dict[ALUOperation, OperationProtocol] = {
        ALUOperation.ADD: int.__add__,
        ALUOperation.SUB: int.__sub__,
        ALUOperation.MUL: int.__mul__,
        ALUOperation.DIV: int.__floordiv__,
        ALUOperation.MOD: int.__mod__,
        ALUOperation.LEFT: lambda *args: args[0],
        ALUOperation.RIGHT: lambda *args: args[1],
    }

    def __init__(self):
        self.right: int = 0
        self.left: int = 0

        self.result: int = 0
        self.zero: bool = True
        self.negative: bool = False

    def execute(self, operation: ALUOperation, flags: bool = True) -> None:
        self.result = self.operations[operation](self.left, self.right)
        if self.result > WORD_MAX_VALUE:
            self.result %= WORD_MAX_VALUE + 1
        elif self.result < WORD_MIN_VALUE:
            self.result %= WORD_MIN_VALUE

        if flags:
            self.zero = self.result == 0
            self.negative = self.result < 0
