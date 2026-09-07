"""Settings and library paths.

Everything the app owns lives inside one folder (the "library"):

    ~/DJI Mic Library/
        audio/YYYY/YYYY-MM-DD/<original file name>.wav   <- untouched originals (the backup)
        cache/<recording id>/                             <- 16k wav, playback m4a, waveform peaks
        library.sqlite                                    <- transcripts, speakers, people
        settings.json                                     <- user settings

Backing up the app == backing up that folder.
"""
from __future__ import annotations

import json
import os
import threading
from dataclasses import dataclass, asdict, field
from pathlib import Path

DEFAULT_LIBRARY = Path(os.environ.get("DJI_MIC_LIBRARY", Path.home() / "DJI Mic Library"))


@dataclass
class Settings:
    # Import
    auto_import: bool = True
    delete_from_device_after_import: bool = False  # copy only; the mic is never cleared unless you opt in
    poll_interval_sec: float = 5.0
    min_file_age_sec: float = 20.0  # skip files still being written by the mic
    extra_volume_names: list[str] = field(default_factory=list)  # manual volume names to treat as mics
    auto_import_voice_memos: bool = False  # copy new Apple Voice Memos automatically (needs Full Disk Access)
    usb_volumes: list[str] = field(default_factory=list)      # non-DJI removable drives to import from (volume names)
    watched_folders: list[str] = field(default_factory=list)  # any folders (iCloud Drive, Dropbox…) to import audio from

    # Integrations (read-only API keys; nothing is written back)
    granola_api_key: str = ""
    granola_auto: bool = True
    omi_api_key: str = ""
    omi_auto: bool = True
    notion_token: str = ""
    notion_database_id: str = ""
    notion_auto: bool = True
    sync_interval_sec: float = 600.0

    # Transcription
    whisper_model: str = "mlx-community/whisper-large-v3-turbo"
    language: str | None = None  # None = auto detect

    # Speakers
    hf_token: str | None = None  # falls back to ~/.cache/huggingface/token
    diarizer: str = "auto"  # auto | pyannote | builtin
    embedding_model: str = "pyannote/wespeaker-voxceleb-resnet34-LM"
    person_match_threshold: float = 0.60  # cosine similarity needed to say "same person"
    cluster_distance_threshold: float = 0.55  # builtin diarizer: cosine distance to merge clusters
    min_speaker_seconds: float = 2.0  # drop diarized speakers with less speech than this

    # Summaries (local models only)
    summary_provider: str = "auto"   # auto | ollama | mlx | off
    summary_model: str = ""          # "" = provider default
    auto_summarize: bool = True      # summarize each recording right after processing

    # Playback
    skip_silence_min_gap: float = 0.7  # pauses shorter than this are kept (seconds)
    skip_silence_pad: float = 0.15     # audio kept on each side of a skipped pause (seconds)

    # UI
    port: int = 8765
    open_browser: bool = True

    def to_json(self) -> dict:
        return asdict(self)

    @classmethod
    def from_json(cls, data: dict) -> "Settings":
        s = cls()
        for k, v in data.items():
            if hasattr(s, k):
                setattr(s, k, v)
        return s


class Library:
    def __init__(self, root: Path = DEFAULT_LIBRARY):
        self.root = Path(root)
        self.audio_dir = self.root / "audio"
        self.cache_dir = self.root / "cache"
        self.db_path = self.root / "library.sqlite"
        self.settings_path = self.root / "settings.json"
        self._lock = threading.Lock()
        for d in (self.root, self.audio_dir, self.cache_dir):
            d.mkdir(parents=True, exist_ok=True)
        self.settings = self._load_settings()

    def _load_settings(self) -> Settings:
        if self.settings_path.exists():
            try:
                return Settings.from_json(json.loads(self.settings_path.read_text()))
            except Exception:
                pass
        s = Settings()
        self.save_settings(s)
        return s

    def reload_settings(self) -> Settings:
        """Re-read settings.json (another process may have changed it)."""
        try:
            if self.settings_path.exists():
                self.settings = Settings.from_json(json.loads(self.settings_path.read_text()))
        except Exception:
            pass
        return self.settings

    def save_settings(self, settings: Settings | None = None) -> None:
        with self._lock:
            if settings is not None:
                self.settings = settings
            self.settings_path.write_text(json.dumps(self.settings.to_json(), indent=2))

    def update_settings(self, patch: dict) -> Settings:
        data = self.settings.to_json()
        for k, v in patch.items():
            if k in data:
                data[k] = v
        self.save_settings(Settings.from_json(data))
        return self.settings

    # ---- small persisted state for connectors (last sync, last error) ----
    def state_get(self) -> dict:
        p = self.root / "sources_state.json"
        try:
            return json.loads(p.read_text()) if p.exists() else {}
        except Exception:
            return {}

    def state_update(self, key: str, **fields) -> None:
        with self._lock:
            st = self.state_get()
            st.setdefault(key, {}).update(fields)
            (self.root / "sources_state.json").write_text(json.dumps(st, indent=2))

    def hf_token(self) -> str | None:
        if self.settings.hf_token:
            return self.settings.hf_token.strip()
        env = os.environ.get("HF_TOKEN")
        if env:
            return env.strip()
        p = Path.home() / ".cache" / "huggingface" / "token"
        if p.exists():
            return p.read_text().strip() or None
        return None

    def recording_cache(self, recording_id: int) -> Path:
        d = self.cache_dir / str(recording_id)
        d.mkdir(parents=True, exist_ok=True)
        return d
