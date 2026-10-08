import pytest

from genshin_midi.windows_input import (
    KEYEVENTF_KEYUP,
    WindowsKeySink,
    key_to_virtual_key,
)


def test_letter_key_uses_windows_virtual_key_code():
    assert key_to_virtual_key("q") == 0x51
    assert key_to_virtual_key("M") == 0x4D


def test_non_letter_key_is_rejected():
    with pytest.raises(ValueError):
        key_to_virtual_key("F7")


class FakeUser32:
    def __init__(self, results):
        self.results = iter(results)
        self.calls = []

    def SendInput(self, count, inputs, size):
        self.calls.append(tuple(
            (inputs[index].ki.wVk, inputs[index].ki.dwFlags)
            for index in range(count)
        ))
        return next(self.results)


def test_key_events_sends_a_chord_as_one_input_batch():
    sink = WindowsKeySink.__new__(WindowsKeySink)
    sink._user32 = FakeUser32([3])

    sink.key_events([("Q", True), ("W", True), ("Q", False)])

    assert sink._user32.calls == [
        ((0x51, 0), (0x57, 0), (0x51, KEYEVENTF_KEYUP))
    ]


def test_partial_key_down_batch_releases_inserted_keys_before_raising():
    sink = WindowsKeySink.__new__(WindowsKeySink)
    sink._user32 = FakeUser32([1, 1])

    with pytest.raises(OSError, match="accepted 1 of 2"):
        sink.key_events([("Q", True), ("W", True)])

    assert sink._user32.calls == [
        ((0x51, 0), (0x57, 0)),
        ((0x51, KEYEVENTF_KEYUP),),
    ]
