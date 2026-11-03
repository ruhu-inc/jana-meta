"""The font of the synthetic worksheets the real reader is shown: Arial on macOS, or Liberation Sans, which has Arial's
metrics, on Linux (fonts-liberation, installed by the CI setup)."""

from __future__ import annotations

from pathlib import Path

_ARIAL = Path("/System/Library/Fonts/Supplemental/Arial.ttf")
_LIBERATION = Path("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf")
FONT = _LIBERATION if _LIBERATION.exists() and not _ARIAL.exists() else _ARIAL
