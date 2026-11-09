"""Parser de descenso recursivo para expresiones aritméticas."""

from dataclasses import asdict, dataclass

from .lexer import Token


@dataclass
class ASTNode:
    value: int | str
    left: "ASTNode | None" = None
    right: "ASTNode | None" = None

    def to_dict(self) -> dict:
        return {
            "value": self.value,
            "left": self.left.to_dict() if self.left else None,
            "right": self.right.to_dict() if self.right else None,
        }


class Parser:
    def __init__(self, tokens: list[Token]):
        self.tokens = tokens
        self.position = 0

    def parse(self) -> ASTNode:
        if not self.tokens:
            raise ValueError("La entrada no contiene una expresión.")
        node = self.expression()
        if self.position != len(self.tokens):
            token = self.tokens[self.position]
            raise ValueError(
                f"Error sintáctico: se esperaba un número en la posición "
                f"{token.position}."
            )
        return node

    def expression(self) -> ASTNode:
        node = self.term()
        while self._matches("+", "-"):
            operator = self._consume().value
            node = ASTNode(operator, node, self.term())
        return node

    def term(self) -> ASTNode:
        node = self.factor()
        while self._matches("*", "/"):
            operator = self._consume().value
            node = ASTNode(operator, node, self.factor())
        return node

    def factor(self) -> ASTNode:
        if self.position >= len(self.tokens):
            raise ValueError("Error sintáctico: falta un número al final.")
        token = self._consume()
        if token.type != "NÚMERO":
            raise ValueError(
                f"Error sintáctico: se esperaba un número en la posición "
                f"{token.position}."
            )
        return ASTNode(token.value)

    def _matches(self, *operators: str) -> bool:
        return (
            self.position < len(self.tokens)
            and self.tokens[self.position].type == "OPERADOR"
            and self.tokens[self.position].value in operators
        )

    def _consume(self) -> Token:
        token = self.tokens[self.position]
        self.position += 1
        return token


def ast_to_text(node: ASTNode, prefix: str = "", is_tail: bool = True) -> str:
    """Genera una representación de árbol legible para sustentación."""
    result = f"{prefix}{'└── ' if is_tail else '├── '}({node.value})\n"
    children = [child for child in (node.left, node.right) if child is not None]
    for child_index, child in enumerate(children):
        result += ast_to_text(
            child,
            prefix + ("    " if is_tail else "│   "),
            child_index == len(children) - 1,
        )
    return result
