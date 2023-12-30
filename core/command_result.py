from dataclasses import dataclass
from typing import Literal

@dataclass
class CommandResult:
    type: Literal["success", "fail", "ignorable"]
    reason: str | None = None
    
    def appendics_message(self) -> str:
        if self.reason is not None:
            return f": {self.reason}"
        else:
            return ""

    @staticmethod
    def success(reason: str | None = None) -> "CommandResult":
        return CommandResult(type="success", reason=reason)

    @staticmethod
    def fail(reason: str | None = None) -> "CommandResult":
        return CommandResult(type="fail", reason=reason)

    @staticmethod
    def ignorable() -> "CommandResult":
        return CommandResult(type="ignorable", reason=None)