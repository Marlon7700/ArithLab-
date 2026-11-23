"""Pide a Gemini la explicación de la fórmula que acaba de compilar el backend.

La interfaz no redacta estos textos. main.py llama a generate_explanation
después de /compilar, y App.jsx muestra únicamente lo que devuelve este módulo
cuando el modelo responde. Si se elimina este archivo, las tres tarjetas
(semántica, fórmula y código máquina) se quedan vacías: no hay otro autor.
"""

import json
import os
import re
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv


# Carga backend/.env aunque uvicorn se arranque desde la raíz del proyecto.
# Si se elimina, GEMINI_API_KEY no entra al proceso y Gemini nunca se llama.
load_dotenv(Path(__file__).with_name(".env"))

_STACK_OPS = {
    "ADD": ("+", lambda left, right: left + right),
    "SUB": ("-", lambda left, right: left - right),
    "MUL": ("*", lambda left, right: left * right),
    "DIV": ("/", lambda left, right: left / right),
}

def format_number(value: int | float) -> str:
    """Normaliza un número para que el texto de la IA no arrastre ceros de más.

    La usan los pasos de la pila y el respaldo sin clave.
    Si se elimina, generate_explanation deja de poder armar el rastro de la pila.
    """
    return str(value) if isinstance(value, int) else f"{value:.10g}"


def current_time_context(hora_cliente: str = "") -> dict[str, str]:
    """Arma el saludo con la hora de quien está usando el simulador.

    App.jsx envía hora_cliente desde el reloj del navegador. Si esa cadena
    viene vacía, se usa la hora local del equipo donde corre el backend.
    Si se elimina, el modelo no recibe la franja del día y responde igual
    a cualquier hora.
    """
    now = datetime.now().astimezone()
    hour = now.hour
    if hour < 12:
        saludo = "Buenos días"
    elif hour < 19:
        saludo = "Buenas tardes"
    else:
        saludo = "Buenas noches"
    texto = hora_cliente.strip().lower()
    for option in ("Buenos días", "Buenas tardes", "Buenas noches"):
        if texto.startswith(option.lower()):
            saludo = option
            break
    presentacion = f"{saludo}, hablas con la IA del simulador ArithLab+."
    return {"saludo": saludo, "presentacion": presentacion}


def _enumerate_nodes(ast: dict | None) -> list[dict]:
    """Numera el AST en el mismo orden que las bolitas N1, N2, N3 del SVG.

    Recorre primero el nodo, luego el hijo izquierdo y después el derecho.
    Si se elimina, Gemini no puede nombrar cada nodo de la imagen del árbol.
    """
    nodes: list[dict] = []

    def walk(node: dict | None, parent: str | None) -> None:
        if not node:
            return
        label = f"N{len(nodes) + 1}"
        value = node.get("value")
        nodes.append({
            "id": label,
            "valor": value,
            "tipo": "operador" if isinstance(value, str) else "número",
            "padre": parent,
        })
        walk(node.get("left"), label)
        walk(node.get("right"), label)

    walk(ast, None)
    return nodes


def _stack_trace(instructions: list[str]) -> list[dict]:
    """Simula la máquina de pila para entregarle a Gemini el efecto real de cada línea.

    No redacta la explicación: solo calcula la pila antes y después.
    Si se elimina, el modelo tendría que imaginar el estado de la pila.
    """
    stack: list[int | float] = []
    trace: list[dict] = []
    for instruction in instructions:
        before = [format_number(item) for item in stack]
        effect = instruction
        if instruction.startswith("PUSH "):
            stack.append(int(instruction.removeprefix("PUSH ")))
            effect = f"entra {instruction.removeprefix('PUSH ')}"
        elif instruction in _STACK_OPS:
            right = stack.pop()
            left = stack.pop()
            symbol, operate = _STACK_OPS[instruction]
            result = operate(left, right)
            if isinstance(result, float) and result.is_integer():
                result = int(result)
            stack.append(result)
            effect = (
                f"{format_number(left)} {symbol} {format_number(right)} "
                f"= {format_number(result)}"
            )
        elif instruction == "STORE R0" and stack:
            effect = f"R0 queda en {format_number(stack[-1])}"
        trace.append({
            "instruccion": instruction,
            "pila_antes": before,
            "pila_despues": [format_number(item) for item in stack],
            "calculo": effect,
        })
    return trace


