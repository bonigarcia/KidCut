from kidcut.models import CutScene


def auto_edit(scenes: list[CutScene]) -> list[CutScene]:
    return scenes


def manual_edit(scenes: list[CutScene], confirm_fn) -> list[CutScene]:
    kept: list[CutScene] = []
    for scene in scenes:
        choice = confirm_fn(
            f"[{scene.start} \u2192 {scene.end}] {scene.reason}",
            choices=["Cut", "Keep"],
            default="Cut",
        )
        if choice is None:
            raise KeyboardInterrupt
        if choice == "Cut":
            kept.append(scene)
    return kept
