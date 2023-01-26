import json
from pathlib import Path
from typing import Optional

from pydantic import parse_raw_as
from typer import Typer, FileText, Argument

from common.errors import TranslationError
from common.operations import (
    BinaryOperation,
    StackOperation,
    JumpOperation,
    MemoryOperation,
    Operation,
)
from translator.parser import ParserError
from translator.reader import Reader
from translator.translator import Translator

app = Typer()


@app.command()
def translate(
    input_file: FileText,
    output_path: Optional[Path] = Argument(None),
    save_parsed: bool = False,
) -> None:
    input_path = input_file.name.rpartition(".")[0]
    if output_path is None:
        output_path = input_path + ".curp"

    code = input_file.read()


@app.command()
def generate_schema(output_path: Optional[Path] = Argument(None)):
    if output_path is None:
        output_path = "docs/operation-schema.json"
    with open(output_path, "w") as f:
        json.dump(Operation.schema(), f, indent=2)


if __name__ == "__main__":
    app()
