from pydantic import BaseModel

from common.operations import (
    BinaryOperation,
    JumpOperation,
)


class ComparatorData(BaseModel):
    jump: JumpOperation.Code
    command: BinaryOperation.Code = BinaryOperation.Code.COMPARE
    negated: bool


class ComparatorTemplate(BaseModel):
    zero: bool
    reversed: bool = False
    negated: bool

    @property
    def data(self) -> ComparatorData:
        return ComparatorData(
            jump=JumpOperation.Code.JUMP_ZERO
            if self.zero
            else JumpOperation.Code.JUMP_NEGATIVE,
            command=BinaryOperation.Code.COMPARE_REVERSE
            if self.reversed
            else BinaryOperation.Code.COMPARE,
            negated=self.negated,
        )


# (> a b) -> (!jn (comp b a)) -> jn +1; jb +skip
# (>= a b) -> (jn (comp a b)) -> jn +skip
# (= a b) -> (!jz (comp a b)) -> jz +1; jb +skip
# (<= a b) -> (jn (comp b a)) -> jn +skip
# (< a b) -> (!jn (comp a b)) -> jn +1; jb +skip
# (!= a b) -> (jz (comp a b)) -> jn +skip
SYMBOL_TO_COMPARATOR: dict[str, ComparatorTemplate] = {
    ">=": ComparatorTemplate(zero=False, reversed=False, negated=False),
    "<": ComparatorTemplate(zero=False, reversed=False, negated=True),
    "<=": ComparatorTemplate(zero=False, reversed=True, negated=False),
    ">": ComparatorTemplate(zero=False, reversed=True, negated=True),
    "=": ComparatorTemplate(zero=True, negated=True),
    "!=": ComparatorTemplate(zero=True, negated=True),
}