def _model_candidates() -> list[str]:
    """Orden de modelos: primero el de backend/.env y después alternativas reales.

    Si se elimina GEMINI_MODEL del .env, sigue intentando gemini-3.5-flash-lite.
    Si se elimina toda la función, no hay nombre de modelo para la URL de la API.
    """
    configured = os.getenv("GEMINI_MODEL", "").strip()
    ordered = [
        configured,
        "gemini-3.5-flash-lite",
        "gemini-3.5-flash",
        "gemini-flash-lite-latest",
    ]
    unique: list[str] = []
    for model in ordered:
        if model and model not in unique:
            unique.append(model)
    return unique


def _extract_response_text(payload: dict) -> str:
    """Lee el texto del primer candidato de generateContent.

    Si se elimina, la respuesta JSON de Google no se convierte en explicación.
    """
    candidates = payload.get("candidates") or []
    if not candidates:
        return ""
    content = candidates[0].get("content") or {}
    parts = content.get("parts") or []
    return "".join(part.get("text", "") for part in parts).strip()


def _parse_json_object(text: str) -> dict | None:
    """Acepta el JSON de Gemini aunque venga envuelto en un bloque ```json.

    Si se elimina, un texto válido se descartaría y la tarjeta quedaría vacía.
    """
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[-1]
        if "```" in cleaned:
            cleaned = cleaned[:cleaned.rfind("```")]
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start < 0 or end <= start:
            return None
        try:
            parsed = json.loads(cleaned[start:end + 1])
        except json.JSONDecodeError:
            return None
    return parsed if isinstance(parsed, dict) else None


def _post_prompt(api_key: str, model: str, prompt: str, mime: str) -> str:
    """Hace un POST a generateContent con la clave del .env.

    La clave viaja solo en esta petición del backend; el navegador no la ve.
    Si se elimina el timeout o la URL, la llamada no sale y no hay texto de IA.
    """
    body = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.4,
            "maxOutputTokens": 4096,
            "responseMimeType": mime,
        },
    }).encode("utf-8")
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{model}:generateContent?key={api_key}"
    )
    request = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=25) as response:
        payload = json.loads(response.read().decode("utf-8"))
    return _extract_response_text(payload)


def _ask_gemini(api_key: str, prompt: str, mime: str) -> tuple[str, str]:
    """Prueba el modelo configurado y, si ese nombre falla, el siguiente de la lista.

    Devuelve (texto, nombre_del_modelo). Si se elimina el bucle, un 404 del
    modelo dejaría la explicación sin intento de respaldo.
    """
    last_error = "Gemini no respondió."
    for model in _model_candidates():
        try:
            text = _post_prompt(api_key, model, prompt, mime)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
            last_error = str(error)
            continue
        if text:
            return text, model
        last_error = f"{model} devolvió una respuesta vacía."
    raise RuntimeError(last_error)


def _ai_failure(message: str) -> dict[str, str]:
    """Respuesta vacía cuando la API no contesta.

    No rellena las tarjetas con un texto escrito en el código.
    Si se elimina, un fallo de red volvería a mostrar párrafos locales.
    """
    return {
        "explicacion_ia": "",
        "explicacion_semantica": "",
        "explicacion_codigo_maquina": "",
        "explicacion_error": "",
        "modelo_ia": "error",
        "ia_error": message,
    }


