"""Analizador léxico del lenguaje aritmético.

main.compile_expression llama a tokenize con el texto de la fórmula.
Si se elimina este módulo, no existen tokens ni errores de carácter inválido.
"""

from dataclasses import asdict, dataclass

_OPERATORS = "+-*/"


@dataclass(frozen=True)
class Token:
    """Una pieza de la fórmula: número u operador, con su posición.

    type distingue NÚMERO de OPERADOR. position empieza en 1.
    Si se quita position, la interfaz y los errores no pueden señalar el carácter.
    """

    type: str
    value: int | str
    position: int


def tokenize(source: str) -> tuple[list[Token], list[str]]:
    """Recorre la fórmula de izquierda a derecha y separa tokens de errores.

    Los espacios se saltan. Los dígitos seguidos forman un solo número.
    Un carácter fuera de + - * / y de los dígitos se anota y el recorrido sigue,
    para reportar todos los errores de una vez. Si se elimina el avance de
    index, esta función no terminaría.
    """
    tokens: list[Token] = []
    errors: list[str] = []
    index = 0

    while index < len(source):
        character = source[index]

        if character.isspace():
            index += 1
            continue

        if character.isdigit():
            start = index
            while index < len(source) and source[index].isdigit():
                index += 1
            tokens.append(Token("NÚMERO", int(source[start:index]), start + 1))
            continue

        if character in _OPERATORS:
            tokens.append(Token("OPERADOR", character, index + 1))
        else:
            errors.append(
                f"Error léxico: carácter no válido '{character}' "
                f"en la posición {index + 1}."
            )
        index += 1

    return tokens, errors


def token_as_dict(token: Token) -> dict:
    """Convierte el token a diccionario para el JSON de /compilar.

    App.jsx lee type, value y position. Si se elimina, la lista de tokens
    no se puede serializar.
    """
    return asdict(token)
