import argparse


def add_resume_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--resume",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Load/save checkpoint and continue pending work (default: resume)",
    )


def add_extract_arguments(parser: argparse.ArgumentParser) -> None:
    add_resume_arguments(parser)
    parser.add_argument(
        "--retry-failed",
        action="store_true",
        help="Include previously failed rows in this extract run",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Repeat batches until no pending rows remain",
    )
