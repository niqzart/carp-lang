from contextlib import contextmanager, nullcontext
from typing import Any

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
    Registry,
)
from translator.comparators import (
    SYMBOL_TO_COMPARATOR,
    ComparatorData,
    ComparatorTemplate,
)
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
                return str(argument)
            raise TranslationError("Argument can't be a string")
        if argument.is_digit:
            return int(argument.text)
        return self.variables.read(argument.text)

    def parse_argument(self, allow_strings: bool = False) -> VarDef | str | int | None:
        if self.reader.current().is_expression:
            return None
        return self._parse_argument(self.reader.next(), allow_strings=allow_strings)

    def translate_argument(
        self,
        operation: OperationBase | None = None,
        result_registry: Registry = RA,
        allow_strings: bool = False,
        stack: bool = True,
    ) -> None:
        """
        Extract argument from reader and adds its operations to result

        :param operation: an operation to execute after
        :param result_registry: registry to put the result into
        :param allow_strings: use if argument is allowed to be a string
        :param stack: will be passed to :py:meth:`translate_valuable` if needed
        :return: None
        """
        argument = self.parse_argument(allow_strings=allow_strings)
        if allow_strings and isinstance(argument, str):
            for character in argument:
                self.extend_result(
                    BinaryOperation(
                        code=BinaryOperation.Code.MOVE_DATA,
                        right=result_registry,
                        left=Value(value=ord(character)),
                    )
                )
                if operation is not None:
                    self.extend_result(operation)
            return
        if argument is None:
            self.translate_valuable(result_registry=result_registry, stack=stack)
        elif isinstance(argument, int):
            self.extend_result(
                BinaryOperation(
                    code=BinaryOperation.Code.MOVE_DATA,
                    right=result_registry,
                    left=Value(value=argument),
                )
            )
        elif isinstance(argument, VarDef):
            self.extend_result(
                MemoryOperation(
                    code=MemoryOperation.Code.LOAD_MEMORY,
                    right=result_registry,
                    address=argument.location,
                )
            )
        if operation is not None:
            self.extend_result(operation)

    @contextmanager
    def stack_save(self, reg: Registry) -> Any:
        """
        Helper context manager to temporarily save value of a registry in stack

        :param reg: the :py:class:`Registry` to save
        """
        self.extend_result(StackOperation(code=StackOperation.Code.PUSH, right=reg))
        yield
        self.extend_result(StackOperation(code=StackOperation.Code.GRAB, right=reg))

    def translate_operation(
        self,
        operation_type: BinaryOperation.Code,
        result_registry: Registry = RA,
        stack: bool = True,
    ) -> None:
        """
        Translates a binary operation and adds its operations to result

        :param operation_type: operation's code
        :param result_registry: registry to put the result into
          the other one will be used as a buffer with stack-protection
        :param stack: if True, the initial buffer's value will be saved
        :return: None
        """
        self.translate_argument(result_registry=result_registry)
        buffer_registry: Registry = RB if result_registry is RA else RA

        with self.stack_save(buffer_registry) if stack else nullcontext():
            while not self.reader.current_or_closing().is_closing:
                self.translate_argument(result_registry=buffer_registry)
                self.extend_result(
                    BinaryOperation(
                        code=operation_type, right=result_registry, left=buffer_registry
                    )
                )

    def translate_output(self, registry: Registry) -> None:
        """
        Translates the output operation
        """

        buffer_registry: Registry = RB if registry is RA else RA

        itoc: Value = Value(value=48)
        self.extend_result(
            StackOperation(code=StackOperation.Code.PUSH, right=registry),
            BinaryOperation(
                code=BinaryOperation.Code.MOVE_DATA, right=registry, left=registry
            ),
        )
        self.extend_result(  # handling zero
            JumpOperation(code=JumpOperation.Code.JUMP_ZERO, offset=1),
            JumpOperation(code=JumpOperation.Code.JUMP_BECAUSE, offset=3),
            BinaryOperation(
                code=BinaryOperation.Code.MATH_ADD, right=registry, left=itoc
            ),
            MemoryOperation(
                code=MemoryOperation.Code.SAVE_MEMORY,
                address=OUTPUT_ADDRESS,
                right=registry,
            ),
            JumpOperation(code=JumpOperation.Code.JUMP_BECAUSE, offset=18),
        )
        self.extend_result(  # handling negative
            JumpOperation(code=JumpOperation.Code.JUMP_NEGATIVE, offset=1),
            JumpOperation(code=JumpOperation.Code.JUMP_BECAUSE, offset=3),
            BinaryOperation(
                code=BinaryOperation.Code.MOVE_DATA,
                right=buffer_registry,
                left=Value(value=45),
            ),
            MemoryOperation(
                code=MemoryOperation.Code.SAVE_MEMORY,
                right=buffer_registry,
                address=OUTPUT_ADDRESS,
            ),
            BinaryOperation(
                code=BinaryOperation.Code.MATH_MUL,
                left=Value(value=-1),
                right=registry,
            ),
        )
        self.extend_result(  # null-termination
            BinaryOperation(
                code=BinaryOperation.Code.MOVE_DATA,
                right=buffer_registry,
                left=Value(value=0),
            ),
            StackOperation(code=StackOperation.Code.PUSH, right=buffer_registry),
        )
        self.extend_result(  # main loop
            BinaryOperation(
                code=BinaryOperation.Code.MOVE_DATA,
                right=buffer_registry,
                left=registry,
            ),
            JumpOperation(code=JumpOperation.Code.JUMP_ZERO, offset=5),
            BinaryOperation(
                code=BinaryOperation.Code.MATH_MOD,
                right=buffer_registry,
                left=Value(value=10),
            ),
            BinaryOperation(
                code=BinaryOperation.Code.MATH_ADD,
                right=buffer_registry,
                left=itoc,
            ),
            StackOperation(code=StackOperation.Code.PUSH, right=buffer_registry),
            BinaryOperation(
                code=BinaryOperation.Code.MATH_DIV,
                left=Value(value=10),
                right=registry,
            ),
            JumpOperation(code=JumpOperation.Code.JUMP_BECAUSE, offset=-7),
        )
        self.extend_result(  # printing loop
            StackOperation(code=StackOperation.Code.GRAB, right=registry),
            JumpOperation(code=JumpOperation.Code.JUMP_ZERO, offset=2),
            MemoryOperation(
                code=MemoryOperation.Code.SAVE_MEMORY,
                address=OUTPUT_ADDRESS,
                right=registry,
            ),
            JumpOperation(code=JumpOperation.Code.JUMP_BECAUSE, offset=-4),
        )
        self.extend_result(
            BinaryOperation(
                code=BinaryOperation.Code.MOVE_DATA,
                right=registry,
                left=Value(value=10),
            ),
            MemoryOperation(
                code=MemoryOperation.Code.SAVE_MEMORY,
                address=OUTPUT_ADDRESS,
                right=registry,
            ),
            StackOperation(code=StackOperation.Code.GRAB, right=registry),
        )

    def translate_comparator(
        self,
        data: ComparatorData,
        result_registry: Registry = RA,
        stack: bool = True,
        expressions: bool = False,
        failure: bool = True,
        parse_condition: bool = True,
        additions: list[OperationBase] | None = None,
    ) -> None:
        buffer_registry: Registry = RB if result_registry is RA else RA

        with self.stack_save(buffer_registry) if stack else nullcontext():
            if parse_condition:
                self.translate_operation(
                    data.command, result_registry=result_registry, stack=False
                )
                self.check_closed_bracket()
            else:
                self.reader.back()
                self.translate_argument(result_registry=result_registry, stack=stack)

            jump_operation: JumpOperation = JumpOperation(code=data.jump)
            self.extend_result(jump_operation)
            if data.negated:
                jump_operation = JumpOperation()
                self.extend_result(jump_operation)
            ip_after_condition: int = len(self.result)

            if expressions:
                self.translate_argument(result_registry=result_registry, stack=stack)
            else:
                self.extend_result(
                    BinaryOperation(
                        code=BinaryOperation.Code.MOVE_DATA,
                        right=result_registry,
                        left=Value(value=1),
                    )
                )
            if additions is not None:
                self.extend_result(*additions)
            jump_operation.offset = len(self.result) - ip_after_condition + failure

            if failure:
                jump_operation = JumpOperation()
                self.extend_result(jump_operation)
                ip_after_condition = len(self.result)

                if expressions and not self.reader.current_or_closing().is_closing:
                    self.translate_argument(
                        result_registry=result_registry, stack=stack
                    )
                    jump_operation.offset = len(self.result) - ip_after_condition
                else:
                    self.extend_result(
                        BinaryOperation(
                            code=BinaryOperation.Code.MOVE_DATA,
                            right=result_registry,
                            left=Value(value=0),
                        )
                    )

            if parse_condition:
                self.check_closed_bracket()

    def translate_construct(
        self,
        loop: bool,
        result_registry: Registry = RA,
        stack: bool = True,
    ) -> None:
        condition: Symbol = self.reader.next()
        template: ComparatorTemplate = SYMBOL_TO_COMPARATOR["!="]

        is_condition: bool = (
            condition.is_expression and condition.text[1:] in SYMBOL_TO_COMPARATOR
        )
        if is_condition:
            template = SYMBOL_TO_COMPARATOR[condition.text[1:]]

        condition_start: int = len(self.result)
        jump_operation: JumpOperation = JumpOperation()
        self.translate_comparator(
            data=template.data,
            result_registry=result_registry,
            stack=stack,
            expressions=True,
            additions=[jump_operation] if loop else None,
            failure=not loop,
            parse_condition=is_condition,
        )
        jump_operation.offset = condition_start - len(self.result)

    def translate_valuable(
        self, result_registry: Registry = RA, stack: bool = True
    ) -> None:
        """
        Translates a valuable (any expression)

        :param result_registry:
        :param stack: will be passed to :py:meth:`translate_valuable` if needed
        :return: None
        """
        header = self.reader.next_expression().text[1:]

        match header:
            case "block":
                self.translate_blocks(
                    allow_quit=True, result_registry=result_registry, stack=stack
                )
            case "print":
                self.translate_argument(
                    MemoryOperation(
                        code=MemoryOperation.Code.SAVE_MEMORY,
                        address=OUTPUT_ADDRESS,
                    ),
                    result_registry=result_registry,
                    allow_strings=True,
                    stack=stack,
                )
            case "output":
                self.translate_argument(stack=stack, result_registry=result_registry)
                self.translate_output(result_registry)
            case "assign":
                var_name = self.reader.next().text
                location = self.variables.register(var_name)
                self.translate_argument(
                    MemoryOperation(
                        code=MemoryOperation.Code.SAVE_MEMORY,
                        address=location,
                    ),
                    result_registry=result_registry,
                    stack=stack,
                )
            case "if":
                self.translate_construct(
                    loop=False, result_registry=result_registry, stack=stack
                )
                return
            case "loop":
                self.translate_construct(
                    loop=True, result_registry=result_registry, stack=stack
                )
                return
            case "input":
                self.extend_result(
                    MemoryOperation(
                        code=MemoryOperation.Code.LOAD_MEMORY,
                        right=result_registry,
                        address=INPUT_ADDRESS,
                    )
                )
            case _:
                template = SYMBOL_TO_COMPARATOR.get(header)
                if template is not None:
                    self.translate_comparator(
                        template.data, result_registry=result_registry, stack=stack
                    )
                    return

                operation_type = OPERATOR_TO_CODE.get(header)
                if operation_type is None:
                    raise TranslationError(f"Unknown operation: '{header}'")
                self.translate_operation(
                    operation_type, result_registry=result_registry, stack=stack
                )

        self.check_closed_bracket()

    def translate_blocks(
        self,
        allow_quit: bool = False,
        result_registry: Registry = RA,
        stack: bool = False,
    ) -> None:
        """
        The main translator function to use on code-blocks

        :param allow_quit: only the top-level should be allowed to quit
        :param result_registry:
        :param stack:
        :return: None
        """

        while self.reader.has_next():
            if allow_quit and self.reader.current_or_closing().is_closing:
                return
            self.translate_argument(result_registry=result_registry, stack=stack)
