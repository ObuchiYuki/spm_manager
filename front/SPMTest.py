from dataclasses import dataclass, field
from argparse import ArgumentParser, Namespace
from pathlib import Path
import subprocess
import re
import time

import core
import front

class SwiftTest:
    pass

spinner_string = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏']

@dataclass
class TestTask:
    @dataclass
    class Test:
        name: str
        index: int = 0
        spinner_index: int = 0
        finished: bool = False
        successed: bool = False
        failed_count: int | None = None
        test_count: int | None = None

    package_path: Path
    printer: core.SingleLinePrinter
    index: int
    
    state: str = "Waiting"
    spinner_index: int = 0
    finished = False
    successed: bool = False

    test_index = 0
    test_subprinter_table: dict[int, core.SingleLinePrinter] = field(default_factory=dict)
    test_state_table: dict[int, str] = field(default_factory=dict)
    
    current_test: Test | None = None
    executed_tests: list[Test] = field(default_factory=list)

    def new_test(self, name: str) -> Test:
        self.building = False
        test = TestTask.Test(name=name, index=self.test_index)
        self.test_index += 1
        self.current_test = test
        return test
    
    def conclude_test(self):
        assert self.current_test is not None
        self.rotate_state_spinner()

        self.executed_tests.append(self.current_test)
        self.current_test = None
    
    @property
    def name(self):
        return self.package_path.absolute().name
    
    def rotate_state_spinner(self):
        if self.finished: return

        index = (self.index + self.spinner_index) % len(spinner_string)
        self.printer.print(f"{spinner_string[index]} {self.name}: {self.state}")
        self.spinner_index += 1

        if self.current_test is not None:
            def format_message(test: TestTask.Test) -> str:
                message = self.test_state_table.get(test.index, "")
                if test.finished:
                    if test.successed:
                        return f"\033[0;32m✓\033[0m {test.name}: {message}"
                    else:
                        return f"\033[0;31m✗\033[0m {test.name}: {message}"
                else:
                    index = (test.spinner_index + test.index) % len(spinner_string)
                    test.spinner_index += 1
                    return f"{spinner_string[index]} {test.name}: {message}"
                

            test_index = self.current_test.index
            if test_index not in self.test_subprinter_table:
                self.test_subprinter_table[test_index] = self.printer.subprinter()
                
            self.test_subprinter_table[test_index].print(
                f"     └ {format_message(self.current_test)}"
            )

            prev_test_index = test_index - 1   

            if prev_test_index in self.test_subprinter_table:
                prev_test_printer = self.test_subprinter_table[prev_test_index]
                prev_test_printer.print(
                    f"     ├ {format_message(self.executed_tests[prev_test_index])}"
                )


    def finish(self):
        for test in self.executed_tests:
            if not test.finished:
                test.finished = True
                test.failed_count = 0
                test.test_count = 0
            
        successed = all([test.successed for test in self.executed_tests])
        if successed:
            self.printer.print(f"\033[0;32m✓\033[0m {self.name}: {self.state}")
        else:
            self.printer.print(f"\033[0;31m✗\033[0m {self.name}: {self.state}")
        
        self.successed = successed
        self.finished = True

    def print_state(self, state: str):
        self.state = state
        self.rotate_state_spinner()

    def print_teststate(self, state: str):
        if self.current_test is None:
            raise Exception("No test is running")
        test_index = self.current_test.index
        
        self.test_state_table[test_index] = state
        self.rotate_state_spinner()


ansi_escape = re.compile(r'\x1B\[[0-?]*[ -/]*[@-~]')

def remove_escape_sequences(line: str) -> str:
    line = ansi_escape.sub('', line)
    return line

