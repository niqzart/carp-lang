from pydantic import BaseModel

from common.operations import Operation


class RegistriesRecord(BaseModel):
    accumulator: int
    buffer: int
    memory_pointer: int
    stack_pointer: int
    instruction_pointer: int
    command_data: Operation | None


class FlagsRecord(BaseModel):
    zero: bool
    negative: bool


class LogRecord(BaseModel):
    registries: RegistriesRecord
    flags: FlagsRecord
    input: int | None = None
    output: int | None = None