def build_local_explanations(source: str, result: dict) -> dict[str, str]:
    """Respaldo solo para cuando no existe GEMINI_API_KEY.

    Las pruebas unitarias quitan la clave a propósito y esperan este texto
    en los errores. Con la clave puesta, generate_explanation no llama aquí.
    Si se elimina, el modo sin clave no tiene nada que devolver.
    """
    simbolos = result.get("simbolos") or []
    pasos = result.get("pasos_resolucion") or []
    instrucciones = result.get("codigo_maquina") or []
    resultado = result.get("resultado")
    if simbolos:
        symbols_text = ", ".join(
            f"{item['symbol']} -> {item['address']}" for item in simbolos
        )
        semantic = (
            f"Símbolos de {source}: {symbols_text}. "
            "Cada número distinto conserva una sola dirección."
        )
    else:
        semantic = "No hay símbolos porque la expresión no se analizó."
    if pasos:
        lines = [
            f"{index}. {step['calculation']} => {step['expression']}"
            for index, step in enumerate(pasos, start=1)
        ]
        explanation = f"{source} = {format_number(resultado)}\n" + "\n".join(lines)
    else:
        explanation = f"No hay pasos de resolución para {source}."
    machine_lines = [f"{index}. {instruction}" for index, instruction in enumerate(instrucciones, start=1)]
    return {
        "explicacion_ia": explanation,
        "explicacion_semantica": semantic,
        "explicacion_codigo_maquina": "\n".join(machine_lines),
        "explicacion_error": "",
        "modelo_ia": "determinista",
        "ia_error": "",
    }


def _facts(source: str, result: dict, clock: dict[str, str]) -> dict:
    """Reúne solo datos que el compilador ya calculó, para que Gemini no invente cifras.

    Si se elimina un campo, esa parte deja de aparecer en la explicación.
    """
    return {
        "hora_de_quien_usa_el_simulador": clock,
        "formula_exacta": source,
        "tokens": result.get("tokens") or [],
        "nodos_ast": _enumerate_nodes(result.get("ast")),
        "arbol_en_texto": result.get("ast_text") or "",
        "simbolos": result.get("simbolos") or [],
        "tipos": result.get("tipos") or [],
        "pasos_de_la_formula": result.get("pasos_resolucion") or [],
        "resultado_final": result.get("resultado"),
        "codigo_maquina": result.get("codigo_maquina") or [],
        "rastro_de_pila": _stack_trace(result.get("codigo_maquina") or []),
    }


def _explanation_prompt(source: str, result: dict, clock: dict[str, str]) -> str:
    """Instrucciones de la explicación. El tono es de Gemini; los números salen de _facts.

    Si se quita la hora o la fórmula de este texto, la respuesta deja de
    depender del reloj o de la expresión que escribió el usuario.
    """
    return (
        "Eres Gemini, profesor de Teoría de Compiladores. Escribe en español "
        "con tus propias frases. No copies un guion fijo.\n"
        "Empieza CADA uno de los tres textos exactamente con "
        f"«{clock['presentacion']}» y después sigue la explicación.\n"
        "No escribas la fecha, la hora en números, «Franja del día» ni frases "
        "como «la noche es el cierre», «abre el laboratorio» o «es un repaso».\n"
        "No menciones nombres internos como arbol_en_texto, rastro_de_pila "
        "o nodos_ast. Di «el árbol» y «la pila».\n"
        f"La fórmula exacta es: {source}\n"
        "Usa exclusivamente los datos JSON. No cambies tokens, nodos, "
        "direcciones, tipos, pasos, resultado ni instrucciones.\n"
        "explicacion_ia: fórmula exacta, luego cada nodo N1, N2... diciendo "
        "quién es su padre, y después la fórmula reducida paso a paso. Cada "
        "paso debe repetir calculation y la expresión que queda. Separa cada "
        "paso con un salto de línea.\n"
        "explicacion_ast: explica por qué el árbol tiene esa forma. Di que * y / "
        "quedan más abajo que + y - por la precedencia, y que las operaciones "
        "iguales se agrupan de izquierda a derecha. Después, un renglón por nodo "
        "del arbol_en_texto: qué valor tiene, quién es su padre y por qué está ahí.\n"
        "explicacion_semantica: fórmula exacta y, símbolo por símbolo, el "
        "número, su dirección dir_n y su tipo. Si un número se repite en la "
        "fórmula, explica que reutiliza la misma dirección. Un renglón por símbolo.\n"
        "explicacion_tipos: recorre la tabla de tipos de arriba abajo. Un renglón "
        "por símbolo: el número, la fila y por qué su tipo es entero. Cierra "
        "diciendo que un número repetido no crea otra fila.\n"
        "explicacion_codigo_maquina: después de la frase inicial, una instrucción "
        "por bloque y una línea en blanco entre bloques. Cada bloque tiene "
        "exactamente estas cuatro líneas, con los datos de rastro_de_pila:\n"
        "01. INSTRUCCION\n"
        "Pila anterior: ...\n"
        "Qué hace: ...\n"
        "Pila después: ...\n"
        "No escribas todas las instrucciones en el mismo párrafo.\n"
        "Devuelve solo JSON con las claves explicacion_ia, explicacion_ast, "
        "explicacion_semantica, explicacion_tipos y explicacion_codigo_maquina.\n"
        f"Datos reales:\n{json.dumps(_facts(source, result, clock), ensure_ascii=False)}"
    )


