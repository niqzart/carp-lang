import pytest

from common.errors import TranslationError
from translator.reader import Reader


def assert_back(reader: Reader) -> None:
    position = reader.position
    reader.back()
    assert reader.position == position - 1
    assert reader.has_next()


@pytest.mark.parametrize(
    ("source", "expression", "closing"),
    [
        pytest.param("hello", False, False, id="normal"),
        pytest.param("(input", True, False, id="expression"),
        pytest.param(")", False, True, id="closing"),
    ],
)
def test_reader(source: str, expression: bool, closing: bool):
    reader = Reader(source)
    assert reader.has_next()

    assert reader.current_or_none().text == source
    assert reader.current_or_closing().text == source

    if closing:
        with pytest.raises(TranslationError) as e:
            reader.current()
        assert str(e.value) == "Unexpected closing symbol"

        with pytest.raises(TranslationError) as e:
            reader.next()
        assert str(e.value) == "Unexpected closing symbol"
        assert_back(reader)

        reader.next_closing()
    elif expression:
        assert reader.next_expression().text == source
    else:
        with pytest.raises(TranslationError) as e:
            reader.next_expression()
        assert str(e.value) == "An expression was expected"
        assert_back(reader)

        assert reader.current().text == source
        assert reader.next().text == source
        assert_back(reader)

        with pytest.raises(TranslationError) as e:
            reader.next_closing()
        assert str(e.value) == "Missing closing bracket"

    assert not reader.has_next()

    with pytest.raises(IndexError):
        reader.current()
    with pytest.raises(IndexError):
        reader.next()

    assert reader.current_or_none() is None
    assert reader.next_or_none() is None
