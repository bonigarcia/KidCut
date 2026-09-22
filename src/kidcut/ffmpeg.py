import json
import os
import shutil
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
    tracks: list[MkvTrack] = []
    for stream in json.loads(result.stdout).get("streams", []):
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
    ts = ts.split(" --> ")[0].strip()
    parts = ts.replace(",", ".").split(":")
    return float(parts[0]) * 3600 + float(parts[1]) * 60 + float(parts[2])


def _fmt(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    return f"{h:02d}:{m:02d}:{s:06.3f}"


def cut_scenes(mkv_path: str, scenes_to_cut: list[CutScene], output_path: str, margin: float = 0.0) -> None:
    if not scenes_to_cut:
        Path(output_path).write_bytes(Path(mkv_path).read_bytes())
        return

    probe = subprocess.run(
        ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", mkv_path],
        capture_output=True, text=True, check=True,
    )
    duration = float(json.loads(probe.stdout)["format"]["duration"])

    cut_ranges = [(get_timestamp_seconds(s.start), get_timestamp_seconds(s.end)) for s in scenes_to_cut]
    cut_ranges.sort()

    tmpdir = Path(tempfile.mkdtemp())
    try:
        concat_lines = []
        cursor = 0.0
        for start, end in cut_ranges:
            clip_end = max(0.0, start - margin)
            if clip_end > cursor + 0.1:
                seg = tmpdir / f"seg{len(concat_lines):04d}.mkv"
                subprocess.run(
                    ["ffmpeg", "-v", "quiet", "-y", "-ss", _fmt(cursor), "-i", mkv_path,
                     "-t", _fmt(clip_end - cursor), "-c", "copy", "-avoid_negative_ts", "1", str(seg)],
                    check=True,
                )
                concat_lines.append(f"file '{seg}'")
            cursor = max(cursor, end + margin)
        if duration - cursor > 0.1:
            seg = tmpdir / f"seg{len(concat_lines):04d}.mkv"
            subprocess.run(
                ["ffmpeg", "-v", "quiet", "-y", "-ss", _fmt(cursor), "-i", mkv_path,
                 "-t", _fmt(duration - cursor), "-c", "copy", "-avoid_negative_ts", "1", str(seg)],
                check=True,
            )
            concat_lines.append(f"file '{seg}'")

        if not concat_lines:
            return
        if len(concat_lines) == 1:
            shutil.copy(next(tmpdir.iterdir()), output_path)
            return

        concat_txt = tmpdir / "concat.txt"
        concat_txt.write_text("\n".join(concat_lines) + "\n", encoding="utf-8")

        subprocess.run(
            ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_txt),
             "-c:v", "libx264", "-preset", "ultrafast", "-crf", "23",
             "-c:a", "aac", "-b:a", "640k", output_path],
            check=True, capture_output=True, text=True,
        )
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"ffmpeg error: {e.stderr[:2000]}")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)