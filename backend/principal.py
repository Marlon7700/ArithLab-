"""API FastAPI del simulador de compilador aritmético.

/compilar solo calcula fichas, AST, tablas, código máquina y resultado.
Las frases de las tarjetas salen de /explicar y /explicar-error, que llaman
a Gemini. Si se elimina la importación de ia, esas dos rutas dejan de existir.
"""

import re

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import AliasChoices, BaseModel, ConfigDict, Field

from .ia import generate_error_explanation, generate_explanation
from .lexico import Token, token_as_dict, tokenize
from .sintactico import Parser, ast_to_text
from .semantico import (
    build_resolution_steps,
    build_tables,
    evaluate,
    generate_machine_code,
)

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
    fuente y base_cero aceptan también source y zero_based, que es lo que envía el navegador.
    """

    model_config = ConfigDict(populate_by_name=True)

    fuente: str = Field(
        default="",
        max_length=2000,
        validation_alias=AliasChoices("source", "fuente"),
    )
    base_cero: bool = Field(
        default=False,
        validation_alias=AliasChoices("zero_based", "base_cero"),
    )
    hora_cliente: str = Field(default="", max_length=180)


def _shift_position(coincidencia: re.Match[str]) -> str:
    """Resta 1 a la posición escrita en un mensaje de error."""
    return f"posición {int(coincidencia.group(1)) - 1}"


def _convert_error_positions(errores: list[str], base_cero: bool) -> list[str]:
    """Pasa las posiciones de base 1 a base 0 cuando el cliente lo pide."""
    if not base_cero:
        return errores
    return [re.sub(r"posición (\d+)", _shift_position, mensaje) for mensaje in errores]


@app.post("/compilar")
def compile_expression(solicitud: CompileRequest) -> dict:
    """Ejecuta lexer, parser, tablas, evaluación y código máquina.

    No redacta la explicación: deja esos campos vacíos para que /explicar
    los llene con Gemini. Si se elimina el llamado a tokenize o a Parser,
    la respuesta llega sin fichas o sin árbol.
    """
    fichas, errores_lexicos = tokenize(solicitud.fuente)
    if solicitud.base_cero:
        fichas = [
            Token(ficha.tipo, ficha.valor, ficha.posicion - 1) for ficha in fichas
        ]
        errores_lexicos = _convert_error_positions(errores_lexicos, True)
    respuesta = {
        "tokens": [token_as_dict(ficha) for ficha in fichas],
        "ast": None,
        "ast_text": "",
        "simbolos": [],
        "tipos": [],
        "errores": errores_lexicos,
        "resultado": None,
        "codigo_maquina": [],
        "pasos_resolucion": [],
        "explicacion_ia": "",
        "explicacion_semantica": "",
        "explicacion_codigo_maquina": "",
        "modelo_ia": "pendiente",
        "explicacion_error": "",
        "ia_error": "",
        "base_posiciones": 0 if solicitud.base_cero else 1,
    }

    if not solicitud.fuente.strip():
        respuesta["errores"] = [
            "La entrada está vacía. Escribe una expresión aritmética."
        ]
        return respuesta
    if errores_lexicos:
        return respuesta

    try:
        arbol = Parser(fichas).parse()
        simbolos, tipos = build_tables(arbol)
        respuesta.update(
            ast=arbol.to_dict(),
            ast_text=ast_to_text(arbol),
            simbolos=simbolos,
            tipos=tipos,
            resultado=evaluate(arbol),
            codigo_maquina=generate_machine_code(arbol),
            pasos_resolucion=build_resolution_steps(arbol),
        )
    except (ValueError, ZeroDivisionError) as fallo:
        respuesta["errores"] = [str(fallo)]
    return respuesta


@app.post("/explicar")
def explain_expression(solicitud: CompileRequest) -> dict:
    """Vuelve a compilar y le pasa a Gemini los datos reales y la hora del cliente.

    App.jsx llama esta ruta justo después de /compilar. Si se elimina,
    las tarjetas se quedan en el mensaje de espera.
    """
    compilado = compile_expression(solicitud)
    if compilado.get("errores") or compilado.get("ast") is None:
        return {
            "explicacion_ia": "",
            "explicacion_semantica": "",
            "explicacion_codigo_maquina": "",
            "modelo_ia": "error",
            "ia_error": "No hay una fórmula válida para que Gemini la explique.",
        }
    return generate_explanation(solicitud.fuente, compilado, solicitud.hora_cliente)


@app.post("/explicar-error")
def explain_error(solicitud: CompileRequest) -> dict:
    """Pide a Gemini el porqué de los errores léxicos o sintácticos.

    Si se elimina, la vista Errores solo lista el mensaje del lexer.
    """
    compilado = compile_expression(solicitud)
    if not compilado.get("errores"):
        return {
            "explicacion_error": "La expresión no contiene errores.",
            "modelo_ia": "determinista",
            "ia_error": "",
        }
    return generate_error_explanation(
        solicitud.fuente,
        compilado["errores"],
        solicitud.base_cero,
        solicitud.hora_cliente,
        compilado.get("tokens") or [],
    )
