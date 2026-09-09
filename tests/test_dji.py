from datetime import datetime

from rapport.dji import AUDIO_EXT, DJI_DIR_RE, parse_name


def test_parse_mic_mini_name():
    p = parse_name("TX02_MIC001_20260907_140758_orig.wav")
    assert p.transmitter == "TX02"
    assert p.file_index == "001"
    assert p.recorded_at == datetime(2026, 9, 7, 14, 7, 58)
    assert p.suffix == "orig"


def test_parse_non_dji_name():
    p = parse_name("Interview with Sam.m4a")
    assert p.transmitter is None and p.recorded_at is None


def test_dir_pattern():
    assert DJI_DIR_RE.match("TX_MIC001_20260907_184337")
    assert not DJI_DIR_RE.match("Recordings")


def test_audio_extensions():
    assert {".wav", ".m4a", ".mp3", ".flac"} <= AUDIO_EXT
