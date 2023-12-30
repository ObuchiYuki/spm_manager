from argparse import ArgumentParser, Namespace
from pathlib import Path
import subprocess
from dataclasses import dataclass

import core
import front
import time
import git

@dataclass
class UpdateTask:
    package_path: Path
    printer: core.SingleLinePrinter
    finished = False

    @property
    def name(self):
        return self.package_path.absolute().name
    
    def print(self, message: str):
        self.printer.print(message)

class SPMUpdate:
    parser: ArgumentParser
    default_root_path: Path
    logger: core.Logger
    parallax_executor = core.ParallaxExecutor()

    def __init__(self, default_root_path: Path, logger: core.Logger, parser: ArgumentParser | None = None) -> None:
        self.default_root_path = default_root_path
        self.logger = logger
        self.parser = parser or ArgumentParser(description="SwiftPM Update")
        self.parser.add_argument("root", nargs="?", type=str, help="Root path of Swift packages")
        self.parser.add_argument("-p", "--parallel", type=int, default=4, help="Number of parallel processes.")
        
    def run(self, args: Namespace):
        root_path: Path = self.default_root_path if args.root is None else Path(args.root)
        parallel_count = args.parallel or 4
        self.parallax_executor.max_parallel = parallel_count
        
        package_pathes = list(front.SPMFind(root_path).find())
        printer = core.MultilinePrinter(len(package_pathes), disable_input=True, command_name=self.logger.command_name)

        tasks: list[UpdateTask] = []
        for i, package_path in enumerate(package_pathes):
            task = UpdateTask(package_path=package_path, printer=printer.printer(i))
            tasks.append(task)
            self.parallax_executor.register(self._run_task, task)
    
        # rotate spinner
        spinner = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏']
        spinner_index = 0
        
        while True:
            for i, task in enumerate(tasks):
                if task.finished: continue
                index = (spinner_index + i) % len(spinner)
                task.print(f"{spinner[index]} Updating: {task.name}...")
            
            spinner_index = spinner_index + 1
            time.sleep(0.1)

            if all([task.finished for task in tasks]):
                break

        self.parallax_executor.join()
        printer.terminate()

    def _run_task(self, task: UpdateTask):
        result = subprocess.run(["swift", "package", "update"], cwd=task.package_path, capture_output=True, text=True)

        task.finished = True
        if not result.returncode == 0:
            error_message = f"Update failed with return code {result.returncode}."
            sub_message: str | None = None
            for row in result.stderr.split("\n"):
                if row.startswith("error: "):
                    sub_message = row[7:]

            
            if sub_message is not None:
                error_message += f"\n      └ \033[0;31m{sub_message}\033[0m"

            task.print(f"\033[0;31m✗\033[0m Update failed: {task.name}: {error_message}")
        
        else:
            task.print(f"\033[0m\033[0;32m✓\033[0m Updated: {task.name}")
    



