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
        ps = f'$f = Get-Content "{fp}" -Raw; ffmpeg -y -i "{mkv_path}" -filter_complex $f {extra_args} "{output_path}"'
        subprocess.run(["powershell", "-Command", ps], check=True, capture_output=True, text=True)
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

    select_terms = []
    cursor = 0.0
    for start, end in cut_ranges:
        if start > cursor + margin + 0.05:
            select_terms.append(f"between(t,{cursor},{start - margin})")
        cursor = max(cursor, end + margin)
    if duration - cursor > 0.05:
        select_terms.append(f"between(t,{cursor},{duration})")

    if not select_terms:
        return

    select_expr = "+".join(select_terms)

    tmpdir = Path(tempfile.mkdtemp())
    try:
        vid_path = tmpdir / "video.mkv"
        aud_path = tmpdir / "audio.mka"

        _run_filter(mkv_path,
            f"select='{select_expr}',setpts=N/FRAME_RATE/TB[v]",
            "-map '[v]' -an -c:v libx264 -preset ultrafast -crf 23",
            str(vid_path))

        _run_filter(mkv_path,
            f"aselect='{select_expr}',asetpts=N/SR/TB[a]",
            "-map '[a]' -vn -c:a aac -b:a 640k",
            str(aud_path))

        subprocess.run(
            ["ffmpeg", "-y", "-i", str(vid_path), "-i", str(aud_path),
             "-c:v", "copy", "-c:a", "copy", output_path],
            check=True, capture_output=True, text=True,
        )
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"ffmpeg error: {e.stderr[:2000]}")
    finally:
        import shutil
        shutil.rmtree(tmpdir, ignore_errors=True)