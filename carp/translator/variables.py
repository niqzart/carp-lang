import re
from typing import Pattern

from pydantic import BaseModel

from common.errors import TranslationError


class VarDef(BaseModel):
    name: str
    location: int


class VariableIndex:
    VARIABLE_REGEX: Pattern[str] = re.compile(r"[a-z_][a-z_0-9]*")

    def __init__(self) -> None:
        self.variables: dict[str, int] = {}
        self.next_location: int = 16

    def bad_name(self, name: str) -> bool:
        return re.fullmatch(self.VARIABLE_REGEX, name) is None

    def register(self, name: str) -> int:
        if self.bad_name(name):
            raise TranslationError(f"Unsupported variable name: '{name}'")
        if name not in self.variables:
            self.variables[name] = self.next_location
            self.next_location += 1
        return self.variables[name]

    def read(self, name: str) -> VarDef:
        if self.bad_name(name):
            raise TranslationError(f"Unsupported variable name: '{name}'")
        location = self.variables.get(name)
        if location is None:
            raise TranslationError(f"Variable '{name}' is not defined")
        return VarDef(name=name, location=location)
