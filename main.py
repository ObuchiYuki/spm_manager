from argparse import ArgumentParser

import core
import git
import front

from default_root_path import default_root_path

if __name__ == "__main__":
    logger = core.Logger(is_debug=False, command_name="spm")

    parser = ArgumentParser(description="SPM package utilities")
    subparsers = parser.add_subparsers()
    
    commit_parser = subparsers.add_parser("push", help="Commit/Push all packages")
    commit_parser.set_defaults(func=front.SPMPush(default_root_path=default_root_path, logger=logger, parser=commit_parser).run)

    pull_parser = subparsers.add_parser("pull", help="Pull all packages")
    pull_parser.set_defaults(func=front.SPMPull(default_root_path=default_root_path, logger=logger, parser=pull_parser).run)

    test_parser = subparsers.add_parser("test", help="Test all packages")
    test_parser.set_defaults(func=front.SPMTest(default_root_path=default_root_path, logger=logger, parser=test_parser).run)

    clean_parser = subparsers.add_parser("clean", help="Clean all packages")
    clean_parser.set_defaults(func=front.SPMClean(default_root_path=default_root_path, logger=logger, parser=clean_parser).run)

    update_parser = subparsers.add_parser("update", help="Update all packages")
    update_parser.set_defaults(func=front.SPMUpdate(default_root_path=default_root_path, logger=logger, parser=update_parser).run)

    args = parser.parse_args()
    if hasattr(args, "func"):
        args.func(args)
