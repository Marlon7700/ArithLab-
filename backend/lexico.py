"""Analizador léxico del lenguaje aritmético.

principal.compile_expression llama a tokenize con el texto de la fórmula.
Si se elimina este módulo, no existen fichas ni errores de carácter inválido.
"""

from dataclasses import dataclass

_OPERADORES = "+-*/"


@dataclass(frozen=True)
class Token:
    """Una pieza de la fórmula: número u operador, con su posición.

    tipo distingue NÚMERO de OPERADOR. posicion empieza en 1.
    Si se quita posicion, la interfaz y los errores no pueden señalar el carácter.
    El JSON que lee App.jsx sigue llamándose type, value y position.
    """

    tipo: str
    valor: int | str
    posicion: int


def tokenize(fuente: str) -> tuple[list[Token], list[str]]:
    """Recorre la fórmula de izquierda a derecha y separa fichas de errores.

    Los espacios se saltan. Los dígitos seguidos forman un solo número.
    Un carácter fuera de + - * / y de los dígitos se anota y el recorrido sigue,
    para reportar todos los errores de una vez. Si se elimina el avance de
    indice, esta función no terminaría.
    """
    fichas: list[Token] = []
    errores: list[str] = []
    indice = 0

    while indice < len(fuente):
        caracter = fuente[indice]

        if caracter.isspace():
            indice += 1
            continue

        if caracter.isdigit():
            inicio = indice
            while indice < len(fuente) and fuente[indice].isdigit():
                indice += 1
            fichas.append(Token("NÚMERO", int(fuente[inicio:indice]), inicio + 1))
            continue

        if caracter in _OPERADORES:
            fichas.append(Token("OPERADOR", caracter, indice + 1))
        else:
            errores.append(
                f"Error léxico: carácter no válido '{caracter}' "
                f"en la posición {indice + 1}."
            )
        indice += 1

    return fichas, errores


def token_as_dict(ficha: Token) -> dict:
    """Convierte la ficha al JSON de /compilar.

    App.jsx lee type, value y position. Si se elimina, la lista de fichas
    no se puede serializar.
    """
    return {"type": ficha.tipo, "value": ficha.valor, "position": ficha.posicion}
