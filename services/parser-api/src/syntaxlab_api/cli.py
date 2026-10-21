"""Command-line utilities: model download, configuration check, OpenAPI export."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from syntaxlab_api.engines.registry import available_engines
from syntaxlab_api.languages.config import load_languages_file
from syntaxlab_api.languages.registry import LanguageRegistry
from syntaxlab_api.settings import get_settings


def _registry(languages: list[str] | None) -> LanguageRegistry:
    settings = get_settings()
    if languages:
        settings = settings.model_copy(update={"enabled_languages": languages})
    return LanguageRegistry.from_config(load_languages_file(settings.languages_file), settings)


def cmd_download(args: argparse.Namespace) -> int:
    for runtime in _registry(args.language):
        print(f"downloading models for {runtime.code} (engine={runtime.engine.name}) ...")
        runtime.engine.download()
    return 0


def cmd_check(args: argparse.Namespace) -> int:
    print("installed engines:", ", ".join(f"{k} -> {v}" for k, v in available_engines().items()))
    for runtime in _registry(args.language):
        caps = ", ".join(c.value for c in runtime.capabilities)
        print(f"{runtime.code}: engine={runtime.engine.name} capabilities=[{caps}]")
        if args.load:
            runtime.engine.load()
            print(f"  loaded OK ({runtime.engine.model_id})")
    return 0


def cmd_openapi(args: argparse.Namespace) -> int:
    from syntaxlab_api.main import create_app

    schema = create_app().openapi()
    text = json.dumps(schema, indent=2, ensure_ascii=False) + "\n"
    if args.output == "-":
        sys.stdout.write(text)
    else:
        Path(args.output).write_text(text, encoding="utf-8")
    return 0


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    parser = argparse.ArgumentParser(prog="syntaxlab-api")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("download-models", help="download models for configured languages")
    p.add_argument("--language", action="append", help="limit to a language code (repeatable)")
    p.set_defaults(func=cmd_download)

    p = sub.add_parser("check", help="validate configuration (and optionally load models)")
    p.add_argument("--language", action="append")
    p.add_argument("--load", action="store_true", help="also load each engine's models")
    p.set_defaults(func=cmd_check)

    p = sub.add_parser("openapi", help="write the OpenAPI schema as JSON")
    p.add_argument("output", nargs="?", default="-", help="file path, or '-' for stdout")
    p.set_defaults(func=cmd_openapi)

    args = parser.parse_args(argv)
    result: int = args.func(args)
    return result


if __name__ == "__main__":
    raise SystemExit(main())
