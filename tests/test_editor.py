from kidcut.editor import auto_edit, manual_edit
from kidcut.models import CutScene


def test_auto_edit_returns_all_scenes():
    scenes = [CutScene(start="00:01", end="00:02", reason="Violence")]
    assert auto_edit(scenes) == scenes


def test_manual_edit_keeps_only_cut_scenes():
    scenes = [
        CutScene(start="00:01", end="00:02", reason="Drugs"),
        CutScene(start="00:03", end="00:04", reason="Sex"),
        CutScene(start="00:05", end="00:06", reason="Violence"),
    ]
    called = []

    def confirm_fn(message, choices, default):
        called.append(message)
        return "Cut"

    result = manual_edit([scenes[0], scenes[2]], confirm_fn)
    assert len(result) == 2
    assert len(called) == 2


def test_manual_edit_empty_scenes():
    def confirm_fn(message, choices, default):
        return "Cut"
    assert manual_edit([], confirm_fn) == []
