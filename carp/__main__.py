import json
from pathlib import Path
from typing import Optional

from typer import Typer, FileText, Argument, Option

from common.errors import TranslationError
from common.operations import Operation
from translator.parser import ParserError
from translator.reader import Reader
from translator.translator import Translator

app = Typer()


@app.command()
def translate(
    input_file: FileText = Argument(..., help="Path to the source file"),
    output_path: Optional[Path] = Argument(None, help="Path for the output"),
    save_parsed: bool = Option(False, help="Saves parsed symbols to a file as well"),
) -> None:
    input_path = input_file.name.rpartition(".")[0]
    if output_path is None:
        output_path = input_path + ".curp"

    code = input_file.read()
    try:
        reader = Reader(code)
        print("Parsing successful")
        if save_parsed:
            parsed = [symbol.dict() for symbol in reader.symbols]
            with open(input_path + ".cpar", "w") as f:
                json.dump(parsed, f, indent=2)
            print("Parsing result saved")
    except ParserError as e:
        print(str(e))

    try:
        translator: Translator = Translator(reader=reader)
        translator.parse_blocks()
        compiled = [operation.dict() for operation in translator.result]

        with open(output_path, "w") as f:
            json.dump(compiled, f, indent=2)
        print("Compilation successful")
        print(f"Result has been saved to {output_path}")
    except TranslationError as e:
        translator.reader.back()
        symbol = translator.reader.current_or_closing()
        print(
            f"Translation error occurred at "
            f"{symbol.line}:{symbol.char} "
            f"({symbol.text}): {e}"
        )
        raise e


@app.command()
def generate_schema(output_path: Optional[Path] = Argument(None)):
    if output_path is None:
        output_path = "docs/operation-schema.json"
    with open(output_path, "w") as f:
        json.dump(Operation.schema(), f, indent=2)


if __name__ == "__main__":
    app()
