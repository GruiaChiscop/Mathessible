from __future__ import annotations

from dataclasses import dataclass

from .ast import Atom, Binary, Fraction, Group, Node, Operator, Placeholder, Script


COMMANDS = {
    "alpha": "α",
    "beta": "β",
    "gamma": "γ",
    "delta": "δ",
    "infty": "∞",
    "neq": "≠",
    "le": "≤",
    "ge": "≥",
    "times": "×",
    "cdot": "·",
}


class ParseError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class Token:
    kind: str
    text: str
    start: int
    end: int


def tokenize(source: str) -> list[Token]:
    result: list[Token] = []
    index = 0
    while index < len(source):
        char = source[index]
        if char.isspace():
            index += 1
            continue
        if source.startswith("=>", index):
            result.append(Token("operator", "⇒", index, index + 2))
            index += 2
            continue
        if char == "\\":
            end = index + 1
            while end < len(source) and source[end].isalpha():
                end += 1
            name = source[index + 1 : end]
            if not name:
                result.append(Token("atom", char, index, index + 1))
                index += 1
                continue
            result.append(Token("atom", COMMANDS.get(name, f"\\{name}"), index, end))
            index = end
            continue
        if char.isdigit() or (char == "." and index + 1 < len(source) and source[index + 1].isdigit()):
            end = index + 1
            while end < len(source) and (source[end].isdigit() or source[end] == "."):
                end += 1
            result.append(Token("atom", source[index:end], index, end))
            index = end
            continue
        if char.isalpha() or ord(char) > 127:
            result.append(Token("atom", char, index, index + 1))
        elif char in "+-=⇒<>≤≥*×·/^_()":
            kind = "paren" if char in "()" else "operator"
            result.append(Token(kind, char, index, index + 1))
        else:
            result.append(Token("atom", char, index, index + 1))
        index += 1
    result.append(Token("eof", "", len(source), len(source)))
    return result


class Parser:
    def __init__(self, source: str):
        self.source = source
        self.tokens = tokenize(source)
        self.index = 0

    @property
    def current(self) -> Token:
        return self.tokens[self.index]

    def advance(self) -> Token:
        token = self.current
        self.index += 1
        return token

    def parse(self) -> Node:
        if self.current.kind == "eof":
            return Placeholder((0, 0))
        result = self.parse_relation()
        if self.current.kind != "eof":
            raise ParseError(f"Unexpected element at position {self.current.start}: {self.current.text!r}")
        return result

    def parse_relation(self) -> Node:
        left = self.parse_sum()
        while self.current.text in {"=", "⇒", "<", ">", "≤", "≥", "≠"}:
            operator = self.advance()
            right = self.parse_sum_or_placeholder(operator.end)
            op = Operator(operator.text, (operator.start, operator.end))
            left = Binary(op, left, right, (left.span[0], right.span[1]))
        return left

    def parse_sum(self) -> Node:
        left = self.parse_product()
        while self.current.text in {"+", "-"}:
            operator = self.advance()
            right = self.parse_product_or_placeholder(operator.end)
            op = Operator(operator.text, (operator.start, operator.end))
            left = Binary(op, left, right, (left.span[0], right.span[1]))
        return left

    def parse_sum_or_placeholder(self, position: int) -> Node:
        if self.current.kind == "eof" or self.current.text == ")":
            return Placeholder((position, position))
        return self.parse_sum()

    def parse_product_or_placeholder(self, position: int) -> Node:
        if self.current.kind == "eof" or self.current.text == ")":
            return Placeholder((position, position))
        return self.parse_product()

    def parse_product(self) -> Node:
        left = self.parse_script()
        while True:
            if self.current.text in {"*", "×", "·", "/"}:
                operator = self.advance()
                right = self.parse_script_or_placeholder(operator.end)
                if operator.text == "/":
                    left = Fraction(left, right, (left.span[0], right.span[1]))
                else:
                    op = Operator(operator.text, (operator.start, operator.end))
                    left = Binary(op, left, right, (left.span[0], right.span[1]))
                continue
            if self.current.kind == "atom" or self.current.text == "(":
                right = self.parse_script()
                op = Operator("⁢", (right.span[0], right.span[0]))
                left = Binary(op, left, right, (left.span[0], right.span[1]), implicit=True)
                continue
            break
        return left

    def parse_script_or_placeholder(self, position: int) -> Node:
        if self.current.kind == "eof" or self.current.text == ")":
            return Placeholder((position, position))
        return self.parse_script()

    def parse_script(self) -> Node:
        base = self.parse_primary()
        subscript: Node | None = None
        superscript: Node | None = None
        end = base.span[1]
        while self.current.text in {"_", "^"}:
            operator = self.advance()
            argument = self.parse_script_argument(operator.end)
            end = argument.span[1]
            if operator.text == "_":
                subscript = argument
            else:
                superscript = argument
        if subscript is None and superscript is None:
            return base
        return Script(base, subscript, superscript, (base.span[0], end))

    def parse_script_argument(self, position: int) -> Node:
        if self.current.kind == "eof" or self.current.text == ")":
            return Placeholder((position, position))
        return self.parse_primary()

    def parse_primary(self) -> Node:
        token = self.current
        if token.text == "(":
            opening = self.advance()
            if self.current.text == ")":
                closing = self.advance()
                return Group(Placeholder((opening.end, opening.end)), (opening.start, closing.end))
            body = self.parse_relation()
            if self.current.text == ")":
                closing = self.advance()
                return Group(body, (opening.start, closing.end))
            return Group(body, (opening.start, body.span[1]))
        if token.kind == "atom":
            self.advance()
            return Atom(token.text, (token.start, token.end))
        raise ParseError(f"Expected an operand at position {token.start}")


def parse_unicodemath(source: str) -> Node:
    return Parser(source).parse()
