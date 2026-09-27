"""Command-line conveniences over the same API used by Python callers."""

import argparse
import sys
from pathlib import Path

from soda import __version__, compile_deck, export_html
from soda.compiler.diagnostics import SodaError


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="soda", description="Markdown 演示编译器")
    parser.add_argument("--version", action="version", version=f"SODA {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("check", "html"):
        cmd = sub.add_parser(name, help="检查内容与时间轴" if name == "check" else "导出 HTML")
        cmd.add_argument("source")
        cmd.add_argument("--static", action="store_true", help="忽略同名 .soda 动画")
        if name == "html":
            cmd.add_argument("-o", "--output", required=True)
            cmd.add_argument("--theme", help="内置主题名或相对 Markdown 的 JSON 路径")
            cmd.add_argument("--target", choices=("portable", "web"), default="portable")
    args = parser.parse_args(argv)
    try:
        deck = compile_deck(args.source, static=args.static)
        if args.command == "check":
            print(f"ok · {len(deck.program.slides)} 页")
        else:
            print(export_html(deck, args.output, theme=args.theme, portable=args.target == "portable"))
        return 0
    except SodaError as exc:
        path = Path(exc.diagnostic.path)
        text = path.read_text(encoding="utf-8") if path.is_file() else ""
        print(exc.diagnostic.format(text), file=sys.stderr)
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
