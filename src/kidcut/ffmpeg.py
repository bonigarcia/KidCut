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
        raise RuntimeError("ffmpeg not found.")


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


def cut_scenes(mkv_path: str, scenes_to_cut: list[CutScene], output_path: str, margin: float = 5.0) -> None:
    if not scenes_to_cut:
        Path(output_path).write_bytes(Path(mkv_path).read_bytes())
        return

    MARGIN = 5.0

    probe = subprocess.run(
        ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", mkv_path],
        capture_output=True, text=True, check=True,
    )
    duration = float(json.loads(probe.stdout)["format"]["duration"])

    cut_ranges = [(get_timestamp_seconds(s.start), get_timestamp_seconds(s.end)) for s in scenes_to_cut]
    cut_ranges.sort()

    segments: list[tuple[float, float]] = []
    cursor = 0.0
    for start, end in cut_ranges:
        clip_end = max(0.0, start - margin)
        if clip_end > cursor + 0.5:
            segments.append((cursor, clip_end))
        cursor = min(duration, end + margin)
    if duration - cursor > 0.5:
        segments.append((cursor, duration))

    if not segments:
        raise RuntimeError("No clean segments remain.")

    filter_parts = []
    for i, (seg_start, seg_end) in enumerate(segments):
        filter_parts.append(
            f"[0:v]trim=start={seg_start:.3f}:end={seg_end:.3f},setpts=N/FRAME_RATE/TB[v{i}];"
            f"[0:a]atrim=start={seg_start:.3f}:end={seg_end:.3f},asetpts=N/SR/TB[a{i}];"
        )
    segment_links = "".join(f"[v{i}][a{i}]" for i in range(len(segments)))
    filter_parts.append(f"{segment_links}concat=n={len(segments)}:v=1:a=1[outv][outa]")
    filter_graph = " ".join(filter_parts)

    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        filter_path = f.name
        f.write(filter_graph)

    try:
        ps_cmd = (
            f'$f = Get-Content "{filter_path}" -Raw; '
            f'ffmpeg -y -i "{mkv_path}" '
            f'-filter_complex $f '
            f'-map "[outv]" -map "[outa]" '
            f'-preset ultrafast -crf 23 "{output_path}"'
        )
        subprocess.run(["powershell", "-Command", ps_cmd], check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"ffmpeg error: {e.stderr[:3000]}")
    finally:
        os.unlink(filter_path)