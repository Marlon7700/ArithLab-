"""Explicaciones educativas opcionales mediante Gemini."""

import json
import os
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv


load_dotenv(Path(__file__).with_name(".env"))
_detected_models: list[str] = []
_detected_model: str | None = None


def detect_available_models(api_key: str) -> list[str]:
    """Consulta a Gemini para detectar modelos habilitados para generateContent."""
    global _detected_models
    if _detected_models:
        return _detected_models

    url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}&pageSize=100"
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=8) as response:
            payload = json.loads(response.read().decode("utf-8"))
        models: list[str] = []
        for item in payload.get("models", []):
            methods = item.get("supportedGenerationMethods", [])
            name = str(item.get("name", "")).removeprefix("models/")
            if name and "generateContent" in methods:
                models.append(name)
        _detected_models = models
    except Exception:
        _detected_models = []
    return _detected_models


def select_model(api_key: str) -> str | None:
    """Selecciona el modelo preferido y disponible en la API configurada."""
    global _detected_model
    if _detected_model:
        return _detected_model

    configured = os.getenv("GEMINI_MODEL", "").strip()
    available = detect_available_models(api_key)
    if not available:
        return configured or None

    preferred = [
        configured,
        "gemini-3.5-flash-lite",
        "gemini-2.5-flash-lite",
        "gemini-2.5-flash",
        "gemini-3.5-flash",
        "gemini-flash-lite-latest",
        "gemini-flash-latest",
        "gemini-3.8-flash",
    ]
    for model in preferred:
        if model and model in available:
            _detected_model = model
            return model

    for model in available:
        if "flash" in model.lower():
            _detected_model = model
            return model
    _detected_model = available[0]
    return _detected_model


def _extract_response_text(payload: dict) -> str:
    candidates = payload.get("candidates") or []
    if not candidates:
        return ""
    content = candidates[0].get("content") or {}
    parts = content.get("parts") or []
    return "".join(part.get("text", "") for part in parts).strip()


def format_number(value: int | float) -> str:
    return str(value) if isinstance(value, int) else f"{value:.10g}"


def build_local_explanations(source: str, result: dict) -> dict[str, str]:
    """Construye explicaciones educativas inmediatas sin depender de una red externa."""
    simbolos = result.get("simbolos") or []
    tipos = result.get("tipos") or []
    pasos = result.get("pasos_resolucion") or []
    instrucciones = result.get("codigo_maquina") or []
    resultado = result.get("resultado")

    if simbolos:
        symbols_text = ", ".join(
            f"{item['symbol']} -> {item['address']}" for item in simbolos
        )
        semantic = (
            f"El recorrido del AST identificó estos números únicos: {', '.join(str(item['symbol']) for item in simbolos)}.\n"
            f"Como aparecen una sola vez, cada símbolo recibe una dirección simulada según su primera aparición:\n"
            f"{symbols_text}.\n"
            "Si un número se repite, no se crea una dirección nueva y se reutiliza su símbolo existente."
        )
    else:
        semantic = "No hay símbolos semánticos disponibles porque la expresión no pudo analizarse."

    if pasos:
        priority_steps = [
            f"{index + 1}. {step['calculation']}. La expresión queda: {step['expression']}."
            for index, step in enumerate(pasos)
        ]
        explanation = (
            f"El resultado final de {source} es {format_number(resultado)}.\n\n"
            "1) Primero se resuelven las operaciones de multiplicación y división, "
            "respetando la precedencia más alta.\n"
            "2) Después se resuelven las sumas y restas de izquierda a derecha.\n"
            "3) Desarrollo exacto:\n"
            + "\n".join(priority_steps)
            + f"\n\nResultado final: {format_number(resultado)}."
        )
    else:
        explanation = f"No se pudo construir una explicación porque no hay un resultado válido para {source}."

    machine_lines: list[str] = []
    for index, instruction in enumerate(instrucciones, start=1):
        if instruction.startswith("PUSH "):
            machine_lines.append(
                f"{index}. PUSH {instruction.removeprefix('PUSH ')}: carga el operando en la pila."
            )
        elif instruction in ("ADD", "SUB", "MUL", "DIV"):
            operation = {
                "ADD": "suma",
                "SUB": "resta",
                "MUL": "multiplicación",
                "DIV": "división",
            }[instruction]
            machine_lines.append(
                f"{index}. {instruction}: extrae los dos últimos valores, ejecuta la {operation} y coloca el resultado."
            )
        elif instruction == "STORE R0":
            machine_lines.append(
                f"{index}. STORE R0: guarda el resultado final disponible en la cima de la pila."
            )

    machine = (
        "El código máquina se genera con recorrido postorden: primero se visita "
        "el subárbol izquierdo, después el derecho y finalmente el operador.\n\n"
        + "\n".join(machine_lines)
        + "\n\nAl finalizar, R0 contiene el resultado de la expresión."
    )
    return {
        "explicacion_ia": explanation,
        "explicacion_semantica": semantic,
        "explicacion_codigo_maquina": machine,
        "modelo_ia": "determinista",
    }


