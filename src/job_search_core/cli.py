"""Machine-facing command-line interface for Core platform operations."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from dataclasses import asdict, dataclass

import uvicorn

from job_search_core.app import component_info
from job_search_core.config import Settings


@dataclass(frozen=True)
class Envelope:
    """Versioned JSON CLI envelope that can evolve without parsing prose output."""

    schema_version: int
    ok: bool
    data: dict[str, str]


def build_parser() -> argparse.ArgumentParser:
    """Define stable commands while keeping human help separate from JSON output."""
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("info", help="print versioned component metadata as JSON")
    subparsers.add_parser("serve", help="run the Core HTTP development server")
    return parser


def info_payload() -> Envelope:
    """Build the version-1 JSON response for automation and host integrations."""
    health = component_info()
    return Envelope(
        schema_version=1,
        ok=True,
        data={"component": health.component, "status": health.status, "version": health.version},
    )


def main(argv: Sequence[str] | None = None) -> int:
    """Execute one CLI command and return a process-compatible exit code.

    ``info`` writes exactly one JSON object to stdout. ``serve`` delegates process
    lifecycle to Uvicorn using typed environment settings. Argparse errors retain
    their conventional exit code 2.
    """
    args = build_parser().parse_args(argv)
    if args.command == "info":
        print(json.dumps(asdict(info_payload()), ensure_ascii=False, sort_keys=True))
        return 0

    settings = Settings()
    uvicorn.run(
        "job_search_core.app:app",
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level.lower(),
        reload=False,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
