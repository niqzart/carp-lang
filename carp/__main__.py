import json
from pathlib import Path
from typing import Optional

from pydantic import parse_raw_as
from typer import Typer, FileText, Argument, Option

from common.errors import TranslationError
from common.operations import Operation
from executor.control import ControlUnit
from executor.wiring import DataPath
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
            with open(input_path + ".cpar", "w", encoding="utf-8") as f:
                json.dump(parsed, f, indent=2)
            print(f"Parsing result saved to {input_path}.cpar")
    except ParserError as e:
        print(str(e))

    try:
        translator: Translator = Translator(reader=reader)
        translator.translate_blocks()
        compiled = [operation.dict() for operation in translator.result]

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(compiled, f, indent=2)
        print("Compilation successful")
        print(f"Result has been saved to {output_path}")
    except TranslationError as e:
        translator.reader.back()
        symbol = translator.reader.current_or_closing()
        print(
            "Translation error occurred at "
            + f"{symbol.line}:{symbol.char} "
            + f"({symbol.text}): {e}"
        )
        raise e


@app.command()
def execute(
    instructions: FileText = Argument(..., help="Path to the compiled code file"),
    input_string: Optional[FileText] = Argument(None, help="Path for the input data"),
    output_path: Optional[Path] = Argument(None, help="Path for the output data"),
    save_log: bool = Option(False, help="Saves the execution logs to a file"),
) -> None:
    operations: list[Operation] = parse_raw_as(list[Operation], instructions.read())
    if input_string is None:
        input_data = []
    else:
        input_data = [ord(char) for char in input_string.read()]

    data_path = DataPath(
        data_memory_size=100,
        instruction_memory=operations,
        input_data=input_data,
    )
    control = ControlUnit(data_path)
    try:
        control.main()
        result = "".join(chr(i) for i in data_path.get_output())
        if output_path:
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(result)
        else:
            print(result)
    except RuntimeError as e:
        control.save_state()
        print(f"Error: {e}")
        print("Run with --save-log to debug this")

    if save_log:
        log_path = instructions.name.rpartition(".")[0] + ".clog"
        with open(log_path, "w", encoding="utf-8") as f:
            json.dump([record.dict() for record in control.log], f, indent=2)
        print(f"Execution log saved to {log_path}")


@app.command()
def generate_schema(output_path: Optional[Path] = Argument(None)) -> None:
    if output_path is None:
        output_path = "docs/operation-schema.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(Operation.schema(), f, indent=2)


if __name__ == "__main__":
    app()
