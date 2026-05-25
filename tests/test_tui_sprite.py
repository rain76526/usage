from __future__ import annotations

import pytest
from rich.text import Text

from tui_sprite import render_sprite


@pytest.mark.parametrize("phase", range(6))
def test_render_sprite_returns_non_empty_text_for_all_expected_phases(phase: int) -> None:
    sprite = render_sprite(phase)

    assert isinstance(sprite, Text)
    assert sprite.plain.strip()


@pytest.mark.parametrize("phase", [-1, -999, 6, 999])
def test_render_sprite_falls_back_for_out_of_range_phases(phase: int) -> None:
    sprite = render_sprite(phase)

    assert isinstance(sprite, Text)
    assert sprite.plain.strip()


def test_render_sprite_phase_wraps_to_same_frame() -> None:
    first = render_sprite(0)
    wrapped = render_sprite(4)

    assert first.plain == wrapped.plain
    assert first.spans == wrapped.spans
