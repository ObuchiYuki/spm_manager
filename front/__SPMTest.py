import sys
import tty
import re
import subprocess
import threading
import time
import queue

from argparse import ArgumentParser
from pathlib import Path
from dataclasses import dataclass
from typing import IO

import core
from SPMFind import SPMFind

@dataclass
class Test:
    name: str
    finished: bool = False
    passed: bool = False
    printing_thread: threading.Thread | None = None

class PackageTestTask:
    line_queue = queue.Queue[str]()
    
    finished: bool = False

    process: subprocess.Popen[bytes]

    process_thread: threading.Thread | None = None

    waiting_thread: threading.Thread | None = None

    executing_test: Test | None = None

    def __init__(self, process: subprocess.Popen[bytes]) -> None:
        self.process = process

    def run(self):
        self.process_thread = threading.Thread(target=self._process_queue)
        self.process_thread.daemon = True
        self.process_thread.start()
        while True:
            if self.process.stdout is None: break

            line = self.process.stdout.readline()
            line = line.decode("utf-8").strip()

            self.line_queue.put(line)

            if self.process.poll() is not None: break

    def wait(self):
        self.process.wait()
        self.finished = True
        if self.process_thread:
            self.process_thread.join()

        print()


    def _process_queue(self):
        while not self.finished or not self.line_queue.empty():
            try:
                line = self.line_queue.get(timeout=0.1)
                self._process_line(line)
            except queue.Empty:
                pass

    def _process_line(self, line: str):
        match = re.match(r"Test Suite '(.*)' started", line)
        if match:
            testname = match.group(1)
            if testname.endswith(".xctest") or testname == "All tests":
                return
            self._test_started(match.group(1))
            return
            
        match = re.match(r"Test Suite '(.*)' passed", line)
        if match and self.executing_test:
            self.executing_test.finished = True
            self.executing_test.passed = True
            return

        match = re.match(r"Test Suite '(.*)' failed", line)
        if match and self.executing_test:
            self.executing_test.finished = True
            self.executing_test.passed = False
            return
        
        match = re.match(r"Executed (\d+) tests, with (\d+) failure", line)
        if match and self.executing_test:
            test_count = int(match.group(1))
            failed_count = int(match.group(2))
            self._test_finished(test_count, failed_count)
            self.executing_test = None
            return

    def _test_started(self, name: str) -> None:
        def rotate_indicator(test: Test):
            braille_patterns = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏']
            index = 0
            while True:
                if test.finished: return                    
                sys.stdout.write(f"\r └ {braille_patterns[(index // 10) % 10]} {name}")
                sys.stdout.flush()
                time.sleep(0.01)
                index += 1

        self.executing_test = Test(name=name)
        thread = threading.Thread(target=rotate_indicator, args=(self.executing_test, ))
        thread.daemon = True  # メインスレッドが終了したら子スレッドも終了するように設定
        thread.start()
        self.executing_test.printing_thread = thread

    def _test_finished(self, test_count: int, failed_count: int) -> None:
        if not self.executing_test: 
            return
        if not self.executing_test.finished:
            return
        if not self.executing_test.printing_thread:
            return

        self.executing_test.printing_thread.join()

        if self.executing_test.passed:
            print(f"\n └ \033[A\033[0;32m✓\033[0m {self.executing_test.name} \t\033[0;32m(passed {test_count}/{test_count})\033[0m" + " " * 100, end="")
        else:
            print(f"\n └ \033[A\033[0;31m✗\033[0m {self.executing_test.name} \t\033[0;31m(failed {failed_count}/{test_count})\033[0m" + " " * 100, end="")


class SPMTestRunner:
    package_path: Path
    logger: core.Logger

    executing_test: Test | None = None

    indent = 0

    def __init__(self, package_path: Path, logger: core.Logger) -> None:
        assert package_path.is_dir(), "Package path is not directory."
        assert (package_path / "Package.swift").exists(), "Package.swift not found."
        self.package_path = package_path
        self.logger = logger

    def run(self):
        tty.setcbreak(sys.stdin.fileno()) # 標準入力を無効化
        process = subprocess.Popen(["stdbuf", "-oL", "swift", "test"], stdout=subprocess.PIPE, cwd=self.package_path, stderr=subprocess.PIPE)
        self.logger.log(f"Testing {self.package_path.name}...")
        task = PackageTestTask(process=process)
        task.run()
        task.wait() 

class SPMTest:
    parser: ArgumentParser
    default_root_path: Path
    logger: core.Logger

    def __init__(self, default_root_path: Path, logger: core.Logger) -> None:
        self.default_root_path = default_root_path
        self.logger = logger
        self.parser = ArgumentParser(description="Test Swift Packages")
        self.parser.add_argument("root_path", nargs="?", type=str, help="Root path of Swift packages")
    
    def run(self, argv: list[str]) -> None:
        args = self.parser.parse_args(argv)
        root_path = self.default_root_path if args.root_path is None else Path(args.root_path)

        finder = SPMFind(root_path=root_path)

        for package_path in finder.find():
            if not package_path.name == "Promise":
                continue
            runner = SPMTestRunner(package_path=package_path, logger=self.logger)
            runner.run()

            # if returncode == 0:
            #     self.logger.log(f"\033[0;32m✓\033[0m {package.name}")
            # else:
            #     self.logger.log(f"\033[0;31m✗\033[0m {package.name}")
            

        
if __name__ == "__main__":
    packages_path = Path("/Users/yuki/Developer/SwiftPM")
    logger = core.Logger(command_name="spm", is_debug=True)
    spm = SPMTest(default_root_path=packages_path, logger=logger)
    spm.run(sys.argv[1:])


# print(f"\033[A\033[0;31m✗\033[0m")