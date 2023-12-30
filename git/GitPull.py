import subprocess
from pathlib import Path

import core

class GitPull:
    def __init__(self, package_path: Path) -> None:
        self.package_path = package_path

    def can_pull(self) -> core.CommandResult | None:
        config_path = self.package_path / ".git" / "config"
        if not config_path.exists():
            return core.CommandResult.fail("Git config not found.")

        with open(config_path, "r") as f:
            config = f.read()
            if "[remote \"origin\"]" not in config:
                return core.CommandResult.fail("Git remote origin not found.")
            
        return core.CommandResult.success()
    
    def run(self, force: bool, auto_fix_upstream_origin: bool) -> core.CommandResult:
        result = subprocess.run(["git", "pull"], cwd=self.package_path, capture_output=True, text=True)

        if "Already up to date." in result.stdout:
            return core.CommandResult.ignorable()
        
        if "There is no tracking information " in result.stderr:
            if auto_fix_upstream_origin:
                result = self._fix_upstream_origin()
                if result.type == "fail":
                    return result
                
                return core.CommandResult.success("Fixed upstream origin.")
                
            return core.CommandResult.fail("Upstream origin not set.")
        
        if "Need to specify how to reconcile divergent branches." in result.stderr:
            if force:
                return self._force_pull()
            else:
                return core.CommandResult.fail("There is a conflict. Use --force to force pull.")
        
        if not result.returncode == 0:
            return core.CommandResult.fail(f"Pull failed with return code {result.returncode}.")
        
        return core.CommandResult.success()
    

    def _get_current_branch_name(self) -> str | None:
        result = subprocess.run("git branch | grep -e '^\\* ' | sed -e 's/^\\* //g'", shell=True, cwd=self.package_path, capture_output=True, text=True)
        if not result.returncode == 0:
            return None
        
        return result.stdout.strip()
    
    def _fix_upstream_origin(self) -> core.CommandResult:
        branch_name = self._get_current_branch_name()
        if branch_name is None:
            return core.CommandResult.fail("Failed to get current branch name.")
        
        result = subprocess.run(f"git branch --set-upstream-to=origin/{branch_name} {branch_name}", shell=True, cwd=self.package_path, capture_output=True, text=True)
        if not result.returncode == 0:
            return core.CommandResult.fail("Failed to set upstream origin.")
        
        return core.CommandResult.ignorable()

    def _force_pull(self) -> core.CommandResult:
        branch_name = self._get_current_branch_name()
        if branch_name is None:
            return core.CommandResult.fail("Failed to get current branch name.")
        
        result = subprocess.run(f"git fetch && git reset --hard origin/{branch_name}", shell=True, cwd=self.package_path, capture_output=True, text=True)
        if not result.returncode == 0:
            return core.CommandResult.fail("Failed to force pull.")
        
        return core.CommandResult.success("Force pulled.")

    


