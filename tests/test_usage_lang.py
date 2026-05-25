from __future__ import annotations

from usage_lang import detect_lang


def test_detect_lang_defaults_to_en_without_environment() -> None:
    assert detect_lang({}) == "en"


def test_detect_lang_reads_lang_zh_tw_locale() -> None:
    assert detect_lang({"LANG": "zh_TW.UTF-8"}) == "zh-TW"


def test_detect_lang_reads_tt_lang_ja() -> None:
    assert detect_lang({"TT_LANG": "ja"}) == "ja"


def test_detect_lang_reads_usage_lang_ko() -> None:
    assert detect_lang({"USAGE_LANG": "ko"}) == "ko"


def test_detect_lang_prefers_usage_lang_over_tt_lang() -> None:
    assert detect_lang({"USAGE_LANG": "ko", "TT_LANG": "ja"}) == "ko"


def test_detect_lang_prefers_usage_lang_over_tt_lang_and_lang() -> None:
    env = {"USAGE_LANG": "ja", "TT_LANG": "ko", "LANG": "zh_TW.UTF-8"}
    assert detect_lang(env) == "ja"


def test_detect_lang_unknown_code_falls_back_to_en() -> None:
    assert detect_lang({"LANG": "de_DE.UTF-8"}) == "en"