def _order_by_marker(text: str, pattern: str) -> str:
    """Parte un párrafo en renglones cuando Gemini no dejó saltos de línea.

    Si el texto ya está en varios renglones, no se toca.
    """
    cleaned = text.replace("\\n", "\n").strip()
    if cleaned.count("\n") >= 2:
        return cleaned
    chunks = [chunk.strip() for chunk in re.split(pattern, cleaned) if chunk.strip()]
    if len(chunks) <= 1:
        return cleaned
    return "\n".join(chunks)


def _order_machine_explanation(text: str) -> str:
    """Separa cada instrucción en su propio bloque si Gemini las pegó en un párrafo.

    Si el texto ya trae varios saltos de línea, se deja igual. Si se elimina,
    la tarjeta de código máquina puede volver a mostrarse como un solo bloque.
    """
    cleaned = text.replace("\\n", "\n").strip()
    if cleaned.count("\n") >= 4:
        return cleaned
    chunks = re.split(r"(?=Instrucción\b|\d{2}\.\s+(?:PUSH|ADD|SUB|MUL|DIV|STORE))", cleaned)
    blocks = [chunk.strip() for chunk in chunks if chunk.strip()]
    if len(blocks) <= 1:
        return cleaned
    return "\n\n".join(blocks)


def generate_explanation(source: str, result: dict, hora_cliente: str = "") -> dict[str, str]:
    """Pide a Gemini las tres explicaciones de una compilación correcta.

    La llama POST /explicar. Sin clave de API usa el respaldo local, que la
    interfaz no presenta como respuesta de Gemini. Si se elimina esta función,
    el botón Compilar no puede llenar las tarjetas de explicación.
    """
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        return build_local_explanations(source, result)

    clock = current_time_context(hora_cliente)
    prompt = _explanation_prompt(source, result, clock)
    try:
        text, model = _ask_gemini(api_key, prompt, "application/json")
    except RuntimeError as error:
        return _ai_failure(f"Gemini no pudo explicar la fórmula. {error}")

    parsed = _parse_json_object(text)
    if not parsed:
        return _ai_failure("Gemini contestó, pero no entregó el JSON de las tres explicaciones.")

    ia = str(parsed.get("explicacion_ia", "")).strip()
    ast = _order_by_marker(str(parsed.get("explicacion_ast", "")).strip(), r"(?=El nodo\b)")
    semantic = str(parsed.get("explicacion_semantica", "")).strip()
    types = _order_by_marker(str(parsed.get("explicacion_tipos", "")).strip(), r"(?=El número\b|Cabe destacar)")
    machine = _order_machine_explanation(str(parsed.get("explicacion_codigo_maquina", "")).strip())
    if not ia or not ast or not semantic or not types or not machine:
        return _ai_failure("Gemini omitió la explicación del árbol, de los tipos o del código máquina.")
    return {
        "explicacion_ia": ia,
        "explicacion_ast": ast,
        "explicacion_semantica": semantic,
        "explicacion_tipos": types,
        "explicacion_codigo_maquina": machine,
        "explicacion_error": "",
        "modelo_ia": model,
        "ia_error": "",
    }


