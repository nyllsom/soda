"""只需 Python：在仓库根目录运行 python examples/quickstart/build.py。"""

from pathlib import Path

from soda import compile_deck, export_html

source = Path(__file__).with_name("deck.md")
deck = compile_deck(source)
output = export_html(deck, "dist/quickstart.html")
print(output)
