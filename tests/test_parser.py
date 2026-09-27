import pytest

from soda.compiler import ast
from soda.compiler.diagnostics import ParseError
from soda.compiler.parser import parse


def test_parser_accepts_only_motion_language_surface():
    program = parse(
        """
const T: Duration = 300ms;
motion intro {
    step "enter" {
        parallel(duration = T) {
            title.fade_in();
            code.create(duration = 500ms);
        }
    }
}
flow { intro -> detail using fade(duration = 300ms); }
"""
    )
    assert [type(decl) for decl in program.declarations] == [
        ast.ConstDecl,
        ast.MotionDecl,
        ast.FlowDecl,
    ]


@pytest.mark.parametrize(
    "source",
    [
        "import zanim.std;",
        "fn helper() {}",
        "slide Demo {}",
        "let x = 1;",
    ],
)
def test_legacy_code_first_surface_is_rejected(source: str):
    with pytest.raises(ParseError, match="expected const, motion, or flow"):
        parse(source)
