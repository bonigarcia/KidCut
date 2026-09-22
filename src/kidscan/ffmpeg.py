import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from kidscan.models import CutScene, MkvTrack


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


def _format_ts(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    return f"{h:02d}:{m:02d}:{s:06.3f}"


def _find_keyframes_before(mkv_path: str, timestamp: float, window: float = 30.0) -> list[float]:
    start = max(0, timestamp - window)
    result = subprocess.run(
        ["ffprobe", "-v", "quiet", "-select_streams", "v", "-show_frames",
         "-show_entries", "frame=pkt_pts_time,pict_type",
         "-read_intervals", f"{_format_ts(start)}%+{window}",
         "-of", "csv=p=0", mkv_path],
        capture_output=True, text=True, check=True,
    )
    keyframes = []
    for line in result.stdout.strip().splitlines():
        parts = line.split(",")
        if len(parts) >= 2 and parts[1] == "I":
            try:
                pts = float(parts[0])
                if pts < timestamp - 0.01:
                    keyframes.append(pts)
            except ValueError:
                continue
    return keyframes


def _find_keyframes_after(mkv_path: str, timestamp: float, window: float = 30.0) -> list[float]:
    result = subprocess.run(
        ["ffprobe", "-v", "quiet", "-select_streams", "v", "-show_frames",
         "-show_entries", "frame=pkt_pts_time,pict_type",
         "-read_intervals", f"{_format_ts(timestamp)}%+{window}",
         "-of", "csv=p=0", mkv_path],
        capture_output=True, text=True, check=True,
    )
    keyframes = []
    for line in result.stdout.strip().splitlines():
        parts = line.split(",")
        if len(parts) >= 2 and parts[1] == "I":
            try:
                pts = float(parts[0])
                if pts > timestamp + 0.01:
                    keyframes.append(pts)
            except ValueError:
                continue
    return keyframes


def _snap_to_keyframes(mkv_path: str, cut_ranges: list[tuple[float, float]], duration: float) -> list[tuple[float, float]]:
    segments: list[tuple[float, float]] = []
    cursor = 0.0
    for start, end in cut_ranges:
        kfs_before = _find_keyframes_before(mkv_path, start)
        if len(kfs_before) >= 2:
            segment_end = kfs_before[-2]  # ponytail: use 2nd-to-last keyframe; -t with -c copy snaps to next keyframe
        elif len(kfs_before) == 1:
            segment_end = max(0, kfs_before[0] - 2.0)
        else:
            segment_end = max(0, start - 2.0)
        if segment_end > cursor + 0.5:
            segments.append((cursor, segment_end))
        kfs_after = _find_keyframes_after(mkv_path, end)
        if kfs_after:
            cursor = kfs_after[0]
        elif kfs_before:
            cursor = kfs_before[-1] + 1.0
            kfs_after2 = _find_keyframes_after(mkv_path, cursor, window=30.0)
            cursor = kfs_after2[0] if kfs_after2 else min(duration, cursor)
        else:
            cursor = min(duration, end + 2.0)
    if duration - cursor > 0.5:
        segments.append((cursor, duration))
    return segments


def _build_segments(mkv_path: str, scenes_to_cut: list[CutScene]) -> list[tuple[float, float]]:
    probe = subprocess.run(
        ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", mkv_path],
        capture_output=True, text=True, check=True,
    )
    duration = float(json.loads(probe.stdout)["format"]["duration"])

    cut_ranges = [(get_timestamp_seconds(s.start), get_timestamp_seconds(s.end)) for s in scenes_to_cut]
    cut_ranges.sort()

    return _snap_to_keyframes(mkv_path, cut_ranges, duration)


def _extract_segment(mkv_path: str, start: float, end: float, output_path: str) -> None:
    duration = end - start
    subprocess.run(
        ["ffmpeg", "-v", "quiet", "-y", "-ss", _format_ts(start), "-i", mkv_path, "-t", _format_ts(duration),
         "-c", "copy", "-avoid_negative_ts", "1", output_path],
        check=True,
    )


def cut_scenes(mkv_path: str, scenes_to_cut: list[CutScene], output_path: str) -> None:
    if not scenes_to_cut:
        Path(output_path).write_bytes(Path(mkv_path).read_bytes())
        return

    segments = _build_segments(mkv_path, scenes_to_cut)
    if not segments:
        raise RuntimeError("No clean segments remain after cutting all scenes.")

    tmpdir = Path(tempfile.mkdtemp())
    try:
        concat_lines = []
        for i, (seg_start, seg_end) in enumerate(segments):
            seg_path = tmpdir / f"seg{i:04d}.mkv"
            _extract_segment(mkv_path, seg_start, seg_end, str(seg_path))
            concat_lines.append(f"file '{seg_path}'")

        concat_path = tmpdir / "concat.txt"
        concat_path.write_text("\n".join(concat_lines) + "\n", encoding="utf-8")

        subprocess.run(
            ["ffmpeg", "-v", "quiet", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_path), "-c", "copy", output_path],
            check=True,
        )
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)