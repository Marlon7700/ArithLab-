"""Parser de descenso recursivo para expresiones aritméticas.

compile_expression hace Parser(fichas).parse() y ast_to_text(arbol).
Si se elimina este módulo, no hay árbol ni precedencia de * y / sobre + y -.
"""

from dataclasses import dataclass

from .lexico import Token


@dataclass
class ASTNode:
    """Nodo del árbol: un número (hoja) o un operador con dos hijos.

    valor guarda el número o el símbolo. izquierda y derecha son los operandos.
    Si se elimina izquierda o derecha, el árbol no puede representar una operación.
    El JSON del SVG sigue usando value, left y right.
    """

    valor: int | str
    izquierda: "ASTNode | None" = None
    derecha: "ASTNode | None" = None

    def to_dict(self) -> dict:
        """Copia el nodo a un diccionario que el SVG y Gemini pueden recorrer.

        Si se elimina la recursión de izquierda o derecha, el JSON del árbol queda plano.
        """
        return {
            "value": self.valor,
            "left": self.izquierda.to_dict() if self.izquierda else None,
            "right": self.derecha.to_dict() if self.derecha else None,
        }


class Parser:
    """Lee la lista de fichas una sola vez, de izquierda a derecha.

    posicion es la ficha actual. Si se reinicia mal, parse() relee o se salta fichas.
    """

    def __init__(self, fichas: list[Token]):
        self.fichas = fichas
        self.posicion = 0

    def parse(self) -> ASTNode:
        """Arranca por expression() y exige haber consumido todas las fichas.

        Si se elimina la comprobación final, una fórmula como «10 +» a medias
        podría aceptarse cuando todavía quedan fichas sin leer.
        """
        if not self.fichas:
            raise ValueError("La entrada no contiene una expresión.")
        nodo = self.expression()
        if self.posicion != len(self.fichas):
            ficha = self.fichas[self.posicion]
            raise ValueError(
                f"Error sintáctico: se esperaba un número en la posición "
                f"{ficha.posicion}."
            )
        return nodo

    def expression(self) -> ASTNode:
        """Agrupa sumas y restas, cada una con menos prioridad que term().

        El bucle cuelga el nodo anterior a la izquierda: 100 - 20 - 5
        queda ((100 - 20) - 5). Si se elimina el while, solo se lee el primer término.
        """
        nodo = self.term()
        while self._matches("+", "-"):
            operador = self._consume().valor
            nodo = ASTNode(operador, nodo, self.term())
        return nodo

    def term(self) -> ASTNode:
        """Agrupa multiplicaciones y divisiones antes de devolver el nodo a expression().

        Por eso en 10 + 25 * 10 el producto es hijo de la suma.
        Si se elimina este nivel, * y / tendrían la misma prioridad que + y -.
        """
        nodo = self.factor()
        while self._matches("*", "/"):
            operador = self._consume().valor
            nodo = ASTNode(operador, nodo, self.factor())
        return nodo

    def factor(self) -> ASTNode:
        """Reconoce un número, que siempre es una hoja del árbol.

        Si se elimina la comprobación de tipo NÚMERO, un operador suelto
        se colaría como hoja.
        """
        if self.posicion >= len(self.fichas):
            raise ValueError("Error sintáctico: falta un número al final.")
        ficha = self._consume()
        if ficha.tipo != "NÚMERO":
            raise ValueError(
                f"Error sintáctico: se esperaba un número en la posición "
                f"{ficha.posicion}."
            )
        return ASTNode(ficha.valor)

    def _matches(self, *operadores: str) -> bool:
        return (
            self.posicion < len(self.fichas)
            and self.fichas[self.posicion].tipo == "OPERADOR"
            and self.fichas[self.posicion].valor in operadores
        )

    def _consume(self) -> Token:
        ficha = self.fichas[self.posicion]
        self.posicion += 1
        return ficha


def ast_to_text(nodo: ASTNode, prefijo: str = "", es_ultimo: bool = True) -> str:
    """Dibuja el árbol en texto bajo el SVG y se lo entrega también a Gemini.

    Si se elimina la recursión sobre los hijos, solo aparece la raíz.
    """
    resultado = f"{prefijo}{'└── ' if es_ultimo else '├── '}({nodo.valor})\n"
    hijos = [hijo for hijo in (nodo.izquierda, nodo.derecha) if hijo is not None]
    for indice_hijo, hijo in enumerate(hijos):
        resultado += ast_to_text(
            hijo,
            prefijo + ("    " if es_ultimo else "│   "),
            indice_hijo == len(hijos) - 1,
        )
    return resultado
