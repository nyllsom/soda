from soda.compiler.lower import lower
from soda.compiler.parser import parse
from soda.compiler.semantics import check


def test_hir_contains_only_constants_motion_and_flow():
    program = parse(
        """
const T: Duration = 250ms;
motion demo {
    step "show" { title.fade_in(duration = T); }
}
flow { demo -> next using fade(duration = T); }
"""
    )
    objects = {
        "demo": {"demo": __import__("soda.compiler.typesys", fromlist=["SLIDE_OBJECT"]).SLIDE_OBJECT,
                 "title": __import__("soda.compiler.typesys", fromlist=["TEXT"]).TEXT},
        "next": {"next": __import__("soda.compiler.typesys", fromlist=["SLIDE_OBJECT"]).SLIDE_OBJECT,
                 "title": __import__("soda.compiler.typesys", fromlist=["TEXT"]).TEXT},
    }
    model = check(program, content_objects=objects)
    hir = lower(program, model)
    assert [(item.name, item.type) for item in hir.constants] == [("T", "Duration")]
    assert hir.motions[0].slide_name == "demo"
    assert hir.motions[0].timeline.statements[0].kind == "step"
    assert [(edge.source, edge.target) for edge in hir.flow] == [("demo", "next")]
