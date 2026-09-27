"""One compiler CLI for direct Python use and the npm launcher."""

import argparse
import sys
from pathlib import Path

from soda import __version__, compile_deck, export_html
from soda.compiler.diagnostics import SodaError


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    parser = argparse.ArgumentParser(
        prog="soda", description="Markdown 演示编译器",
        epilog="直接导出：soda deck.md [motion.soda] [-o output.html]；查看范例：npm 安装后运行 soda example。",
    )
    parser.add_argument("--version", "-v", action="version", version=f"SODA {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("check", "html"):
        cmd = sub.add_parser(name, help="检查内容与时间轴" if name == "check" else "导出 HTML")
        cmd.add_argument("source", help="Markdown 路径")
        cmd.add_argument("motion", nargs="?", help="可选 .soda 路径；省略时自动读取同名文件")
        cmd.add_argument("--static", action="store_true", help="忽略同名 .soda 动画")
        if name == "html":
            cmd.add_argument("-o", "--output", help="输出 HTML 路径；默认在源文件旁生成同名 .html")
            cmd.add_argument("--theme", help="nju（默认）、ipads 或相对 Markdown 的主题 JSON 路径")
            cmd.add_argument("--target", choices=("portable", "web"), default="portable")
    if argv and argv[0] not in {"check", "html", "--help", "-h", "--version", "-v"}:
        argv.insert(0, "html")
    args = parser.parse_args(argv)
    try:
        source = Path(args.source).expanduser().resolve()
        motion = Path(args.motion).expanduser().resolve() if args.motion else None
        deck = compile_deck(source, motion=motion, static=args.static)
        if args.command == "check":
            print(f"ok · {len(deck.program.slides)} 页")
        else:
            output = Path(args.output).expanduser() if args.output else source.with_suffix(".html")
            protected = {source, source.with_suffix(".soda"), motion}
            if output.resolve() in protected:
                raise ValueError("输出路径不能覆盖 Markdown 或动画源文件")
            print(export_html(deck, output, theme=args.theme, portable=args.target == "portable"))
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
