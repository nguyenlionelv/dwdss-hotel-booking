"""Compatibility entry point for run_pipeline.py --to dw."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.run_pipeline import main as pipeline_main  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    """Forward legacy runner arguments to the shared pipeline CLI."""
    arguments = sys.argv[1:] if argv is None else argv
    return pipeline_main(["--to", "dw", *arguments])


if __name__ == "__main__":
    raise SystemExit(main())
