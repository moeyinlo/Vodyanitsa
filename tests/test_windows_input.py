import pytest

from genshin_midi.windows_input import key_to_virtual_key


def test_letter_key_uses_windows_virtual_key_code():
    assert key_to_virtual_key("q") == 0x51
    assert key_to_virtual_key("M") == 0x4D


def test_non_letter_key_is_rejected():
    with pytest.raises(ValueError):
        key_to_virtual_key("F7")
