"""Parser de descenso recursivo para expresiones aritméticas.

compile_expression hace Parser(tokens).parse() y ast_to_text(ast).
Si se elimina este módulo, no hay árbol ni precedencia de * y / sobre + y -.
"""

from dataclasses import dataclass

from .lexer import Token


@dataclass
class ASTNode:
    """Nodo del árbol: un número (hoja) o un operador con dos hijos.

    value guarda el número o el símbolo. left y right son los operandos.
    Si se elimina left o right, el árbol no puede representar una operación.
    """

    value: int | str
    left: "ASTNode | None" = None
    right: "ASTNode | None" = None

    def to_dict(self) -> dict:
        """Copia el nodo a un diccionario que el SVG y Gemini pueden recorrer.

        Si se elimina la recursión de left o right, el JSON del árbol queda plano.
        """
        return {
            "value": self.value,
            "left": self.left.to_dict() if self.left else None,
            "right": self.right.to_dict() if self.right else None,
        }


class Parser:
    """Lee la lista de tokens una sola vez, de izquierda a derecha.

    position es el token actual. Si se reinicia mal, parse() relee o se salta tokens.
    """

    def __init__(self, tokens: list[Token]):
        self.tokens = tokens
        self.position = 0

    def parse(self) -> ASTNode:
        """Arranca por expression() y exige haber consumido todos los tokens.

        Si se elimina la comprobación final, una fórmula como «10 +» a medias
        podría aceptarse cuando todavía quedan tokens sin leer.
        """
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
        """Agrupa sumas y restas, cada una con menos prioridad que term().

        El bucle cuelga el nodo anterior a la izquierda: 100 - 20 - 5
        queda ((100 - 20) - 5). Si se elimina el while, solo se lee el primer término.
        """
        node = self.term()
        while self._matches("+", "-"):
            operator = self._consume().value
            node = ASTNode(operator, node, self.term())
        return node

    def term(self) -> ASTNode:
        """Agrupa multiplicaciones y divisiones antes de devolver el nodo a expression().

        Por eso en 10 + 25 * 10 el producto es hijo de la suma.
        Si se elimina este nivel, * y / tendrían la misma prioridad que + y -.
        """
        node = self.factor()
        while self._matches("*", "/"):
            operator = self._consume().value
            node = ASTNode(operator, node, self.factor())
        return node

    def factor(self) -> ASTNode:
        """Reconoce un número, que siempre es una hoja del árbol.

        Si se elimina la comprobación de tipo NÚMERO, un operador suelto
        se colaría como hoja.
        """
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
    """Dibuja el árbol en texto bajo el SVG y se lo entrega también a Gemini.

    Si se elimina la recursión sobre los hijos, solo aparece la raíz.
    """
    result = f"{prefix}{'└── ' if is_tail else '├── '}({node.value})\n"
    children = [child for child in (node.left, node.right) if child is not None]
    for child_index, child in enumerate(children):
        result += ast_to_text(
            child,
            prefix + ("    " if is_tail else "│   "),
            child_index == len(children) - 1,
        )
    return result
