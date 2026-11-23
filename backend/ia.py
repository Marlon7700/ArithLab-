"""Pide a Gemini la explicación de la fórmula que acaba de compilar el backend.

La interfaz no redacta estos textos. principal.py llama a generate_explanation
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

_OPERACIONES_PILA = {
    "ADD": ("+", lambda izquierda, derecha: izquierda + derecha),
    "SUB": ("-", lambda izquierda, derecha: izquierda - derecha),
    "MUL": ("*", lambda izquierda, derecha: izquierda * derecha),
    "DIV": ("/", lambda izquierda, derecha: izquierda / derecha),
}


def format_number(valor: int | float) -> str:
    """Normaliza un número para que el texto de la IA no arrastre ceros de más.

    La usan los pasos de la pila y el respaldo sin clave.
    Si se elimina, generate_explanation deja de poder armar el rastro de la pila.
    """
    return str(valor) if isinstance(valor, int) else f"{valor:.10g}"


def current_time_context(hora_cliente: str = "") -> dict[str, str]:
    """Arma el saludo con la hora de quien está usando el simulador.

    App.jsx envía hora_cliente desde el reloj del navegador. Si esa cadena
    viene vacía, se usa la hora local del equipo donde corre el backend.
    Si se elimina, el modelo no recibe la franja del día y responde igual
    a cualquier hora.
    """
    ahora = datetime.now().astimezone()
    hora = ahora.hour
    if hora < 12:
        saludo = "Buenos días"
    elif hora < 19:
        saludo = "Buenas tardes"
    else:
        saludo = "Buenas noches"
    texto = hora_cliente.strip().lower()
    for opcion in ("Buenos días", "Buenas tardes", "Buenas noches"):
        if texto.startswith(opcion.lower()):
            saludo = opcion
            break
    presentacion = f"{saludo}, hablas con la IA del simulador ArithLab+."
    return {"saludo": saludo, "presentacion": presentacion}


def _enumerate_nodes(arbol: dict | None) -> list[dict]:
    """Numera el AST en el mismo orden que las bolitas N1, N2, N3 del SVG.

    Recorre primero el nodo, luego el hijo izquierdo y después el derecho.
    Si se elimina, Gemini no puede nombrar cada nodo de la imagen del árbol.
    """
    nodos: list[dict] = []

    def recorrer(nodo: dict | None, padre: str | None) -> None:
        if not nodo:
            return
        etiqueta = f"N{len(nodos) + 1}"
        valor = nodo.get("value")
        nodos.append(
            {
                "id": etiqueta,
                "valor": valor,
                "tipo": "operador" if isinstance(valor, str) else "número",
                "padre": padre,
            }
        )
        recorrer(nodo.get("left"), etiqueta)
        recorrer(nodo.get("right"), etiqueta)

    recorrer(arbol, None)
    return nodos


def _stack_trace(instrucciones: list[str]) -> list[dict]:
    """Simula la máquina de pila para entregarle a Gemini el efecto real de cada línea.

    No redacta la explicación: solo calcula la pila antes y después.
    Si se elimina, el modelo tendría que imaginar el estado de la pila.
    """
    pila: list[int | float] = []
    rastro: list[dict] = []
    for instruccion in instrucciones:
        antes = [format_number(elemento) for elemento in pila]
        efecto = instruccion
        if instruccion.startswith("PUSH "):
            pila.append(int(instruccion.removeprefix("PUSH ")))
            efecto = f"entra {instruccion.removeprefix('PUSH ')}"
        elif instruccion in _OPERACIONES_PILA:
            derecha = pila.pop()
            izquierda = pila.pop()
            simbolo, operar = _OPERACIONES_PILA[instruccion]
            resultado = operar(izquierda, derecha)
            if isinstance(resultado, float) and resultado.is_integer():
                resultado = int(resultado)
            pila.append(resultado)
            efecto = (
                f"{format_number(izquierda)} {simbolo} {format_number(derecha)} "
                f"= {format_number(resultado)}"
            )
        elif instruccion == "STORE R0" and pila:
            efecto = f"R0 queda en {format_number(pila[-1])}"
        rastro.append(
            {
                "instruccion": instruccion,
                "pila_antes": antes,
                "pila_despues": [format_number(elemento) for elemento in pila],
                "calculo": efecto,
            }
        )
    return rastro


def _model_candidates() -> list[str]:
    """Orden de modelos: primero el de backend/.env y después alternativas reales.

    Si se elimina GEMINI_MODEL del .env, sigue intentando gemini-3.5-flash-lite.
    Si se elimina toda la función, no hay nombre de modelo para la URL de la API.
    """
    configurado = os.getenv("GEMINI_MODEL", "").strip()
    ordenados = [
        configurado,
        "gemini-3.5-flash-lite",
        "gemini-3.5-flash",
        "gemini-flash-lite-latest",
    ]
    unicos: list[str] = []
    for modelo in ordenados:
        if modelo and modelo not in unicos:
            unicos.append(modelo)
    return unicos


def _extract_response_text(carga: dict) -> str:
    """Lee el texto del primer candidato de generateContent.

    Si se elimina, la respuesta JSON de Google no se convierte en explicación.
    """
    candidatos = carga.get("candidates") or []
    if not candidatos:
        return ""
    contenido = candidatos[0].get("content") or {}
    partes = contenido.get("parts") or []
    return "".join(parte.get("text", "") for parte in partes).strip()


def _parse_json_object(texto: str) -> dict | None:
    """Acepta el JSON de Gemini aunque venga envuelto en un bloque ```json.

    Si se elimina, un texto válido se descartaría y la tarjeta quedaría vacía.
    """
    limpio = texto.strip()
    if limpio.startswith("```"):
        limpio = limpio.split("\n", 1)[-1]
        if "```" in limpio:
            limpio = limpio[: limpio.rfind("```")]
    try:
        objeto = json.loads(limpio)
    except json.JSONDecodeError:
        inicio = limpio.find("{")
        fin = limpio.rfind("}")
        if inicio < 0 or fin <= inicio:
            return None
        try:
            objeto = json.loads(limpio[inicio : fin + 1])
        except json.JSONDecodeError:
            return None
    return objeto if isinstance(objeto, dict) else None


