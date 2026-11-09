"""Analizador léxico del lenguaje aritmético."""

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class Token:
    type: str
    value: int | str
    position: int


def tokenize(source: str) -> tuple[list[Token], list[str]]:
    """Convierte la entrada en tokens y reporta todos los caracteres inválidos."""
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

        if character in "+-*/":
            tokens.append(Token("OPERADOR", character, index + 1))
        else:
            errors.append(
                f"Error léxico: carácter no válido '{character}' "
                f"en la posición {index + 1}."
            )
        index += 1

    return tokens, errors


def token_as_dict(token: Token) -> dict:
    """Serializa un token para la respuesta JSON de FastAPI."""
    return asdict(token)