_ERROR_FIELDS = (
    "explicacion_error",
    "explicacion_tokens",
    "explicacion_ast",
    "explicacion_semantica",
    "explicacion_ia",
    "explicacion_tipos",
    "explicacion_codigo_maquina",
    "explicacion_resultado",
)


def generate_error_explanation(
    source: str,
    errors: list[str],
    zero_based: bool,
    hora_cliente: str = "",
    tokens: list | None = None,
) -> dict[str, str]:
    """Pide a Gemini por qué falló cada fase: léxico, AST, tablas, pila y resultado.

    La llama POST /explicar-error. Sin clave, el texto de explicacion_error
    es el que esperan las pruebas. Si se elimina un campo del JSON, esa
    tarjeta de la interfaz se queda en el aviso vacío.
    """
    base = "desde cero (0)" if zero_based else "desde uno (1)"
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        local = (
            f"La expresión «{source}» no pudo compilarse porque contiene errores.\n"
            f"Las posiciones se cuentan {base}.\n"
            + "\n".join(f"• {error}" for error in errors)
        )
        stopped = "Esta fase no corre porque el análisis anterior ya falló."
        fields = {name: stopped for name in _ERROR_FIELDS}
        fields["explicacion_error"] = local
        return {**fields, "modelo_ia": "determinista", "ia_error": ""}

    clock = current_time_context(hora_cliente)
    prompt = (
        "Eres Gemini, profesor de Teoría de Compiladores. Escribe en español, "
        "con tus propias frases. No inventes errores, tokens ni resultados.\n"
        "Empieza SOLO explicacion_error exactamente con "
        f"«{clock['presentacion']}» y después explica el error real, "
        "su posición y el cambio mínimo para dejar la fórmula válida.\n"
        "No escribas la fecha, la hora en números, «Franja del día» ni frases "
        "como «la noche es el cierre», «abre el laboratorio» o «es un repaso».\n"
        "Las otras claves NO repiten el saludo. Cada una explica, en un párrafo, "
        "por qué ESA fase queda vacía o incompleta a causa de los errores reales.\n"
        "Este compilador solo acepta números enteros y los operadores + - * /. "
        "No menciones identificadores, variables, alcance ni ejecutables.\n"
        "explicacion_tokens: qué números u operadores sí se reconocieron y "
        "qué caracteres no pueden ser token.\n"
        "explicacion_ast: por qué el parser no construye el árbol.\n"
        "explicacion_semantica: por qué no hay símbolos ni direcciones dir_n.\n"
        "explicacion_ia: por qué no se puede reducir la fórmula paso a paso.\n"
        "explicacion_tipos: por qué no hay tipos entero.\n"
        "explicacion_codigo_maquina: por qué no hay PUSH, ADD, SUB, MUL, DIV ni STORE R0.\n"
        "explicacion_resultado: por qué no hay un número final.\n"
        f"Base de posiciones: {base}. Fórmula exacta: {source}\n"
        "Devuelve solo JSON con esas ocho claves.\n"
        f"Tokens reconocidos: {json.dumps(tokens or [], ensure_ascii=False)}\n"
        f"Errores reales: {json.dumps(errors, ensure_ascii=False)}"
    )
    try:
        text, model = _ask_gemini(api_key, prompt, "application/json")
    except RuntimeError as error:
        return _ai_failure(f"Gemini no pudo explicar el error. {error}")

    parsed = _parse_json_object(text)
    if not parsed:
        return _ai_failure("Gemini contestó, pero no entregó la explicación de cada fase.")
    fields = {name: str(parsed.get(name, "")).strip() for name in _ERROR_FIELDS}
    if any(not fields[name] for name in _ERROR_FIELDS):
        return _ai_failure("Gemini omitió la explicación de alguna fase con error.")
    return {**fields, "modelo_ia": model, "ia_error": ""}