def _post_prompt(clave: str, modelo: str, consigna: str, tipo_mime: str) -> str:
    """Hace un POST a generateContent con la clave del .env.

    La clave viaja solo en esta petición del backend; el navegador no la ve.
    Si se elimina el timeout o la URL, la llamada no sale y no hay texto de IA.
    """
    cuerpo = json.dumps(
        {
            "contents": [{"parts": [{"text": consigna}]}],
            "generationConfig": {
                "temperature": 0.4,
                "maxOutputTokens": 4096,
                "responseMimeType": tipo_mime,
            },
        }
    ).encode("utf-8")
    enlace = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{modelo}:generateContent?key={clave}"
    )
    peticion = urllib.request.Request(
        enlace,
        data=cuerpo,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(peticion, timeout=25) as respuesta:
        carga = json.loads(respuesta.read().decode("utf-8"))
    return _extract_response_text(carga)


def _ask_gemini(clave: str, consigna: str, tipo_mime: str) -> tuple[str, str]:
    """Prueba el modelo configurado y, si ese nombre falla, el siguiente de la lista.

    Devuelve (texto, nombre_del_modelo). Si se elimina el bucle, un 404 del
    modelo dejaría la explicación sin intento de respaldo.
    """
    ultimo_fallo = "Gemini no respondió."
    for modelo in _model_candidates():
        try:
            texto = _post_prompt(clave, modelo, consigna, tipo_mime)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as fallo:
            ultimo_fallo = str(fallo)
            continue
        if texto:
            return texto, modelo
        ultimo_fallo = f"{modelo} devolvió una respuesta vacía."
    raise RuntimeError(ultimo_fallo)


def _ai_failure(mensaje: str) -> dict[str, str]:
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
        "ia_error": mensaje,
    }


def build_local_explanations(fuente: str, compilado: dict) -> dict[str, str]:
    """Respaldo solo para cuando no existe GEMINI_API_KEY.

    Las pruebas unitarias quitan la clave a propósito y esperan este texto
    en los errores. Con la clave puesta, generate_explanation no llama aquí.
    Si se elimina, el modo sin clave no tiene nada que devolver.
    """
    simbolos = compilado.get("simbolos") or []
    pasos = compilado.get("pasos_resolucion") or []
    instrucciones = compilado.get("codigo_maquina") or []
    valor_final = compilado.get("resultado")
    if simbolos:
        texto_simbolos = ", ".join(
            f"{elemento['symbol']} -> {elemento['address']}" for elemento in simbolos
        )
        semantica = (
            f"Símbolos de {fuente}: {texto_simbolos}. "
            "Cada número distinto conserva una sola dirección."
        )
    else:
        semantica = "No hay símbolos porque la expresión no se analizó."
    if pasos:
        lineas = [
            f"{indice}. {paso['calculation']} => {paso['expression']}"
            for indice, paso in enumerate(pasos, start=1)
        ]
        explicacion = f"{fuente} = {format_number(valor_final)}\n" + "\n".join(lineas)
    else:
        explicacion = f"No hay pasos de resolución para {fuente}."
    lineas_maquina = [
        f"{indice}. {instruccion}"
        for indice, instruccion in enumerate(instrucciones, start=1)
    ]
    return {
        "explicacion_ia": explicacion,
        "explicacion_semantica": semantica,
        "explicacion_codigo_maquina": "\n".join(lineas_maquina),
        "explicacion_error": "",
        "modelo_ia": "determinista",
        "ia_error": "",
    }


