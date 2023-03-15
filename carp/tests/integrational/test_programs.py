import subprocess
from pathlib import Path

import pytest
from pytest_golden.plugin import (  # type: ignore
    GoldenTestFixtureFactory,
    GoldenTestFixture,
)

EXAMPLE_FOLDER: Path = Path("examples")


def check_output(*args: str) -> str:
    return (
        subprocess.check_output(["python", "carp", *args], cwd="./..")
        .decode("utf-8")
        .strip()
        .replace("\r\n", "\n")
    )


@pytest.mark.skip()
@pytest.mark.parametrize(
    ("program_name", "file_in", "expected"),
    [
        pytest.param("hello", False, "Hello World", id="hello"),
        pytest.param("cat", True, None, id="cat"),
        pytest.param("prob2", False, "4613732", id="prob2"),
    ],
)
def test_one(
    golden: GoldenTestFixtureFactory,
    program_name: str,
    file_in: bool,
    expected: str | None,
) -> None:
    gold: GoldenTestFixture = golden.open(Path("programs.yml"))

    source_path: Path = EXAMPLE_FOLDER / f"{program_name}.carp"
    executable_path: Path = EXAMPLE_FOLDER / f"{program_name}.curp"
    clog_path: Path = EXAMPLE_FOLDER / f"{program_name}.clog"
    input_path: Path = EXAMPLE_FOLDER / f"{program_name}.in.txt"

    check_output("translate", str(source_path))

    execute_command = ["execute", str(executable_path)]
    if file_in:
        execute_command.append(str(input_path))

    if expected is None:
        path: Path = ".." / input_path
        with path.open(encoding="utf-8") as f:
            expected = f.read() + "\0"

    assert check_output(*execute_command) == expected

    with (".." / executable_path).open(encoding="utf-8") as f:
        assert f.read() == gold.out[f"{program_name}_curp"]

    with (".." / clog_path).open(encoding="utf-8") as f:
        assert f.read() == gold.out[f"{program_name}_clog"]
