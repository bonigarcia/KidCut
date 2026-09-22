import json
import os
import subprocess
import tempfile
from pathlib import Path

from kidcut.models import CutScene, MkvTrack


def check_binary() -> None:
    try:
        subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True)
    except (FileNotFoundError, subprocess.CalledProcessError):
        raise RuntimeError("ffmpeg not found. Install ffmpeg and ensure it is in your PATH.")


def probe_tracks(mkv_path: str) -> list[MkvTrack]:
    result = subprocess.run(
        ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_streams", mkv_path],
        capture_output=True, text=True, check=True,
    )
    data = json.loads(result.stdout)
    tracks: list[MkvTrack] = []
    for stream in data.get("streams", []):
        index = stream.get("index", 0)
        codec_type = stream.get("codec_type", "")
        language = stream.get("tags", {}).get("language", "und")
        default = stream.get("disposition", {}).get("default", 0) == 1
        codec = stream.get("codec_name", "")
        tracks.append(MkvTrack(index=index, kind=codec_type, language=language, default=default, codec=codec))
    return tracks


def extract_subtitles(mkv_path: str, track_index: int) -> str:
    result = subprocess.run(
        ["ffmpeg", "-v", "quiet", "-y", "-i", mkv_path, "-map", f"0:{track_index}", "-f", "srt", "-"],
        capture_output=True, check=True,
    )
    return result.stdout.decode("utf-8", errors="replace")


def get_timestamp_seconds(ts: str) -> float:
    parts = ts.replace(",", ".").split(":")
    h, m, s = float(parts[0]), float(parts[1]), float(parts[2])
    return h * 3600 + m * 60 + s


def cut_scenes(mkv_path: str, scenes_to_cut: list[CutScene], output_path: str) -> None:
    if not scenes_to_cut:
        Path(output_path).write_bytes(Path(mkv_path).read_bytes())
        return

    MARGIN = 0.2

    probe = subprocess.run(
        ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", mkv_path],
        capture_output=True, text=True, check=True,
    )
    duration = float(json.loads(probe.stdout)["format"]["duration"])

    cut_ranges = [(get_timestamp_seconds(s.start), get_timestamp_seconds(s.end)) for s in scenes_to_cut]
    cut_ranges.sort()

    select_terms = []
    cursor = 0.0
    for start, end in cut_ranges:
        if start > cursor + MARGIN:
            select_terms.append(f"between(t,{cursor:.1f},{start:.3f})")
        cursor = max(cursor, end)
    if duration - cursor > MARGIN:
        select_terms.append(f"between(t,{cursor:.1f},{duration:.3f})")

    if not select_terms:
        raise RuntimeError("No clean segments remain.")

    select_expr = "+".join(select_terms)
    filter_graph = (
        f"select='{select_expr}',setpts=PTS-STARTPTS[v];"
        f"aselect='{select_expr}',asetpts=PTS-STARTPTS[a]"
    )

    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        filter_path = f.name
        f.write(filter_graph)

    try:
        subprocess.run(
            f'set /p filter=<"{filter_path}" && ffmpeg -y -i "{mkv_path}" '
            f'-filter_complex "%filter%" -map "[v]" -map "[a]" '
            f'-preset ultrafast -crf 23 "{output_path}"',
            shell=True, check=True, capture_output=True, text=True,
        )
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"ffmpeg error: {e.stderr[:1500]}")
    finally:
        os.unlink(filter_path)
