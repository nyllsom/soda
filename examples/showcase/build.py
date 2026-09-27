"""同一份内容导出两套主题；需要 Typst 和 esbuild。"""

from pathlib import Path

from soda import compile_deck, export_html

deck = compile_deck(Path(__file__).with_name("deck.md"))
print(export_html(deck, "dist/showcase.html"))
print(export_html(deck, "dist/showcase-ipads.html", theme="ipads"))
