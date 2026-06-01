import json
from pathlib import Path

DEFAULT_HISTORY_PATH = Path(__file__).resolve().parent.parent / "data" / "ytd_history.json"


class YtdTracker:
    def __init__(self, path: Path | None = None):
        self.path = path or DEFAULT_HISTORY_PATH
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._data = self._load()

    def _load(self) -> dict:
        if not self.path.exists():
            return {}
        with open(self.path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _save(self) -> None:
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(self._data, f, indent=2)

    def _key(self, key: str) -> str:
        return str(key).strip()

    def stored_ytd(self, key: str) -> float:
        entry = self._data.get(self._key(key), {})
        return float(entry.get("ytd", 0.0))

    def resolve_ytd(self, key: str, net_pay: float, csv_ytd: float | None) -> float:
        if csv_ytd is not None:
            return csv_ytd
        return self.stored_ytd(key) + net_pay

    def record(self, key: str, name: str, ytd_after: float) -> None:
        self._data[self._key(key)] = {"name": name, "ytd": ytd_after}
        self._save()
