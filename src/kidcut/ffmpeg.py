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


def _run_filter(mkv_path: str, filter_graph: str, extra_args: str, output_path: str) -> None:
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        fp = f.name
        f.write(filter_graph)
    try:
        if os.name == "nt":
            ps = f'$f = Get-Content "{fp}" -Raw; ffmpeg -y -i "{mkv_path}" -filter_complex $f {extra_args} "{output_path}"'
            subprocess.run(["powershell", "-Command", ps], check=True, capture_output=True, text=True)
        else:
            with open(fp) as f:
                filter_str = f.read()
            cmd = (["ffmpeg", "-y", "-i", mkv_path, "-filter_complex", filter_str]
                   + extra_args.split() + [output_path])
            subprocess.run(cmd, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"ffmpeg error: {e.stderr[:2000]}")
    finally:
        os.unlink(fp)


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

    filter_parts = []
    cursor = 0.0
    idx = 0
    for start, end in cut_ranges:
        clip_end = max(0.0, start - margin)
        if clip_end > cursor + 0.1:
            filter_parts.append(
                f"[0:v]trim=start={cursor:.3f}:end={clip_end:.3f},setpts=N/FRAME_RATE/TB[v{idx}];"
                f"[0:a]atrim=start={cursor:.3f}:end={clip_end:.3f},asetpts=PTS-STARTPTS[a{idx}];"
            )
            idx += 1
        cursor = max(cursor, end + margin)
    if duration - cursor > 0.1:
        filter_parts.append(
            f"[0:v]trim=start={cursor:.3f}:end={duration:.3f},setpts=N/FRAME_RATE/TB[v{idx}];"
            f"[0:a]atrim=start={cursor:.3f}:end={duration:.3f},asetpts=PTS-STARTPTS[a{idx}];"
        )
        idx += 1

    if idx == 0:
        return
    if idx == 1:
        subprocess.run(
            ["ffmpeg", "-y", "-i", mkv_path,
             "-vf", f"trim=start={cursor:.3f}:end={duration:.3f},setpts=PTS-STARTPTS",
             "-af", f"atrim=start={cursor:.3f}:end={duration:.3f},asetpts=PTS-STARTPTS",
             "-c:v", "libx264", "-preset", "ultrafast", "-crf", "23",
             "-c:a", "aac", "-b:a", "640k",
             output_path],
            check=True, capture_output=True, text=True,
        )
        return

    segment_links = "".join(f"[v{i}][a{i}]" for i in range(idx))
    filter_parts.append(f"{segment_links}concat=n={idx}:v=1:a=1[outv][outa]")
    filter_graph = " ".join(filter_parts)

    _run_filter(mkv_path, filter_graph,
        "-map [outv] -map [outa] -c:v libx264 -preset ultrafast -crf 23 -c:a aac -b:a 640k",
        output_path)