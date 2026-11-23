"""API FastAPI del simulador de compilador aritmético.

/compilar solo calcula tokens, AST, tablas, código máquina y resultado.
Las frases de las tarjetas salen de /explicar y /explicar-error, que llaman
a Gemini. Si se elimina la importación de gemini, esas dos rutas dejan de existir.
"""

import re

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .gemini import generate_error_explanation, generate_explanation
from .lexer import Token, token_as_dict, tokenize
from .parser import Parser, ast_to_text
from .semantic import build_resolution_steps, build_tables, evaluate, generate_machine_code

app = FastAPI(title="ArithLab+ API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[],
    allow_origin_regex=r"(https?://(localhost|127\.0\.0\.1)(:\d+)?|https://([a-z0-9-]+\.)*vercel\.app)$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict:
    return {"ok": True, "service": "arithlab-backend"}


class CompileRequest(BaseModel):
    """Cuerpo que envía App.jsx al compilar o al pedir la explicación.

    hora_cliente es el reloj del navegador. Si se elimina ese campo, Gemini
    solo ve la hora del servidor y no la de quien está frente a la pantalla.
    """

    source: str = Field(default="", max_length=2000)
    zero_based: bool = Field(default=False)
    hora_cliente: str = Field(default="", max_length=180)


def _shift_position(match: re.Match[str]) -> str:
    """Resta 1 a la posición escrita en un mensaje de error."""
    return f"posición {int(match.group(1)) - 1}"


def _convert_error_positions(errors: list[str], zero_based: bool) -> list[str]:
    """Pasa las posiciones de base 1 a base 0 cuando el cliente lo pide."""
    if not zero_based:
        return errors
    return [re.sub(r"posición (\d+)", _shift_position, error) for error in errors]


@app.post("/compilar")
def compile_expression(request: CompileRequest) -> dict:
    """Ejecuta lexer, parser, tablas, evaluación y código máquina.

    No redacta la explicación: deja esos campos vacíos para que /explicar
    los llene con Gemini. Si se elimina el llamado a tokenize o a Parser,
    la respuesta llega sin tokens o sin árbol.
    """
    tokens, lexical_errors = tokenize(request.source)
    if request.zero_based:
        tokens = [
            Token(token.type, token.value, token.position - 1)
            for token in tokens
        ]
        lexical_errors = _convert_error_positions(lexical_errors, True)
    response = {
        "tokens": [token_as_dict(token) for token in tokens],
        "ast": None,
        "ast_text": "",
        "simbolos": [],
        "tipos": [],
        "errores": lexical_errors,
        "resultado": None,
        "codigo_maquina": [],
        "pasos_resolucion": [],
        "explicacion_ia": "",
        "explicacion_semantica": "",
        "explicacion_codigo_maquina": "",
        "modelo_ia": "pendiente",
        "explicacion_error": "",
        "ia_error": "",
        "base_posiciones": 0 if request.zero_based else 1,
    }

    if not request.source.strip():
        response["errores"] = ["La entrada está vacía. Escribe una expresión aritmética."]
        return response
    if lexical_errors:
        return response

    try:
        ast = Parser(tokens).parse()
        symbols, types = build_tables(ast)
        response.update(
            ast=ast.to_dict(),
            ast_text=ast_to_text(ast),
            simbolos=symbols,
            tipos=types,
            resultado=evaluate(ast),
            codigo_maquina=generate_machine_code(ast),
            pasos_resolucion=build_resolution_steps(ast),
        )
    except (ValueError, ZeroDivisionError) as error:
        response["errores"] = [str(error)]
    return response


@app.post("/explicar")
def explain_expression(request: CompileRequest) -> dict:
    """Vuelve a compilar y le pasa a Gemini los datos reales y la hora del cliente.

    App.jsx llama esta ruta justo después de /compilar. Si se elimina,
    las tarjetas se quedan en el mensaje de espera.
    """
    compiled = compile_expression(request)
    if compiled.get("errores") or compiled.get("ast") is None:
        return {
            "explicacion_ia": "",
            "explicacion_semantica": "",
            "explicacion_codigo_maquina": "",
            "modelo_ia": "error",
            "ia_error": "No hay una fórmula válida para que Gemini la explique.",
        }
    return generate_explanation(request.source, compiled, request.hora_cliente)


@app.post("/explicar-error")
def explain_error(request: CompileRequest) -> dict:
    """Pide a Gemini el porqué de los errores léxicos o sintácticos.

    Si se elimina, la vista Errores solo lista el mensaje del lexer.
    """
    compiled = compile_expression(request)
    if not compiled.get("errores"):
        return {
            "explicacion_error": "La expresión no contiene errores.",
            "modelo_ia": "determinista",
            "ia_error": "",
        }
    return generate_error_explanation(
        request.source,
        compiled["errores"],
        request.zero_based,
        request.hora_cliente,
        compiled.get("tokens") or [],
    )
