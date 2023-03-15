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
    OPERATOR_TO_CODE,
)
from translator.comparators import SYMBOL_TO_COMPARATOR
from translator.parser import Symbol
from translator.reader import Reader
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

    def extend_result(self, *operations: OperationBase) -> None:
        self.result.extend(operations)

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
        self, operation: OperationBase | None = None, allow_strings: bool = False
    ) -> None:
        argument = self.parse_argument(allow_strings=allow_strings)
        if allow_strings and isinstance(argument, str):
            for character in argument:
                self.extend_result(
                    BinaryOperation(
                        code=BinaryOperation.Code.MOVE_DATA,
                        left=Value(value=ord(character)),
                    )
                )
                if operation is not None:
                    self.extend_result(operation)
            return
        if argument is None:
            self.translate_valuable()
        elif isinstance(argument, int):
            self.extend_result(
                BinaryOperation(
                    code=BinaryOperation.Code.MOVE_DATA,
                    left=Value(value=argument),
                )
            )
        elif isinstance(argument, VarDef):
            self.extend_result(
                MemoryOperation(
                    code=MemoryOperation.Code.LOAD_MEMORY,
                    address=argument.location,
                )
            )
        if operation is not None:
            self.extend_result(operation)

    def translate_construct(self) -> tuple[JumpOperation, int]:
        header: Symbol = self.reader.next()
        skip_operation: JumpOperation
        if header.is_expression:
            comparator: str = header.text[1:]
            template = SYMBOL_TO_COMPARATOR.get(comparator)
            if template is None:
                raise TranslationError(f"Unknown comparator: '{comparator}'")
            data = template.data
            self.translate_operation(data.command)
            skip_operation = JumpOperation(code=data.jump)
            self.extend_result(skip_operation)
            if data.negated:
                skip_operation = JumpOperation()
                self.extend_result(skip_operation)
            self.check_closed_bracket()
        else:
            self.extend_result(
                MemoryOperation(
                    code=MemoryOperation.Code.LOAD_MEMORY,
                    address=self.variables.read(header.text).location,
                )
            )
            skip_operation = JumpOperation(code=JumpOperation.Code.JUMP_ZERO)
            self.extend_result(skip_operation)
        skip_jump_index = len(self.result)
        self.translate_blocks(allow_quit=True)
        return skip_operation, skip_jump_index

    def translate_operation(self, operation_type: BinaryOperation.Code) -> None:
        self.translate_argument()

        right = self.parse_argument()
        if right is None:
            self.extend_result(StackOperation(code=StackOperation.Code.PUSH))
            self.translate_valuable()
            self.extend_result(
                StackOperation(code=StackOperation.Code.GRAB, right=RB),
                BinaryOperation(code=operation_type, right=RB, left=RA),
            )
            if operation_type != BinaryOperation.Code.COMPARE:
                self.extend_result(
                    BinaryOperation(code=BinaryOperation.Code.MOVE_DATA, left=RB)
                )
        elif isinstance(right, int):
            self.extend_result(
                BinaryOperation(code=operation_type, left=Value(value=right))
            )
        elif isinstance(right, VarDef):
            self.extend_result(
                MemoryOperation(
                    code=MemoryOperation.Code.LOAD_MEMORY,
                    right=RB,
                    address=right.location,
                ),
                BinaryOperation(code=operation_type, left=RB),
            )

    def translate_output(self) -> None:
        itoc: Value = Value(value=48)
        self.extend_result(  # handling zero
            JumpOperation(code=JumpOperation.Code.JUMP_ZERO, offset=1),
            JumpOperation(code=JumpOperation.Code.JUMP_BECAUSE, offset=3),
            BinaryOperation(code=BinaryOperation.Code.MATH_ADD, left=itoc),
            MemoryOperation(
                code=MemoryOperation.Code.SAVE_MEMORY,
                address=OUTPUT_ADDRESS,
            ),
            JumpOperation(code=JumpOperation.Code.JUMP_BECAUSE, offset=18),
        )
        self.extend_result(  # handling negative
            JumpOperation(code=JumpOperation.Code.JUMP_NEGATIVE, offset=1),
            JumpOperation(code=JumpOperation.Code.JUMP_BECAUSE, offset=3),
            BinaryOperation(
                code=BinaryOperation.Code.MOVE_DATA,
                right=RB,
                left=Value(value=45),
            ),
            MemoryOperation(
                code=MemoryOperation.Code.SAVE_MEMORY,
                right=RB,
                address=OUTPUT_ADDRESS,
            ),
            BinaryOperation(
                code=BinaryOperation.Code.MATH_MUL,
                left=Value(value=-1),
            ),
        )
        self.extend_result(  # null-termination
            BinaryOperation(
                code=BinaryOperation.Code.MOVE_DATA,
                right=RB,
                left=Value(value=0),
            ),
            StackOperation(code=StackOperation.Code.PUSH, right=RB),
        )
        self.extend_result(  # main loop
            BinaryOperation(
                code=BinaryOperation.Code.MOVE_DATA,
                right=RB,
                left=RA,
            ),
            JumpOperation(code=JumpOperation.Code.JUMP_ZERO, offset=5),
            BinaryOperation(
                code=BinaryOperation.Code.MATH_MOD,
                right=RB,
                left=Value(value=10),
            ),
            BinaryOperation(
                code=BinaryOperation.Code.MATH_ADD,
                right=RB,
                left=itoc,
            ),
            StackOperation(code=StackOperation.Code.PUSH, right=RB),
            BinaryOperation(
                code=BinaryOperation.Code.MATH_DIV,
                left=Value(value=10),
            ),
            JumpOperation(code=JumpOperation.Code.JUMP_BECAUSE, offset=-7),
        )
        self.extend_result(  # printing loop
            StackOperation(code=StackOperation.Code.GRAB),
            JumpOperation(code=JumpOperation.Code.JUMP_ZERO, offset=2),
            MemoryOperation(
                code=MemoryOperation.Code.SAVE_MEMORY,
                address=OUTPUT_ADDRESS,
            ),
            JumpOperation(code=JumpOperation.Code.JUMP_BECAUSE, offset=-4),
        )

    def translate_command(self) -> None:
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
            case "output":
                self.translate_argument()
                self.translate_output()
            case "assign":
                var_name = self.reader.next().text
                location = self.variables.register(var_name)
                self.translate_argument(
                    MemoryOperation(
                        code=MemoryOperation.Code.SAVE_MEMORY,
                        address=location,
                    )
                )
            case "if":
                skip_operation, skip_jump_index = self.translate_construct()
                skip_operation.offset = len(self.result) - skip_jump_index
            case "loop":
                condition_start: int = len(self.result)
                skip_operation, skip_jump_index = self.translate_construct()
                self.extend_result(
                    JumpOperation(offset=condition_start - len(self.result) - 1)
                )
                skip_operation.offset = len(self.result) - skip_jump_index
            case _:
                raise TranslationError(f"Unknown command: '{header}'")

        self.check_closed_bracket()

    def translate_valuable(self) -> None:
        header = self.reader.next_expression().text[1:]

        if header == "input":
            self.extend_result(
                MemoryOperation(
                    code=MemoryOperation.Code.LOAD_MEMORY,
                    address=INPUT_ADDRESS,
                )
            )
        else:
            operation_type = OPERATOR_TO_CODE.get(header)
            if operation_type is None:
                raise TranslationError(f"Unknown operation: '{header}'")
            self.translate_operation(operation_type)
        self.check_closed_bracket()

    def translate_blocks(self, allow_quit: bool = False) -> None:
        while self.reader.has_next():
            if allow_quit and self.reader.current_or_closing().is_closing:
                return
            self.translate_command()