def generate_explanation(source: str, result: dict) -> dict[str, str]:
    """Genera una explicación basada en los datos reales del compilador."""
    local = build_local_explanations(source, result)
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        return local

    model = select_model(api_key)
    if not model:
        return {**local, "modelo_ia": "determinista"}

    safe_data = {
        "entrada": source,
        "tokens": result["tokens"],
        "ast_text": result["ast_text"],
        "simbolos": result["simbolos"],
        "tipos": result["tipos"],
        "resultado": result["resultado"],
        "codigo_maquina": result["codigo_maquina"],
        "pasos_resolucion": result["pasos_resolucion"],
    }
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    prompt = (
        "Eres un profesor de Teoría de Compiladores. Explica en español la "
        "evaluación de la siguiente expresión usando solo los datos reales "
        "entregados.\n"
        f"Fecha y hora de consulta (UTC): {now}. No afirmes que conoces datos "
        "externos; usa solo la expresión, el AST y los datos proporcionados.\n"
        "No inventes tokens, símbolos, pasos, resultados ni instrucciones.\n"
        "Primero resuelve multiplicaciones/divisiones y después sumas/restas "
        "de izquierda a derecha.\n"
        "Explica el código máquina como una máquina de pila: PUSH carga, "
        "operaciones reducen dos valores y STORE R0 guarda el resultado final.\n"
        "Devuelve exclusivamente JSON válido con estas tres claves:\n"
        "{\n"
        '  "explicacion_ia": "explicación paso a paso breve y clara",\n'
        '  "explicacion_semantica": "explicación clara de símbolos, direcciones y tipos",\n'
        '  "explicacion_codigo_maquina": "explicación detallada línea por línea"\n'
        "}\n"
        f"Datos reales:\n{json.dumps(safe_data, ensure_ascii=False)}"
    )
    body = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.2,
            "responseMimeType": "application/json",
        },
    }).encode("utf-8")
    fallback_models = [model]
    available = detect_available_models(api_key)
    for candidate in ["gemini-3.5-flash-lite", "gemini-3.8-flash", "gemini-2.5-flash-lite", "gemini-2.5-flash", "gemini-flash-lite-latest", "gemini-flash-latest"]:
        if candidate in available and candidate not in fallback_models:
            fallback_models.append(candidate)
    for candidate in fallback_models:
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{candidate}:generateContent?key={api_key}"
        )
        request = urllib.request.Request(
            url,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=4) as response:
                payload = json.loads(response.read().decode("utf-8"))
            text = _extract_response_text(payload)
            if not text:
                continue
            parsed = json.loads(text)
            if not isinstance(parsed, dict):
                continue
            ia = str(parsed.get("explicacion_ia", "")).strip()
            machine = str(parsed.get("explicacion_codigo_maquina", "")).strip()
            semantic = str(parsed.get("explicacion_semantica", "")).strip()
            return {
                "explicacion_ia": ia or local["explicacion_ia"],
                "explicacion_semantica": semantic or local["explicacion_semantica"],
                "explicacion_codigo_maquina": machine or local["explicacion_codigo_maquina"],
                "modelo_ia": candidate,
            }
        except Exception:
            continue
    return {**local, "modelo_ia": "determinista"}


def generate_error_explanation(source: str, errors: list[str], zero_based: bool) -> dict[str, str]:
    """Explica errores léxicos o sintácticos usando la API y una respuesta local rápida."""
    base = "desde cero (0)" if zero_based else "desde uno (1)"
    local = (
        f"La expresión «{source}» no pudo compilarse porque contiene errores.\n"
        f"Las posiciones se cuentan {base}.\n"
        + "\n".join(f"• {error}" for error in errors)
    )
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        return {"explicacion_error": local, "modelo_ia": "determinista"}

    model = select_model(api_key)
    if not model:
        return {"explicacion_error": local, "modelo_ia": "determinista"}

    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    prompt = (
        "Eres un profesor de Teoría de Compiladores. Explica en español por qué "
        "esta expresión produjo errores. Usa únicamente los errores entregados.\n"
        f"Fecha y hora de consulta (UTC): {now}. No inventes otros errores.\n"
        "Indica qué carácter o estructura es inválida, su posición conforme a la "
        "base indicada y qué cambio mínimo haría válida la fórmula.\n"
        "Si los errores son léxicos, distingue caracteres válidos e inválidos.\n"
        "Si el análisis sintáctico falla, explica el número u operador esperado.\n"
        "Devuelve únicamente texto plano en 2 o 3 párrafos breves.\n"
        f"Entrada: {source}\n"
        f"Base de posiciones: {base}\n"
        f"Errores reales: {json.dumps(errors, ensure_ascii=False)}"
    )
    body = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.1,
            "maxOutputTokens": 220,
            "responseMimeType": "text/plain",
        },
    }).encode("utf-8")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    request = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=4) as response:
            payload = json.loads(response.read().decode("utf-8"))
        text = _extract_response_text(payload)
        if text:
            return {"explicacion_error": text, "modelo_ia": model}
    except Exception:
        pass
    return {"explicacion_error": local, "modelo_ia": "determinista"}
