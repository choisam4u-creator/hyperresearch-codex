"""실행 기록(manifest): 어느 단계까지 했는지 파일로 남겨 중단돼도 그 자리에서 이어 간다."""
import json
import os
import tempfile
import time
from pathlib import Path


def atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=".hpr-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


class Manifest:
    def __init__(self, run_dir: Path, prompt: str | None = None, tier: str = "light"):
        self.path = run_dir / "manifest.json"
        if self.path.exists():
            self.data = json.loads(self.path.read_text(encoding="utf-8"))
        else:
            if prompt is None:
                raise FileNotFoundError(f"manifest 없음: {self.path}")
            self.data = {"run_id": run_dir.name, "prompt": prompt, "tier": tier,
                         "created_at": time.time(), "steps": [], "artifacts": {}, "usage": []}
            self.save()

    def save(self) -> None:
        atomic_write(self.path, json.dumps(self.data, ensure_ascii=False, indent=2))

    def done(self, name: str) -> bool:
        return any(s["name"] == name and s["status"] == "ok" for s in self.data["steps"])

    def start(self, name: str) -> None:
        self.data["steps"].append({"name": name, "status": "running", "started_at": time.time()})
        self.save()

    def finish(self, name: str, status: str = "ok", note: str = "") -> None:
        for step in reversed(self.data["steps"]):
            if step["name"] == name and step["status"] == "running":
                step.update(status=status, finished_at=time.time(), note=note)
                break
        self.save()

    def artifact(self, key: str, path: Path) -> None:
        self.data["artifacts"][key] = str(path)
        self.save()

    def usage(self, record: dict) -> None:
        self.data["usage"].append(record)
        self.save()
