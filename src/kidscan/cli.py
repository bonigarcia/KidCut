import os
from pathlib import Path

import questionary
from rich.console import Console

from kidscan.editor import auto_edit, manual_edit
from kidscan.ffmpeg import check_binary, probe_tracks, extract_subtitles, cut_scenes
from kidscan.models import CutScene
from kidscan.scanner import build_request_completion, analyze_subtitles
from kidscan.subtitle import parse_subtitles
from kidscan.ui import run_with_spinner
from kidscan.vendors import discover_vendors, list_models_for_vendor


def choose_from_options(message: str, choices: list[str], default: str | None = None) -> str | None:
    try:
        return questionary.select(message, choices=choices, default=default).ask()
    except (KeyboardInterrupt, EOFError):
        return None


def choose_text(message: str, default: str | None = None) -> str | None:
    try:
        return questionary.text(message, default=default).ask()
    except (KeyboardInterrupt, EOFError):
        return None


def confirm_cut(message: str, choices: list[str], default: str | None = None) -> str | None:
    try:
        return questionary.select(message, choices=choices, default=default, use_shortcuts=True).ask()
    except (KeyboardInterrupt, EOFError):
        return None


def _find_mkv_path(console: Console) -> str:
    current = Path.home()
    while True:
        items = _list_dir_items(current)
        if not items:
            raise RuntimeError(f"No MKV files or directories in {current}")
        selected = choose_from_options(f"MKV file ({current})", items, default=items[0])
        if selected is None:
            raise KeyboardInterrupt
        if selected == "[..]":
            current = current.parent
        elif selected.startswith("[") and selected.endswith("]"):
            current = current / selected[1:-1]
        else:
            path = str(current / selected)
            if not os.path.isfile(path):
                raise RuntimeError("Selected file not found.")
            return path


def _list_dir_items(current: Path) -> list[str]:
    items = []
    try:
        entries = sorted(current.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
    except PermissionError:
        return items
    if current.parent != current:
        items.append("[..]")
    for entry in entries:
        if entry.name.startswith("."):
            continue
        if entry.is_dir():
            items.append(f"[{entry.name}]")
        elif entry.suffix.lower() == ".mkv":
            items.append(entry.name)
    return items


def _auto_select_subtitle_track(tracks, default_audio_lang: str) -> int | None:
    subtitle_tracks = [t for t in tracks if t.kind == "subtitle" and t.codec in ("subrip", "ass", "ssa", "text")]
    if not subtitle_tracks:
        return None
    matches = [t for t in subtitle_tracks if t.language == default_audio_lang and not t.default]
    if matches:
        return matches[0].index
    non_default = [t for t in subtitle_tracks if not t.default]
    if non_default:
        return non_default[0].index
    return subtitle_tracks[0].index


def _pick_tracks_manually(console: Console, tracks) -> tuple[int, int]:
    audio_choices = [f"Track {t.index} \u2014 audio \u2014 {t.language} ({t.codec})" for t in tracks if t.kind == "audio"]
    sub_choices = [f"Track {t.index} \u2014 subtitles \u2014 {t.language} ({t.codec})" for t in tracks if t.kind == "subtitle"]
    if not sub_choices:
        raise RuntimeError("No text-based subtitle tracks found in this MKV.")

    sel_audio = choose_from_options("Select audio track", audio_choices)
    if sel_audio is None:
        raise KeyboardInterrupt
    audio_idx = int(sel_audio.split("\u2014")[0].replace("Track ", "").strip())

    sel_sub = choose_from_options("Select subtitle track", sub_choices)
    if sel_sub is None:
        raise KeyboardInterrupt
    sub_idx = int(sel_sub.split("\u2014")[0].replace("Track ", "").strip())

    return audio_idx, sub_idx


def _choose_vendor_and_model(console: Console):
    vendors = discover_vendors()
    if not vendors:
        raise RuntimeError("No AI vendors available. Set an API key or start Ollama.")
    vendor_name = choose_from_options("Choose provider", [v.name for v in vendors])
    if vendor_name is None:
        raise KeyboardInterrupt
    vendor = next(v for v in vendors if v.name == vendor_name)
    api_key = os.getenv(vendor.api_key_env) if vendor.api_key_env else None
    models = list_models_for_vendor(vendor_name, api_key=api_key)
    if not models:
        raise RuntimeError(f"No models available for {vendor_name}.")
    model = choose_from_options("Choose model", models)
    if model is None:
        raise KeyboardInterrupt
    return vendor_name, model, api_key


def _choose_edit_mode(console: Console) -> str:
    return choose_from_options(
        "Edit mode",
        ["Automatic (cut all)", "Manual (review each scene)"],
        default="Automatic (cut all)",
    ) or "Automatic (cut all)"


def _get_output_path(mkv_path: str) -> str:
    p = Path(mkv_path)
    return str(p.parent / f"{p.stem}-kidcut{p.suffix}")


def main(argv: list[str] | None = None) -> int:
    console = Console()
    try:
        console.print("[bold]KidCut[/bold] \u2014 AI-powered movie editor for families")
        check_binary()

        mkv_path = _find_mkv_path(console)
        console.print(f"Probing [bold]{mkv_path}[/bold]...")
        tracks = probe_tracks(mkv_path)

        audio_tracks = [t for t in tracks if t.kind == "audio"]
        default_audio = next((t for t in audio_tracks if t.default), audio_tracks[0] if audio_tracks else None)
        default_audio_lang = default_audio.language if default_audio else "und"

        subtitle_idx = _auto_select_subtitle_track(tracks, default_audio_lang)
        if subtitle_idx is None:
            console.print("No matching subtitle track found for default audio language.")
            _, subtitle_idx = _pick_tracks_manually(console, tracks)
        else:
            console.print(f"Auto-selected subtitle track {subtitle_idx} (language matches audio)")

        console.print("Extracting subtitles...")
        raw_subs = run_with_spinner(console, "Extracting subtitles", lambda: extract_subtitles(mkv_path, subtitle_idx))
        subtitle_entries = parse_subtitles(raw_subs)
        if not subtitle_entries:
            raise RuntimeError("No text subtitles found or parsed.")
        console.print(f"Found [bold]{len(subtitle_entries)}[/bold] subtitle entries.")

        vendor_name, model, api_key = _choose_vendor_and_model(console)
        request_completion = build_request_completion(vendor_name, model, api_key=api_key)

        run, scenes = run_with_spinner(
            console, "Analyzing subtitles with AI",
            lambda: analyze_subtitles(subtitle_entries, mkv_path, request_completion, vendor_name, model),
        )
        if not scenes:
            console.print("[green]No inappropriate scenes detected.[/green]")
            return 0
        console.print(f"Found [bold]{len(scenes)}[/bold] scene(s) to review.")

        edit_mode = _choose_edit_mode(console)
        if edit_mode.startswith("Automatic"):
            to_cut = auto_edit(scenes)
        else:
            to_cut = manual_edit(scenes, confirm_cut)

        if not to_cut:
            console.print("[yellow]No scenes selected for cutting. Output unchanged.[/yellow]")
            return 0

        output_path = _get_output_path(mkv_path)
        console.print(f"Cutting [bold]{len(to_cut)}[/bold] scene(s)...")
        run_with_spinner(console, "Cutting scenes", lambda: cut_scenes(mkv_path, to_cut, output_path))
        console.print(f"[green]Done![/green] Output saved to [bold]{output_path}[/bold]")
        return 0
    except KeyboardInterrupt:
        console.print("Cancelled.")
        return 1
    except RuntimeError as e:
        console.print(f"[red]Error:[/red] {e}")
        return 1