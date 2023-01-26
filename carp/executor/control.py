from common.operations import (
    BinaryOperation,
    Registry,
    Value,
    StackOperation,
    JumpOperation,
    MemoryOperation, OperationBase,
)
from executor.alu import ALUOperation
from executor.logs import LogRecord
from executor.wiring import DataPath


class ControlUnit:
    def __init__(self, data_path: DataPath):
        self.data_path: DataPath = data_path
        self.log: list[LogRecord] = []
        self.finished: bool = False

    def fetch_instruction(self) -> None:
        if self.data_path.read_command():
            self.data_path.instruction_pointer += 1
        else:
            self.finished = True

    OPERATION_TO_ALU = {
        BinaryOperation.Code.MOVE_DATA: ALUOperation.RIGHT,
        BinaryOperation.Code.MATH_ADD: ALUOperation.ADD,
        BinaryOperation.Code.MATH_SUB: ALUOperation.SUB,
        BinaryOperation.Code.MATH_MUL: ALUOperation.MUL,
        BinaryOperation.Code.MATH_DIV: ALUOperation.DIV,
        BinaryOperation.Code.MATH_MOD: ALUOperation.MOD,
    }

    def execute_binary_operation(self, operation: BinaryOperation) -> None:
        if isinstance(operation.left, Registry):
            source: int = self.data_path.read_register(operation.left.code)
        elif isinstance(operation.left, Value):
            source: int = operation.left.value
        target: int = self.data_path.read_register(operation.right.code)

        if operation.code == BinaryOperation.Code.COMPARE:
            self.data_path.alu_execute(
                operation=ALUOperation.SUB,
                left=target,
                right=source,
            )
        elif operation.code == BinaryOperation.Code.COMPARE_REVERSE:
            self.data_path.alu_execute(
                operation=ALUOperation.SUB,
                left=source,
                right=target,
            )
        else:
            self.data_path.write_register(
                operation.right.code,
                self.data_path.alu_execute(
                    operation=self.OPERATION_TO_ALU[operation.code],
                    left=target,
                    right=source,
                ),
            )

    def execute_jump_operation(self, operation: JumpOperation) -> None:
        if (
            operation.code is JumpOperation.Code.JUMP_ZERO
            and not self.data_path.alu.zero
            or operation.code is JumpOperation.Code.JUMP_NEGATIVE
            and not self.data_path.alu.negative
        ):
            return

        self.data_path.instruction_pointer = self.data_path.alu_execute(
            operation=ALUOperation.ADD,
            left=self.data_path.instruction_pointer,
            right=operation.offset,
            flags=False,
        )

    def execute_instruction(self) -> None:
        operation: OperationBase = self.data_path.command_data.__root__
        if isinstance(operation, BinaryOperation):
            self.execute_binary_operation(operation)
        elif isinstance(operation, JumpOperation):
            self.execute_jump_operation(operation)
        elif isinstance(operation, MemoryOperation):
            self.data_path.memory_pointer = operation.address
        elif isinstance(operation, StackOperation):
            self.data_path.stack_pointer = self.data_path.alu_execute(
                operation=ALUOperation.ADD
                if operation.code is StackOperation.Code.PUSH
                else ALUOperation.SUB,
                left=self.data_path.stack_pointer,
                right=1,
                flags=False,
            )

    def memory_fetch(self) -> None:
        operation: OperationBase = self.data_path.command_data.__root__
        if isinstance(operation, MemoryOperation):
            if operation.code is MemoryOperation.Code.LOAD_MEMORY:
                self.data_path.memory_read(operation.right.code)
            elif operation.code is MemoryOperation.Code.SAVE_MEMORY:
                self.data_path.memory_write(operation.right.code)
        elif isinstance(operation, StackOperation):
            if operation.code is StackOperation.Code.PUSH:
                self.data_path.memory_write(operation.right.code, stack=True)
            elif operation.code is StackOperation.Code.GRAB:
                self.data_path.memory_read(operation.right.code, stack=True)

    def save_state(self) -> None:
        self.log.append(self.data_path.record_state())

    def main(self) -> None:
        self.save_state()
        self.fetch_instruction()
        while not self.finished:
            self.execute_instruction()
            self.memory_fetch()
            self.save_state()
            self.fetch_instruction()
