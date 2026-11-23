# ArithLab+

Simulador interactivo de un compilador aritmético para el proyecto final de Teoría de Compiladores. La lógica está implementada en Python y la interfaz en React + Vite. El diseño toma como referencia el HTML entregado, pero se reorganiza en una aplicación de componentes, con AST en SVG y reporte imprimible a PDF.

## Estructura

```text
package.json       # comando único para frontend + backend
models/             # ejemplos JSON del AST y respuesta de la API
backend/
  lexico.py      # tokens y errores léxicos
  sintactico.py  # descenso recursivo y AST
  semantico.py   # tablas, evaluación y código máquina de pila
  ia.py          # explicaciones de Gemini
  principal.py   # API POST /compilar
  pruebas.py
frontend/
  src/App.jsx    # interfaz y flujo interactivo
  src/styles.css # tema oscuro, responsive y variables de diseño
  package.json
```

La respuesta de `/compilar` incluye `codigo_maquina`: instrucciones de una máquina de pila (`PUSH`, `ADD`, `SUB`, `MUL`, `DIV`, `STORE R0`). La interfaz las muestra junto con una explicación progresiva del proceso de construcción del AST.

La carpeta `node_modules/` se genera automáticamente con `npm install`; no se debe crear ni editar manualmente.

## Ejecución

### Opción recomendada: una sola terminal (Windows)

Desde la carpeta raíz:

```powershell
npm install
npm run install:all
npm run dev
```

El frontend quedará en `http://localhost:5173` y FastAPI en `http://localhost:8000`.

También puedes ejecutar `INICIAR_ARITHLAB.bat` haciendo doble clic en ese archivo.

Si aparece un error antiguo en el navegador, detén la terminal anterior con `Ctrl+C`, cierra la pestaña y vuelve a abrir `http://localhost:5173`. No abras `frontend/dist/index.html` directamente.

### Backend

```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
pip install -r backend/requirements.txt
python -m uvicorn backend.principal:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Abrir `http://localhost:5173`. El botón **Descargar reporte** abre un documento con formato listo para guardar como PDF desde el diálogo de impresión del navegador.

Para iniciar frontend y backend en una sola terminal:

```bash
cd frontend
npm install
npm run dev:all
```

La opción manual requiere dos terminales: FastAPI en `http://localhost:8000` y Vite en `http://localhost:5173`.

## Conectar Gemini

Gemini se ejecuta únicamente en el backend. La clave nunca se coloca en React ni se publica en el navegador.

1. Crea una clave en Google AI Studio:
   `https://aistudio.google.com/apikey`
2. En Windows PowerShell, antes de iniciar el backend:

```powershell
$env:GEMINI_API_KEY="PEGA_AQUI_TU_CLAVE"
$env:GEMINI_MODEL="gemini-2.5-flash"
python -m uvicorn backend.principal:app --reload --port 8000
```

Para Render, agrega estas variables en **Environment**:

```text
GEMINI_API_KEY=tu-clave
GEMINI_MODEL=gemini-2.5-flash
```

Si `GEMINI_API_KEY` no está configurada, el sistema sigue funcionando con las explicaciones locales deterministas.

## Sustentación

1. **Léxico:** recorre la cadena, agrupa dígitos en números, reconoce operadores y reporta todos los caracteres inválidos con posición.
2. **Sintaxis:** `expression()` procesa `+/-`, `term()` procesa `*/` y `factor()` reconoce números. Los bucles producen asociación izquierda.
3. **Semántica:** recorre el AST en preorden para registrar cada número una sola vez con `dir_n`; cada símbolo recibe tipo `entero`.
4. **Evaluación:** recorre recursivamente el árbol y devuelve el resultado opcional, controlando división por cero.

## Pruebas

Desde la raíz:

```bash
python -m unittest backend.pruebas
```
