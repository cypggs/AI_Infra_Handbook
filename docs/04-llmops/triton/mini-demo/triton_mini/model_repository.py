"""Model Repository loader for the Mini Triton demo."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict

from .backend import backend_for_config, BaseBackend
from .config_parser import ConfigParser, TritonConfig
from .scheduler import Scheduler, scheduler_for_config


@dataclass
class Model:
    """A loaded model in the repository."""

    name: str
    config: TritonConfig
    backend: BaseBackend
    scheduler: Scheduler
    path: Path
    version: int = 1

    @property
    def is_ensemble(self) -> bool:
        return self.config.ensemble_scheduling is not None


class ModelRepository:
    """Loads models from a Triton model repository directory."""

    def __init__(self, repo_path: Path | str) -> None:
        self.repo_path = Path(repo_path)
        self.models: Dict[str, Model] = {}

    def load(self) -> "ModelRepository":
        """Scan the repository and load every model directory."""
        if not self.repo_path.is_dir():
            raise ValueError(f"Model repository does not exist: {self.repo_path}")
        for entry in sorted(self.repo_path.iterdir()):
            if not entry.is_dir():
                continue
            config_path = entry / "config.pbtxt"
            if not config_path.exists():
                continue
            config = ConfigParser().parse_file(config_path)
            config.name = config.name or entry.name
            backend = backend_for_config(config)
            scheduler = scheduler_for_config(config)
            self.models[config.name] = Model(
                name=config.name,
                config=config,
                backend=backend,
                scheduler=scheduler,
                path=entry,
                version=self._detect_version(entry),
            )
        return self

    def _detect_version(self, model_dir: Path) -> int:
        """Return the first integer version subdirectory, otherwise 1."""
        for child in sorted(model_dir.iterdir()):
            if child.is_dir() and child.name.isdigit():
                return int(child.name)
        return 1

    def get(self, name: str) -> Model:
        if name not in self.models:
            raise ValueError(f"Model not found: {name}")
        return self.models[name]

    def list_models(self) -> list[str]:
        return sorted(self.models.keys())
