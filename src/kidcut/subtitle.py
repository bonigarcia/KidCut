import re

from kidcut.models import SubtitleEntry


def parse_srt(content: str) -> list[SubtitleEntry]:
    entries: list[SubtitleEntry] = []
    blocks = re.split(r"\n\s*\n", content.strip())
    for block in blocks:
        lines = block.strip().splitlines()
        if len(lines) < 3:
            continue
        if "-->" not in lines[1]:
            continue
        try:
            index = int(lines[0].strip())
        except ValueError:
            continue
        time_part = lines[1].strip()
        parts = time_part.split(" --> ")
        if len(parts) != 2:
            continue
        start, end = parts[0].strip(), parts[1].strip()
        text = "\n".join(lines[2:])
        entries.append(SubtitleEntry(index=index, start=start, end=end, text=text))
    return entries


def parse_ass(content: str) -> list[SubtitleEntry]:
    entries: list[SubtitleEntry] = []
    in_events = False
    index = 0
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("[Events]"):
            in_events = True
            continue
        if not in_events:
            continue
        if stripped.startswith("Format:"):
            headers = [h.strip() for h in stripped[len("Format:"):].split(",")]
            continue
        if not stripped.startswith("Dialogue:"):
            continue
        parts = [p.strip() for p in stripped[len("Dialogue:"):].split(",", 9)]
        if len(parts) < 10:
            continue
        index += 1
        _, start, end, *rest = parts[:10]
        text = rest[-1]
        start = start.replace(".", ",")
        end = end.replace(".", ",")
        text = text.replace("\\N", "\n").replace("\\n", "\n")
        entries.append(SubtitleEntry(index=index, start=start, end=end, text=text))
    return entries


def parse_subtitles(content: str) -> list[SubtitleEntry]:
    if content.strip().startswith("[Script Info]") or content.strip().startswith("[Events]"):
        return parse_ass(content)
    return parse_srt(content)
