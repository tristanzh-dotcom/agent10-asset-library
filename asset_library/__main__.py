import sys

from .cli import run_cli
from .runtime import build_runtime


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    service = None
    if not argv or argv[0] != "validate-draft":
        service = build_runtime().producer_service
    status, output = run_cli(argv, service=service)
    stream = sys.stdout if status == 0 else sys.stderr
    print(output, file=stream)
    return status


if __name__ == "__main__":
    raise SystemExit(main())
