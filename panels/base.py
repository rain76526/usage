from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol

try:
    from Foundation import NSBundle as _NSBundle, NSUserDefaults as _NSUserDefaults
    _HAS_FOUNDATION = True
except ImportError:
    _HAS_FOUNDATION = False
    _NSBundle = None  # type: ignore[assignment]
    _NSUserDefaults = None  # type: ignore[assignment]

if TYPE_CHECKING:
    from menubar import PopoverState

ACTIVE_PANEL_DEFAULTS_KEY = "usage.activePanelId"


class Panel(Protocol):
    id: str
    i18n_key: str

    def build_view(self, delegate: Any) -> Any: ...
    def apply_state(self, view: Any, state: PopoverState) -> None: ...
    def preferred_size(self) -> tuple[float, float]: ...


def load_active_panel_id(defaults: Any | None = None) -> str:
    if not _HAS_FOUNDATION:
        return "classic"
    store = defaults if defaults is not None else _NSUserDefaults.standardUserDefaults()
    value = store.stringForKey_(ACTIVE_PANEL_DEFAULTS_KEY)
    return str(value) if value else "classic"


def save_active_panel_id(panel_id: str, defaults: Any | None = None) -> None:
    if not _HAS_FOUNDATION:
        return
    store = defaults if defaults is not None else _NSUserDefaults.standardUserDefaults()
    store.setObject_forKey_(panel_id, ACTIVE_PANEL_DEFAULTS_KEY)
    if hasattr(store, "synchronize"):
        store.synchronize()


def resolve_resource(name: str) -> str:
    if _HAS_FOUNDATION and _NSBundle is not None:
        bundle = _NSBundle.mainBundle()
        if bundle is not None:
            stem, _, ext = name.rpartition(".")
            path = bundle.pathForResource_ofType_(stem, ext)
            if path:
                return str(path)
    return str(Path(__file__).resolve().parent.parent / "assets" / name)
