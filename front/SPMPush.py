from argparse import ArgumentParser, Namespace
from pathlib import Path
from dataclasses import dataclass
import time
import datetime

import core
import git
import front

@dataclass
class CommitTask:
    path: Path
    force: bool
    printer: core.SingleLinePrinter
    is_daemon: bool
    tag_printer: core.SingleLinePrinter | None = None
    finished = False

    @property
    def name(self):
        return self.path.absolute().name
    
    def print(self, message: str):
        if self.is_daemon:
            print(core.remove_escape_sequences(message))
        else:
            self.printer.print(message)

    def print_tag(self, message: str):
        if self.is_daemon:
            print(core.remove_escape_sequences(message))
        else:
            if self.tag_printer is None:
                self.tag_printer = self.printer.subprinter()

            self.tag_printer.print(message)

class SPMPush:
    parser: ArgumentParser
    logger: core.Logger
    default_root_path: Path
    parallax_executor: core.ParallaxExecutor

    def __init__(self, default_root_path: Path, logger: core.Logger, parser: ArgumentParser | None = None) -> None:
        self.logger = logger
        self.default_root_path = default_root_path
        self.parallax_executor = core.ParallaxExecutor()
        self.parser = parser or ArgumentParser(description="SwiftPM Commit")
        self.parser.add_argument("root", nargs="?", type=str, help="Root path of Swift packages")
        self.parser.add_argument("-f", "--force", action="store_true", help="Force pull even if there is a conflict.")
        self.parser.add_argument("-p", "--parallel", type=int, default=4, help="Number of parallel processes.")
        self.parser.add_argument("--daemon", action="store_true", help="Run as daemon.")

    def run(self, args: Namespace):
        root_path: Path = self.default_root_path if args.root is None else Path(args.root)
        parallel_count = args.parallel or 4
        force_push = args.force or False
        is_daemon = args.daemon or False

        if is_daemon:
            parallel_count = 1

        self.parallax_executor.max_parallel = parallel_count
        
        package_pathes = list(front.SPMFind(root_path).find())
        
        printer = core.MultilinePrinter(len(package_pathes), disable_input=not is_daemon, command_name=self.logger.command_name)
        
        tasks: list[CommitTask] = []

        if is_daemon:
            date = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(date)

        for i, package_path in enumerate(package_pathes):
            task = CommitTask(path=package_path, force=force_push, printer=printer.printer(i), is_daemon=is_daemon)
            tasks.append(task)
            self.parallax_executor.register(self._run_task, task)

        # rotate spinner
        spinner = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏']
        spinner_index = 0
        
        while True:
            if is_daemon: break
            for i, task in enumerate(tasks):
                if task.finished: continue
                index = (spinner_index + i) % len(spinner)
                task.print(f"{spinner[index]} Pushing: {task.name}...")
            
            spinner_index = spinner_index + 1
            time.sleep(0.1)

            if all([task.finished for task in tasks]):
                break

        self.parallax_executor.join()
        if printer is not None:
            printer.terminate()

    def _run_task(self, task: CommitTask):
        commiter = git.GitCommit(task.path)
        pusher = git.GitPush(task.path)

        if commiter.commit():
            task.finished = True
            task.print(f"\033[0;32m✓\033[0m Commit: {task.name}")
            result = pusher.push(task.force)
            if result.type == "success":
                task.print(f"\033[0;32m✓\033[0m Push: {task.name}{result.appendics_message()}")
            elif result.type == "fail":
                task.print(f"\033[0;31m✗\033[0m Push failed: {task.name}{result.appendics_message()}")
        else:
            task.finished = True
            task.print(f"No changes: {task.name}")

        result = pusher.push_tags()

        if result.type == "success":
            task.print_tag(f"      └ \033[0;32m✓\033[0m Push tags: {task.name}{result.appendics_message()}")
        elif result.type == "fail":
            task.print_tag(f"      └ \033[0;31m✗\033[0m Push tags failed: {task.name}{result.appendics_message()}")

