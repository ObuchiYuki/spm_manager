from argparse import ArgumentParser, Namespace
from pathlib import Path
import subprocess
from dataclasses import dataclass

import core
import front
import time
import git

@dataclass
class CleanTask:
    package_path: Path
    printer: core.SingleLinePrinter
    finished = False

    @property
    def name(self):
        return self.package_path.absolute().name
    
    def print(self, message: str):
        self.printer.print(message)

class SPMClean:
    parser: ArgumentParser
    default_root_path: Path
    logger: core.Logger
    parallax_executor: core.ParallaxExecutor

    def __init__(self, default_root_path: Path, logger: core.Logger, parser: ArgumentParser | None = None) -> None:
        self.default_root_path = default_root_path
        self.logger = logger
        self.parallax_executor = core.ParallaxExecutor()
        self.parser = parser or ArgumentParser(description="SwiftPM Clean")
        self.parser.add_argument("root", nargs="?", type=str, help="Root path of Swift packages")
        self.parser.add_argument("-p", "--parallel", type=int, default=4, help="Number of parallel processes.")
        
    def run(self, args: Namespace):
        root_path: Path = self.default_root_path if args.root is None else Path(args.root)
        parallel_count = args.parallel or 4
        self.parallax_executor.max_parallel = parallel_count
        
        package_pathes = list(front.SPMFind(root_path).find())
        printer = core.MultilinePrinter(len(package_pathes), disable_input=True, command_name=self.logger.command_name)

        tasks: list[CleanTask] = []
        for i, package_path in enumerate(package_pathes):
            task = CleanTask(package_path=package_path, printer=printer.printer(i))
            tasks.append(task)
            self.parallax_executor.register(self._run_task, task)
    
        # rotate spinner
        spinner = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏']
        spinner_index = 0
        
        while True:
            for i, task in enumerate(tasks):
                if task.finished: continue
                index = (spinner_index + i) % len(spinner)
                task.print(f"{spinner[index]} Cleaning: {task.name}...")
            
            spinner_index = spinner_index + 1
            time.sleep(0.1)

            if all([task.finished for task in tasks]):
                break

        self.parallax_executor.join()
        printer.terminate()

    def _run_task(self, task: CleanTask):
        def display_result(result: core.CommandResult):
            if result.type == "success":
                task.print(f"\033[0m\033[0;32m✓\033[0m Clean: {task.name}{result.appendics_message()}")
            elif result.type == "fail":
                task.print(f"\033[0;31m✗\033[0m Clean failed: {task.name}{result.appendics_message()}")
            elif result.type == "ignorable":
                task.print(f"Nothing to clean: {task.name}")

        result = self._run_clean(task)
        task.finished = True
        display_result(result)

    def _run_clean(self, task: CleanTask) -> core.CommandResult:
        result = subprocess.run(["swift", "package", "clean"], cwd=task.package_path, capture_output=True, text=True)

        if not result.returncode == 0:
            return core.CommandResult.fail(f"Clean failed with return code {result.returncode}.")

        return core.CommandResult.success()        


