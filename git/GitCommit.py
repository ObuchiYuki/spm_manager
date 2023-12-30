import datetime
import subprocess
from pathlib import Path

class GitCommit:
    def __init__(self, package_path: Path) -> None:
        assert package_path.is_dir(), "Package path is not directory."
        assert (package_path / "Package.swift").exists(), "Package.swift not found."
        self.package_path = package_path

    def commit(self) -> bool:
        _ = subprocess.run(["git", "add", "."], cwd=self.package_path, capture_output=True, text=True)
        # date
        commit_message = datetime.datetime.now().strftime("%Y/%m/%d %H:%M:%S")
        result = subprocess.run(["git", "commit", "-m", commit_message], cwd=self.package_path, capture_output=True, text=True)

        if "nothing to commit" in result.stdout:
            return False

        return True