def _facts(fuente: str, compilado: dict, reloj: dict[str, str]) -> dict:
    """Reúne solo datos que el compilador ya calculó, para que Gemini no invente cifras.

    Si se elimina un campo, esa parte deja de aparecer en la explicación.
    """
    return {
        "hora_de_quien_usa_el_simulador": reloj,
        "formula_exacta": fuente,
        "tokens": compilado.get("tokens") or [],
        "nodos_ast": _enumerate_nodes(compilado.get("ast")),
        "arbol_en_texto": compilado.get("ast_text") or "",
        "simbolos": compilado.get("simbolos") or [],
        "tipos": compilado.get("tipos") or [],
        "pasos_de_la_formula": compilado.get("pasos_resolucion") or [],
        "resultado_final": compilado.get("resultado"),
        "codigo_maquina": compilado.get("codigo_maquina") or [],
        "rastro_de_pila": _stack_trace(compilado.get("codigo_maquina") or []),
    }


def _explanation_prompt(fuente: str, compilado: dict, reloj: dict[str, str]) -> str:
    """Instrucciones de la explicación. El tono es de Gemini; los números salen de _facts.

    Si se quita la hora o la fórmula de este texto, la respuesta deja de
    depender del reloj o de la expresión que escribió el usuario.
    """
    return (
        "Eres Gemini, profesor de Teoría de Compiladores. Escribe en español "
        "con tus propias frases. No copies un guion fijo.\n"
        "Empieza CADA uno de los tres textos exactamente con "
        f"«{reloj['presentacion']}» y después sigue la explicación.\n"
        "No escribas la fecha, la hora en números, «Franja del día» ni frases "
        "como «la noche es el cierre», «abre el laboratorio» o «es un repaso».\n"
        "No menciones nombres internos como arbol_en_texto, rastro_de_pila "
        "o nodos_ast. Di «el árbol» y «la pila».\n"
        f"La fórmula exacta es: {fuente}\n"
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
        f"Datos reales:\n{json.dumps(_facts(fuente, compilado, reloj), ensure_ascii=False)}"
    )


def _order_by_marker(texto: str, patron: str) -> str:
    """Parte un párrafo en renglones cuando Gemini no dejó saltos de línea.

    Si el texto ya está en varios renglones, no se toca.
    """
    limpio = texto.replace("\\n", "\n").strip()
    if limpio.count("\n") >= 2:
        return limpio
    fragmentos = [
        fragmento.strip() for fragmento in re.split(patron, limpio) if fragmento.strip()
    ]
    if len(fragmentos) <= 1:
        return limpio
    return "\n".join(fragmentos)


def _order_machine_explanation(texto: str) -> str:
    """Separa cada instrucción en su propio bloque si Gemini las pegó en un párrafo.

    Si el texto ya trae varios saltos de línea, se deja igual. Si se elimina,
    la tarjeta de código máquina puede volver a mostrarse como un solo bloque.
    """
    limpio = texto.replace("\\n", "\n").strip()
    if limpio.count("\n") >= 4:
        return limpio
    fragmentos = re.split(
        r"(?=Instrucción\b|\d{2}\.\s+(?:PUSH|ADD|SUB|MUL|DIV|STORE))", limpio
    )
    bloques = [fragmento.strip() for fragmento in fragmentos if fragmento.strip()]
    if len(bloques) <= 1:
        return limpio
    return "\n\n".join(bloques)


