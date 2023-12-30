from pathlib import Path
from typing import Generator

class SPMFind:
    root_path: Path

    def __init__(self, root_path: Path):
        self.root_path = root_path

    def find(self) -> Generator[Path, None, None]:
        if (self.root_path / "Package.swift").exists():
            yield self.root_path
            return

        for dir in self.root_path.iterdir():
            if dir.is_dir() and (dir / "Package.swift").exists():
                yield dir
        