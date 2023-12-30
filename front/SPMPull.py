from argparse import ArgumentParser, Namespace
from pathlib import Path
import threading
from dataclasses import dataclass

import core
import front
import time
import git

@dataclass
class PullTask:
    path: Path
    force_pull: bool
    auto_fix_upstream_origin: bool
    printer: core.SingleLinePrinter
    finished = False

    @property
    def name(self):
        return self.path.absolute().name
    
    def print(self, message: str):
        self.printer.print(message)

class SPMPull:
    parser: ArgumentParser
    default_root_path: Path
    logger: core.Logger

    parallax_executor: core.ParallaxExecutor

    def __init__(self, default_root_path: Path, logger: core.Logger, parser: ArgumentParser | None = None) -> None:
        self.default_root_path = default_root_path
        self.logger = logger
        self.parallax_executor = core.ParallaxExecutor()
        self.parser = parser or ArgumentParser(description="SwiftPM Pull")
        self.parser.add_argument("root", nargs="?", type=str, help="Root path of Swift packages")
        self.parser.add_argument("--force", action="store_true", help="Force pull even if there is a conflict.")
        self.parser.add_argument("--autofix", action="store_true", help="Automatically fix upstream origin.")
        self.parser.add_argument("-p", "--parallel", type=int, default=4, help="Number of parallel processes.")
        
    def run(self, args: Namespace):
        root_path: Path = self.default_root_path if args.root is None else Path(args.root)
        force_pull = args.force or False
        auto_fix_upstream_origin = args.autofix or True
        parallel_count = args.parallel or 4
        self.parallax_executor.max_parallel = parallel_count
        
        package_pathes = list(front.SPMFind(root_path).find())
        printer = core.MultilinePrinter(len(package_pathes), disable_input=True, command_name=self.logger.command_name)

        tasks: list[PullTask] = []
        for i, package_path in enumerate(package_pathes):
            task = PullTask(path=package_path, force_pull=force_pull, auto_fix_upstream_origin=auto_fix_upstream_origin, printer=printer.printer(i))
            tasks.append(task)
            self.parallax_executor.register(self._run_task, task)
    
        # rotate spinner
        spinner = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏']
        spinner_index = 0
        
        while True:
            for i, task in enumerate(tasks):
                if task.finished: continue
                index = (spinner_index + i) % len(spinner)
                task.print(f"{spinner[index]} Pulling: {task.name}...")
            
            spinner_index = spinner_index + 1
            time.sleep(0.1)

            if all([task.finished for task in tasks]):
                break

        self.parallax_executor.join()
        printer.terminate()

    def _run_task(self, task: PullTask):
        def display_result(result: core.CommandResult):
            if result.type == "success":
                task.print(f"\033[0m\033[0;32m✓\033[0m Pull: {task.name}{result.appendics_message()}")
            elif result.type == "fail":
                task.print(f"\033[0;31m✗\033[0m Pull failed: {task.name}{result.appendics_message()}")
            elif result.type == "ignorable":
                task.print(f"Nothing to pull: {task.name}")

        pull = git.GitPull(task.path)
        can_pull = pull.can_pull()
        if can_pull is None:
            task.finished = True
            return
        if can_pull.type != "success":
            task.finished = True
            display_result(can_pull)
            return
                
        result = pull.run(task.force_pull, task.auto_fix_upstream_origin)
        task.finished = True
        display_result(result)