class SPMTest: 
    logger: core.Logger
    parser: ArgumentParser
    default_root_path: Path
    parallax_executor: core.ParallaxExecutor

    def __init__(self, default_root_path: Path, logger: core.Logger, parser: ArgumentParser | None = None) -> None:
        self.logger = logger
        self.default_root_path = default_root_path
        self.parallax_executor = core.ParallaxExecutor()
        self.parser = parser or ArgumentParser(description="SwiftPM Test")
        self.parser.add_argument("root", nargs="?", help="The packages root directory", type=str)
        self.parser.add_argument("-n", "--name", help="The package name", type=str)
        self.parser.add_argument("-p", "--parallel", type=int, help="Run tests in parallel (default: 1)")
        
    def run(self, args: Namespace) -> None:
        root_path = self.default_root_path if args.root is None else Path(args.root)
        package_name = args.name
        parallel = args.parallel or 1
        self.parallax_executor.max_parallel = parallel

        package_pathes = [p for p in front.SPMFind(root_path).find() if p.is_dir() and (package_name is None or p.name == package_name)]
        printer = core.MultilinePrinter(len(package_pathes), command_name=self.logger.command_name)
        # printer.enabled = False
        tasks: list[TestTask] = []

        for i, package_path in enumerate(package_pathes):
            task = TestTask(package_path=package_path, printer=printer.printer(i), index=i)
            task.print_state("Waiting")
            tasks.append(task)
            self.parallax_executor.register(self._run_task, task)

        while True:
            for task in tasks:
                task.rotate_state_spinner()
            if all([task.finished for task in tasks]):
                break
            time.sleep(0.1)

        self.parallax_executor.join()
        printer.terminate()

        successed = all([task.successed for task in tasks])

        if successed:
            self.logger.log(f"\033[0;32m✓\033[0m All tests passed")
        else:
            failed_tests_names = ", ".join([task.name for task in tasks if not task.successed])
            self.logger.log(f"\033[0;31m✗\033[0m Failed tests: {failed_tests_names}")
            exit(1)
            
    def _run_task(self, task: TestTask):
        process = subprocess.Popen(
            ["stdbuf", "-oL", "swift", "test"],
            cwd=task.package_path, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.STDOUT
        )

        if process.stdout is None: return

        while True:
            line = process.stdout.readline()
            line = line.decode("utf-8").strip()
            line = remove_escape_sequences(line)

            self._process_line(task, line)

            if process.poll() is not None: break

        successed = all([test.successed for test in task.executed_tests])
        test_count = sum([test.test_count or 0 for test in task.executed_tests])
        failed_count = sum([test.failed_count or 0 for test in task.executed_tests])

        if successed:
            task.print_state(f"\033[0;32mPassed {test_count} tests\033[0m")
        else:
            task.print_state(f"\033[0;31mFailed {failed_count}/{test_count} tests\033[0m")

        task.finish()


    def _process_line(self, task: TestTask, line: str):
        if line == "": return

        if line.startswith("Building"):
            task.print_state(f"Building")
            return

        if line.startswith("Build complete"):
            task.print_state(f"Build complete")
            return

        match = re.match(r"Test Suite '(.*)' started", line)
        if match:
            task.print_state(f"Testing")
            testname = match.group(1)
            if testname.endswith(".xctest") or testname == "All tests":
                return
            self._test_started(task, match.group(1))
            return
            
        match = re.match(r"Test Suite '(.*)' passed", line)
        if match and task.current_test:
            task.current_test.finished = True
            task.current_test.successed = True
            return

        match = re.match(r"Test Suite '(.*)' failed", line)
        if match and task.current_test:
            task.current_test.finished = True
            task.current_test.successed = False
            return
        
        match = re.match(r"Executed (\d+) tests?, with (\d+) failures?", line)
        if match and task.current_test:
            test_count = int(match.group(1))
            failed_count = int(match.group(2))
            self._test_finished(task, test_count, failed_count)

    def _test_started(self, task: TestTask, name: str) -> None:
        test = task.new_test(name=name)
        task.current_test = test
        task.print_teststate(f"Testing")

    def _test_finished(self, task: TestTask, test_count: int, failed_count: int) -> None:
        test = task.current_test  
        if not test: 
            raise Exception("No test is running")
        if not test.finished:
            raise Exception("Test is not finished")
        
        test.failed_count = failed_count
        test.test_count = test_count

        if test.successed:
            task.print_teststate(f"\033[0;32mPased {test_count} tests\033[0m")
        else:
            task.print_teststate(f"\033[0;31mFailed {failed_count}/{test_count} tests\033[0m")

        task.conclude_test()