def generate_explanation(
    fuente: str, compilado: dict, hora_cliente: str = ""
) -> dict[str, str]:
    """Pide a Gemini las tres explicaciones de una compilación correcta.

    La llama POST /explicar. Sin clave de API usa el respaldo local, que la
    interfaz no presenta como respuesta de Gemini. Si se elimina esta función,
    el botón Compilar no puede llenar las tarjetas de explicación.
    """
    clave = os.getenv("GEMINI_API_KEY", "").strip()
    if not clave:
        return build_local_explanations(fuente, compilado)

    reloj = current_time_context(hora_cliente)
    consigna = _explanation_prompt(fuente, compilado, reloj)
    try:
        texto, modelo = _ask_gemini(clave, consigna, "application/json")
    except RuntimeError as fallo:
        return _ai_failure(f"Gemini no pudo explicar la fórmula. {fallo}")

    objeto = _parse_json_object(texto)
    if not objeto:
        return _ai_failure(
            "Gemini contestó, pero no entregó el JSON de las tres explicaciones."
        )

    texto_ia = str(objeto.get("explicacion_ia", "")).strip()
    texto_arbol = _order_by_marker(
        str(objeto.get("explicacion_ast", "")).strip(), r"(?=El nodo\b)"
    )
    semantica = str(objeto.get("explicacion_semantica", "")).strip()
    tipos = _order_by_marker(
        str(objeto.get("explicacion_tipos", "")).strip(),
        r"(?=El número\b|Cabe destacar)",
    )
    maquina = _order_machine_explanation(
        str(objeto.get("explicacion_codigo_maquina", "")).strip()
    )
    if not texto_ia or not texto_arbol or not semantica or not tipos or not maquina:
        return _ai_failure(
            "Gemini omitió la explicación del árbol, de los tipos o del código máquina."
        )
    return {
        "explicacion_ia": texto_ia,
        "explicacion_ast": texto_arbol,
        "explicacion_semantica": semantica,
        "explicacion_tipos": tipos,
        "explicacion_codigo_maquina": maquina,
        "explicacion_error": "",
        "modelo_ia": modelo,
        "ia_error": "",
    }


_CAMPOS_ERROR = (
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
    fuente: str,
    errores: list[str],
    base_cero: bool,
    hora_cliente: str = "",
    fichas: list | None = None,
) -> dict[str, str]:
    """Pide a Gemini por qué falló cada fase: léxico, AST, tablas, pila y resultado.

    La llama POST /explicar-error. Sin clave, el texto de explicacion_error
    es el que esperan las pruebas. Si se elimina un campo del JSON, esa
    tarjeta de la interfaz se queda en el aviso vacío.
    """
    base = "desde cero (0)" if base_cero else "desde uno (1)"
    clave = os.getenv("GEMINI_API_KEY", "").strip()
    if not clave:
        texto_local = (
            f"La expresión «{fuente}» no pudo compilarse porque contiene errores.\n"
            f"Las posiciones se cuentan {base}.\n"
            + "\n".join(f"• {mensaje}" for mensaje in errores)
        )
        fase_detenida = "Esta fase no corre porque el análisis anterior ya falló."
        campos = {nombre: fase_detenida for nombre in _CAMPOS_ERROR}
        campos["explicacion_error"] = texto_local
        return {**campos, "modelo_ia": "determinista", "ia_error": ""}

    reloj = current_time_context(hora_cliente)
    consigna = (
        "Eres Gemini, profesor de Teoría de Compiladores. Escribe en español, "
        "con tus propias frases. No inventes errores, tokens ni resultados.\n"
        "Empieza SOLO explicacion_error exactamente con "
        f"«{reloj['presentacion']}» y después explica el error real, "
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
        f"Base de posiciones: {base}. Fórmula exacta: {fuente}\n"
        "Devuelve solo JSON con esas ocho claves.\n"
        f"Tokens reconocidos: {json.dumps(fichas or [], ensure_ascii=False)}\n"
        f"Errores reales: {json.dumps(errores, ensure_ascii=False)}"
    )
    try:
        texto, modelo = _ask_gemini(clave, consigna, "application/json")
    except RuntimeError as fallo:
        return _ai_failure(f"Gemini no pudo explicar el error. {fallo}")

    objeto = _parse_json_object(texto)
    if not objeto:
        return _ai_failure(
            "Gemini contestó, pero no entregó la explicación de cada fase."
        )
    campos = {nombre: str(objeto.get(nombre, "")).strip() for nombre in _CAMPOS_ERROR}
    if any(not campos[nombre] for nombre in _CAMPOS_ERROR):
        return _ai_failure("Gemini omitió la explicación de alguna fase con error.")
    return {**campos, "modelo_ia": modelo, "ia_error": ""}
