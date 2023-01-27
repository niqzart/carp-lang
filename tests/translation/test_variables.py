import pytest

from common.errors import TranslationError
from translator.variables import VariableIndex


@pytest.fixture
def variables() -> VariableIndex:
    return VariableIndex()


@pytest.mark.parametrize(
    ("name", "valid"),
    [
        pytest.param("1000", False, id="numbers-invalid"),
        pytest.param("var-var", False, id="dashes-invalid"),
        pytest.param("VAR", False, id="capital-invalid"),
        pytest.param("var", True, id="normal"),
        pytest.param("var_var", True, id="snaked"),
    ],
)
def test_variables(variables, name: str, valid: bool):
    if valid:
        with pytest.raises(TranslationError) as e:
            variables.read(name)
        assert str(e.value) == f"Variable '{name}' is not defined"

        registered = variables.register(name)
        value = variables.read(name)
        assert registered == value.location
    else:
        with pytest.raises(TranslationError) as e:
            variables.read(name)
        assert str(e.value) == f"Unsupported variable name: '{name}'"

        with pytest.raises(TranslationError) as e:
            variables.register(name)
        assert str(e.value) == f"Unsupported variable name: '{name}'"
