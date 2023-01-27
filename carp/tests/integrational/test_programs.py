import subprocess
from pathlib import Path

import pytest

EXAMPLE_FOLDER: Path = Path("examples")


def check_output(*args: str) -> str:
    return (
        subprocess.check_output(["python", "carp", *args], cwd="./..")
        .decode("utf-8")
        .strip()
        .replace("\r\n", "\n")
    )


@pytest.mark.parametrize(
    ("program_name", "file_in", "expected"),
    [
        pytest.param("hello", False, "Hello World", id="hello"),
        pytest.param("cat", True, None, id="cat"),
        pytest.param("prob2", False, "4613732", id="prob2"),
    ],
)
def test_one(program_name: str, file_in: bool, expected: str | None):
    check_output("translate", str(EXAMPLE_FOLDER / f"{program_name}.carp"))

    execute_command = ["execute", str(EXAMPLE_FOLDER / f"{program_name}.curp")]
    if file_in:
        execute_command.append(str(EXAMPLE_FOLDER / f"{program_name}.in.txt"))

    if expected is None:
        path = ".." / EXAMPLE_FOLDER / f"{program_name}.in.txt"
        with open(path, encoding="utf-8") as f:
            expected = f.read() + "\0"

    assert check_output(*execute_command) == expected
