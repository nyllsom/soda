from __future__ import annotations

from soda.compiler import ast
from soda.compiler.diagnostics import Diagnostic, ParseError
from soda.compiler.lexer import lex
from soda.compiler.span import Span
from soda.compiler.tokens import Token, TokenKind

_BINARY_PRECEDENCE = {
    TokenKind.OROR: 1,
    TokenKind.ANDAND: 2,
    TokenKind.EQEQ: 3,
    TokenKind.BANGEQ: 3,
    TokenKind.LT: 4,
    TokenKind.LTE: 4,
    TokenKind.GT: 4,
    TokenKind.GTE: 4,
    TokenKind.PLUS: 5,
    TokenKind.MINUS: 5,
    TokenKind.STAR: 6,
    TokenKind.SLASH: 6,
    TokenKind.PERCENT: 6,
}


class Parser:
    def __init__(self, tokens: list[Token], *, path: str = "<input>") -> None:
        self.tokens = tokens
        self.path = path
        self.index = 0

    @property
    def current(self) -> Token:
        return self.tokens[self.index]

    def _peek(self, offset: int = 1) -> Token:
        return self.tokens[min(self.index + offset, len(self.tokens) - 1)]

    def _advance(self) -> Token:
        token = self.current
        if token.kind is not TokenKind.EOF:
            self.index += 1
        return token

    def _match(self, *kinds: TokenKind) -> Token | None:
        if self.current.kind in kinds:
            return self._advance()
        return None

    def _expect(self, kind: TokenKind, message: str | None = None) -> Token:
        if self.current.kind is kind:
            return self._advance()
        raise ParseError(
            Diagnostic(message or f"expected {kind.name.lower()}", self.current.span, self.path)
        )

    def parse_program(self) -> ast.Program:
        start = self.current.span
        declarations: list[ast.Decl] = []
        while self.current.kind is not TokenKind.EOF:
            declarations.append(self._parse_top_decl())
        return ast.Program(Span.merge(start, self.current.span), tuple(declarations))

    def _parse_top_decl(self) -> ast.Decl:
        if self.current.kind is TokenKind.CONST:
            return self._parse_const()
        if self.current.kind is TokenKind.MOTION:
            return self._parse_motion()
        if self.current.kind is TokenKind.FLOW:
            return self._parse_flow()
        raise ParseError(
            Diagnostic(
                "expected const, motion, or flow declaration",
                self.current.span,
                self.path,
            )
        )

    def _parse_const(self) -> ast.ConstDecl:
        start = self._expect(TokenKind.CONST).span
        name = self._expect(TokenKind.IDENT, "expected constant name")
        type_ref = None
        if self._match(TokenKind.COLON):
            type_ref = self._parse_type_ref()
        self._expect(TokenKind.EQ, "expected '=' in constant declaration")
        value = self._parse_expression()
        end = self._expect(TokenKind.SEMICOLON, "expected ';' after constant").span
        return ast.ConstDecl(Span.merge(start, end), name.lexeme, value, type_ref)

    def _parse_motion(self) -> ast.MotionDecl:
        start = self._expect(TokenKind.MOTION).span
        slide = self._expect(TokenKind.IDENT, "expected slide id after 'motion'")
        timeline = self._parse_block()
        return ast.MotionDecl(Span.merge(start, timeline.span), slide.lexeme, timeline)

    def _parse_flow(self) -> ast.FlowDecl:
        start = self._expect(TokenKind.FLOW).span
        self._expect(TokenKind.LBRACE)
        edges: list[ast.FlowEdge] = []
        while self.current.kind is not TokenKind.RBRACE:
            if self.current.kind is TokenKind.EOF:
                raise ParseError(Diagnostic("unterminated flow block", self.current.span, self.path))
            source = self._expect(TokenKind.IDENT, "expected source slide name")
            self._expect(TokenKind.ARROW, "expected '->' in flow edge")
            target = self._expect(TokenKind.IDENT, "expected target slide name")
            transition = None
            if self._match(TokenKind.USING):
                transition = self._parse_expression()
            end = self._expect(TokenKind.SEMICOLON, "expected ';' after flow edge")
            edges.append(
                ast.FlowEdge(Span.merge(source.span, end.span), source.lexeme, target.lexeme, transition)
            )
        end = self._expect(TokenKind.RBRACE).span
        return ast.FlowDecl(Span.merge(start, end), tuple(edges))

    def _parse_block(self) -> ast.Block:
        start = self._expect(TokenKind.LBRACE, "expected '{'").span
        statements: list[ast.Stmt] = []
        while self.current.kind is not TokenKind.RBRACE:
            if self.current.kind is TokenKind.EOF:
                raise ParseError(Diagnostic("unterminated block", self.current.span, self.path))
            statements.append(self._parse_statement())
        end = self._expect(TokenKind.RBRACE).span
        return ast.Block(Span.merge(start, end), tuple(statements))

    def _parse_statement(self) -> ast.Stmt:
        if self._match(TokenKind.WAIT):
            start = self.tokens[self.index - 1].span
            duration = self._parse_expression()
            end = self._expect(TokenKind.SEMICOLON).span
            return ast.WaitStmt(Span.merge(start, end), duration)

        if self._match(TokenKind.STEP):
            start = self.tokens[self.index - 1].span
            label = None
            if self.current.kind is TokenKind.STRING:
                label = str(self._advance().value)
            body = self._parse_block()
            return ast.StepStmt(Span.merge(start, body.span), label, body)

        if self._match(TokenKind.PARALLEL):
            start = self.tokens[self.index - 1].span
            args: tuple[ast.CallArg, ...] = ()
            if self._match(TokenKind.LPAREN):
                args = self._parse_arguments_after_lparen()
            body = self._parse_block()
            return ast.ParallelStmt(Span.merge(start, body.span), args, body)

        expr = self._parse_expression()
        end = self._expect(TokenKind.SEMICOLON, "expected ';' after expression").span
        return ast.ExprStmt(Span.merge(expr.span, end), expr)

    def _parse_type_ref(self) -> ast.TypeRef:
        first = self._expect(TokenKind.IDENT, "expected type name")
        parts = [first.lexeme]
        end = first.span
        while self._match(TokenKind.DOT):
            item = self._expect(TokenKind.IDENT, "expected identifier after '.'")
            parts.append(item.lexeme)
            end = item.span
        args: list[ast.TypeRef] = []
        if self._match(TokenKind.LT):
            while True:
                args.append(self._parse_type_ref())
                if self._match(TokenKind.COMMA) is None:
                    break
            end = self._expect(TokenKind.GT, "expected '>' after type arguments").span
        return ast.TypeRef(Span.merge(first.span, end), tuple(parts), tuple(args))

    def _parse_expression(self, min_precedence: int = 1) -> ast.Expr:
        left = self._parse_unary()
        while True:
            precedence = _BINARY_PRECEDENCE.get(self.current.kind)
            if precedence is None or precedence < min_precedence:
                break
            op = self._advance()
            right = self._parse_expression(precedence + 1)
            left = ast.BinaryExpr(Span.merge(left.span, right.span), left, op.lexeme, right)
        return left

    def _parse_unary(self) -> ast.Expr:
        if self.current.kind in {TokenKind.BANG, TokenKind.MINUS, TokenKind.PLUS}:
            op = self._advance()
            operand = self._parse_unary()
            return ast.UnaryExpr(Span.merge(op.span, operand.span), op.lexeme, operand)
        return self._parse_postfix()

    def _parse_postfix(self) -> ast.Expr:
        expr = self._parse_primary()
        while True:
            if self._match(TokenKind.DOT):
                name = self._expect(TokenKind.IDENT, "expected member name after '.'")
                expr = ast.MemberExpr(Span.merge(expr.span, name.span), expr, name.lexeme)
                continue
            if self._match(TokenKind.LPAREN):
                args = self._parse_arguments_after_lparen()
                expr = ast.CallExpr(
                    Span.merge(expr.span, self.tokens[self.index - 1].span),
                    expr,
                    args,
                )
                continue
            if self._match(TokenKind.LBRACKET):
                index = self._parse_expression()
                end = self._expect(TokenKind.RBRACKET, "expected ']' after index").span
                expr = ast.IndexExpr(Span.merge(expr.span, end), expr, index)
                continue
            break
        return expr

    def _parse_arguments_after_lparen(self) -> tuple[ast.CallArg, ...]:
        args: list[ast.CallArg] = []
        saw_named = False
        if self.current.kind is not TokenKind.RPAREN:
            while True:
                name = None
                start = self.current.span
                if self.current.kind is TokenKind.IDENT and self._peek().kind is TokenKind.EQ:
                    name = self._advance().lexeme
                    self._advance()
                    saw_named = True
                elif saw_named:
                    raise ParseError(
                        Diagnostic(
                            "positional arguments cannot follow named arguments",
                            self.current.span,
                            self.path,
                        )
                    )
                value = self._parse_expression()
                args.append(ast.CallArg(Span.merge(start, value.span), value, name))
                if self._match(TokenKind.COMMA) is None:
                    break
                if self.current.kind is TokenKind.RPAREN:
                    break
        self._expect(TokenKind.RPAREN, "expected ')' after arguments")
        return tuple(args)

    def _parse_primary(self) -> ast.Expr:
        token = self.current
        if token.kind is TokenKind.INT:
            self._advance()
            return ast.LiteralExpr(token.span, token.value, "Int")
        if token.kind is TokenKind.FLOAT:
            self._advance()
            return ast.LiteralExpr(token.span, token.value, "Float")
        if token.kind is TokenKind.DURATION:
            self._advance()
            return ast.LiteralExpr(token.span, token.value, "Duration")
        if token.kind is TokenKind.STRING:
            self._advance()
            return ast.LiteralExpr(token.span, token.value, "String")
        if token.kind in {TokenKind.TRUE, TokenKind.FALSE}:
            self._advance()
            return ast.LiteralExpr(token.span, token.kind is TokenKind.TRUE, "Bool")
        if token.kind is TokenKind.IDENT:
            self._advance()
            return ast.NameExpr(token.span, token.lexeme)
        if self._match(TokenKind.LBRACKET):
            start = self.tokens[self.index - 1].span
            items: list[ast.Expr] = []
            if self.current.kind is not TokenKind.RBRACKET:
                while True:
                    items.append(self._parse_expression())
                    if self._match(TokenKind.COMMA) is None:
                        break
                    if self.current.kind is TokenKind.RBRACKET:
                        break
            end = self._expect(TokenKind.RBRACKET, "expected ']' after array").span
            return ast.ArrayExpr(Span.merge(start, end), tuple(items))
        if self._match(TokenKind.LPAREN):
            expr = self._parse_expression()
            self._expect(TokenKind.RPAREN, "expected ')' after expression")
            return expr
        raise ParseError(Diagnostic("expected expression", token.span, self.path))


def parse(source: str, *, path: str = "<input>") -> ast.Program:
    return Parser(lex(source, path=path), path=path).parse_program()
