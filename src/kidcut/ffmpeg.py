import json
import re
import subprocess
import sys
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


def _show_progress(duration: float, stream) -> None:
    line = ""
    while True:
        chunk = stream.read(4096)
        if not chunk:
            break
        line += chunk
        while "\n" in line:
            l, line = line.split("\n", 1)
            if l.startswith("frame="):
                m = re.search(r"time=(\d+):(\d+):([\d.]+)", l)
                if m:
                    h, min_, s = float(m.group(1)), float(m.group(2)), float(m.group(3))
                    current = h * 3600 + min_ * 60 + s
                    pct = min(current / duration * 100, 100)
                    sys.stdout.write(f"\r\x1b[K[{pct:>3.0f}%] {l}")
                    sys.stdout.flush()
    sys.stdout.write("\n")
    sys.stdout.flush()


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

    keep_segments: list[tuple[float, float]] = []
    cursor = 0.0
    for start, end in cut_ranges:
        clip_end = max(0.0, start - margin)
        if clip_end > cursor + 0.1:
            keep_segments.append((cursor, clip_end))
        cursor = max(cursor, end + margin)
    if duration - cursor > 0.1:
        keep_segments.append((cursor, duration))

    if not keep_segments:
        return

    select_expr = "+".join(f"between(t,{s:.3f},{e:.3f})" for s, e in keep_segments)

    proc = subprocess.Popen(
        ["ffmpeg", "-y",
         "-i", mkv_path,
         "-vf", f"select='{select_expr}',setpts=N/FRAME_RATE/TB",
         "-af", f"aselect='{select_expr}',asetpts=N/SR/TB",
         "-c:v", "libx264", "-preset", "ultrafast", "-crf", "23",
         "-c:a", "aac", "-b:a", "640k",
         output_path],
        stderr=subprocess.PIPE,
        text=True,
    )

    _show_progress(duration, proc.stderr)

    ret = proc.wait()
    if ret != 0:
        raise RuntimeError(f"ffmpeg failed with exit code {ret}.")