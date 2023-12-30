import subprocess
from pathlib import Path

import core 

class GitPush:
    def __init__(self, package_path: Path) -> None:
        assert package_path.is_dir(), "Package path is not directory."
        assert (package_path / "Package.swift").exists(), "Package.swift not found."
        self.package_path = package_path

    def can_push(self) -> core.CommandResult | None:
        config_path = self.package_path / ".git" / "config"
        if not config_path.exists():
            return core.CommandResult.fail("Git config not found.")

        with open(config_path, "r") as f:
            config = f.read()
            if "[remote \"origin\"]" not in config:
                return core.CommandResult.fail("Git remote origin not found.")

    def push(self, force: bool) -> core.CommandResult:
        can_push = self.can_push()
        if can_push is not None:
            return can_push
        
        command = ["git", "push"]
        if force:
            command.append("--force")

        result = subprocess.run(command, cwd=self.package_path, capture_output=True, text=True)
        if "Everything up-to-date" in result.stdout:
            return core.CommandResult.ignorable()

        if not result.returncode == 0:
            lines = result.stderr.split("\n")
            if len(lines) > 0:
                reason = lines[0]
                return core.CommandResult.fail(reason)
            else:
                return core.CommandResult.fail(f"Push failed with return code {result.returncode}")

        return core.CommandResult.success()

    def push_tags(self) -> core.CommandResult:
        can_push = self.can_push()
        if can_push is not None:
            return can_push

        result = subprocess.run(["git", "push", "--tags"], cwd=self.package_path, capture_output=True, text=True)
        if "Everything up-to-date" in result.stderr:
            return core.CommandResult.ignorable()

        # print("stdout", result.stdout)
        # print("stderr", result.stderr)

        reject_message = [line for line in result.stderr.split("\n") if "[rejected]" in line]
        if len(reject_message):
            return core.CommandResult.fail(reject_message[0].replace("! [rejected]", "").strip())

        if not result.returncode == 0:
            lines = result.stderr.split("\n")
            if len(lines) > 0:
                reason = lines[0]
                return core.CommandResult.fail(reason)
            else:
                return core.CommandResult.fail(f"Push tags failed with return code {result.returncode}")

        return core.CommandResult.success()