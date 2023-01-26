from common.constants import INPUT_ADDRESS, OUTPUT_ADDRESS
from common.errors import TranslationError
from common.operations import (
    OperationBase,
    MemoryOperation,
    BinaryOperation,
    Value,
    StackOperation,
    RB,
    RA,
    JumpOperation,
    OPERAND_TO_CODE,
)
from translator.reader import Reader, Symbol
from translator.comparators import SYMBOL_TO_COMPARATOR
from translator.variables import VariableIndex, VarDef


class Translator:
    """
    Class that does the main bulk of translating CARP™ source code to machine code.

    More specifically it translates parsed symbols (accessed via :py:class:`Reader`)
    to machine code operations, created with pydantic models from ``common.operations``
    (represented in :py:attr:`result` as a list of :py:class:`OperationBase`).

    Basic usage: initialize and call :py:meth:`parce_blocks`
    """

    def __init__(self, reader: Reader) -> None:
        self.reader: Reader = reader
        self.result: list[OperationBase] = []
        self.variables: VariableIndex = VariableIndex()

    def check_closed_bracket(self) -> None:
        self.reader.next_closing()

    def _parse_argument(
        self, argument: Symbol, allow_strings: bool = False
    ) -> VarDef | str | int:
        if argument.is_quoted:
            if allow_strings:
                return argument.text[1:-1]
            raise TranslationError("Argument can't be a string")
        if argument.text.isdigit():
            return int(argument.text)
        return self.variables.read(argument.text)

    def parse_argument(self, allow_strings: bool = False) -> VarDef | str | int | None:
        if self.reader.current().is_expression:
            return None
        return self._parse_argument(self.reader.next(), allow_strings=allow_strings)

    def translate_argument(
        self, operation: OperationBase = None, allow_strings: bool = False
    ) -> None:
        argument = self.parse_argument(allow_strings=allow_strings)
        if allow_strings and isinstance(argument, str):
            for character in argument[1:-1]:
                self.result.append(
                    BinaryOperation(
                        code=BinaryOperation.Code.MOVE_DATA,
                        left=Value(value=ord(character)),
                    )
                )
                if operation is not None:
                    self.result.append(operation)
            return
        if argument is None:
            self.parse_valuable()
        elif isinstance(argument, int):
            self.result.append(
                BinaryOperation(
                    code=BinaryOperation.Code.MOVE_DATA,
                    left=Value(value=argument),
                )
            )
        elif isinstance(argument, VarDef):
            self.result.append(
                MemoryOperation(
                    code=MemoryOperation.Code.LOAD_MEMORY,
                    address=argument.location,
                )
            )
        if operation is not None:
            self.result.append(operation)

    def translate_construct(self) -> tuple[JumpOperation, int]:
        header: Symbol = self.reader.next()
        skip_operation: JumpOperation
        if header.is_expression:
            comparator: str = header.text[1:]
            data = SYMBOL_TO_COMPARATOR.get(comparator).data
            self.translate_operation(data.command)
            if data is None:
                raise TranslationError(f"Unknown comparator: '{comparator}'")
            skip_operation = JumpOperation(code=data.jump)
            self.result.append(skip_operation)
            if data.negated:
                skip_operation = JumpOperation()
                self.result.append(skip_operation)
            self.check_closed_bracket()
        elif self.variables.check_name(header.text):
            variable = self.variables.read(header.text)
            self.result.append(
                MemoryOperation(
                    code=MemoryOperation.Code.LOAD_MEMORY,
                    address=variable.location,
                )
            )
            skip_operation = JumpOperation(code=JumpOperation.Code.JUMP_ZERO)
            self.result.append(skip_operation)
        else:
            raise TranslationError(f"Unsupported condition header: '{header}'")
        skip_jump_index = len(self.result)
        self.parse_blocks(allow_quit=True)
        return skip_operation, skip_jump_index

    def translate_operation(self, operation_type: BinaryOperation.Code) -> None:
        self.translate_argument()

        right = self.parse_argument()
        if right is None:
            self.result.append(StackOperation(code=StackOperation.Code.PUSH))
            self.parse_valuable()
            self.result.append(StackOperation(code=StackOperation.Code.GRAB, right=RB))
            self.result.append(BinaryOperation(code=operation_type, right=RB, left=RA))
            if operation_type != BinaryOperation.Code.COMPARE:
                self.result.append(
                    BinaryOperation(code=BinaryOperation.Code.MOVE_DATA, left=RB)
                )
        elif isinstance(right, int):
            self.result.append(
                BinaryOperation(code=operation_type, left=Value(value=right))
            )
        elif isinstance(right, VarDef):
            self.result.append(
                MemoryOperation(
                    code=MemoryOperation.Code.LOAD_MEMORY,
                    right=RB,
                    address=right.location,
                )
            )
            self.result.append(BinaryOperation(code=operation_type, left=RB))

    def parse_command(self) -> None:
        header = self.reader.next_expression().text[1:]

        match header:
            case "print":
                self.translate_argument(
                    MemoryOperation(
                        code=MemoryOperation.Code.SAVE_MEMORY,
                        address=OUTPUT_ADDRESS,
                    ),
                    allow_strings=True,
                )
            case "assign":
                var_name = self.reader.next().text
                location = self.variables.register(var_name)
                self.translate_argument(
                    MemoryOperation(
                        code=MemoryOperation.Code.SAVE_MEMORY,
                        address=location,
                    ),
                    allow_strings=True,
                )
            case "if":
                skip_operation, skip_jump_index = self.translate_construct()
                skip_operation.offset = len(self.result) - skip_jump_index
            case "loop":
                condition_start: int = len(self.result)
                skip_operation, skip_jump_index = self.translate_construct()
                self.result.append(
                    JumpOperation(offset=condition_start - len(self.result) - 1)
                )
                skip_operation.offset = len(self.result) - skip_jump_index
            case _:
                raise TranslationError(f"Unknown command: '{header}'")

        self.check_closed_bracket()

    def parse_valuable(self) -> None:
        header = self.reader.next_expression().text[1:]

        if header == "input":
            self.result.append(
                MemoryOperation(
                    code=MemoryOperation.Code.LOAD_MEMORY,
                    address=INPUT_ADDRESS,
                )
            )
        else:
            operation_type = OPERAND_TO_CODE.get(header)
            if operation_type is None:
                raise TranslationError(f"Unknown operand: '{header}'")
            self.translate_operation(operation_type)
        self.check_closed_bracket()

    def parse_blocks(self, allow_quit: bool = False) -> None:
        while self.reader.has_next():
            if allow_quit and self.reader.current_or_closing().is_closing:
                return
            self.parse_command()
