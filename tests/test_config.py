import json


def test_defaults_are_safe(library):
    s = library.settings
    assert s.delete_from_device_after_import is False, "imports must be copy-only by default"
    assert s.auto_import_voice_memos is False
    assert s.granola_api_key == "" and s.omi_api_key == "" and s.notion_token == ""


def test_settings_round_trip(library):
    library.update_settings({"whisper_model": "mlx-community/whisper-base-mlx", "not_a_setting": 1})
    on_disk = json.loads(library.settings_path.read_text())
    assert on_disk["whisper_model"] == "mlx-community/whisper-base-mlx"
    assert "not_a_setting" not in on_disk
    assert library.reload_settings().whisper_model == "mlx-community/whisper-base-mlx"


def test_state_update(library):
    library.state_update("granola", last_sync="2026-09-09T10:00:00")
    library.state_update("granola", last_error=None)
    assert library.state_get()["granola"] == {"last_sync": "2026-09-09T10:00:00", "last_error": None}


def test_library_layout(library):
    assert library.audio_dir.is_dir() and library.cache_dir.is_dir()
    assert library.recording_cache(7) == library.cache_dir / "7"
