from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SubtitleEntry:
    index: int
    start: str
    end: str
    text: str


@dataclass(frozen=True, slots=True)
class CutScene:
    start: str
    end: str
    reason: str


@dataclass(frozen=True, slots=True)
class MkvTrack:
    index: int
    kind: str
    language: str
    default: bool
    codec: str


@dataclass(frozen=True, slots=True)
class ScanRunSummary:
    scan_id: str
    mkv_path: str
    vendor: str
    model: str
    started_at: str
    finished_at: str
    input_tokens: int | None = None
    output_tokens: int | None = None
    finding_count: int | None = None
    duration_seconds: float | None = None
