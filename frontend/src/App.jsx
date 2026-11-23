import { useEffect, useMemo, useState, useRef } from "react";

// En desarrollo se llama directamente a FastAPI. En despliegue se configura
// VITE_API_URL con la URL pública del backend.
const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";
const examples = [
  ["Válido", "10 + 25 * 10 - 4"],
  ["Izquierda", "100 - 20 - 5"],
  ["Repetidos", "8 * 2 + 8 / 2"],
  ["Con error", "7 $ 3 & 2"],
];

const emptyResult = { tokens: [], ast: null, ast_text: "", simbolos: [], tipos: [], errores: [], resultado: null, codigo_maquina: [], pasos_resolucion: [], explicacion_ia: "", explicacion_semantica: "", explicacion_codigo_maquina: "", explicacion_error: "", modelo_ia: "determinista", base_posiciones: 1 };

const menuIcons = {
  Simulador: "▦",
  Tokens: "⌘",
  AST: "⌁",
  Tablas: "▤",
  Errores: "⚠",
  Teoría: "◈",
};

function countNodes(node) {
  return node ? 1 + countNodes(node.left) + countNodes(node.right) : 0;
}

function AstSvg({ node, activeToken }) {
  const [positions, setPositions] = useState({});
  const [connectionStep, setConnectionStep] = useState(-1);
  const [isBuilding, setIsBuilding] = useState(true);
  const dragRef = useRef(null);
  const nodes = [];
  function leafCount(current) {
    if (!current) return 0;
    if (!current.left && !current.right) return 1;
    return leafCount(current.left) + leafCount(current.right);
  }
  const svgWidth = Math.max(600, leafCount(node) * 94 + 60);
  useEffect(() => setPositions({}), [node]);
  function flatten(current, start, end, depth, parent = null, path = "root") {
    if (!current) return;
    const position = positions[path] || { x: (start + end) / 2, y: 38 + depth * 78 };
    const item = { ...current, x: position.x, y: position.y, parent, path };
    nodes.push(item);
    const leftLeaves = leafCount(current.left);
    const totalLeaves = Math.max(1, leafCount(current));
    const split = start + ((end - start) * leftLeaves) / totalLeaves;
    flatten(current.left, start, split, depth + 1, item, `${path}.left`);
    flatten(current.right, split, end, depth + 1, item, `${path}.right`);
  }
  flatten(node, 30, svgWidth - 30, 0);
  const height = Math.max(130, Math.max(...nodes.map((item) => item.y), 38) + 60);
  const connections = nodes.filter((item) => item.parent);
  useEffect(() => {
    setConnectionStep(-1);
    setIsBuilding(true);
    if ("speechSynthesis" in window) window.speechSynthesis.cancel();
    let cancelled = false;
    let fallbackTimer;
    const advance = (step) => {
      if (cancelled) return;
      if (step >= connections.length) {
        setConnectionStep(connections.length);
        setIsBuilding(false);
        return;
      }
      setConnectionStep(step);
      speakNode(connections[step], step, () => advance(step + 1));
    };
    const speakNode = (connection, step, onFinished) => {
      const value = connection?.value;
      const phrase = typeof value === "string"
        ? `Nodo ${nodes.indexOf(connection) + 1}. Operador ${value}.`
        : `Nodo ${nodes.indexOf(connection) + 1}. Número ${value}.`;
      if (!("speechSynthesis" in window)) {
        fallbackTimer = window.setTimeout(onFinished, 1400);
        return;
      }
      const utterance = new SpeechSynthesisUtterance(phrase);
      utterance.lang = "es-ES";
      utterance.rate = 0.9;
      utterance.pitch = 1.05;
      utterance.volume = 1;
      utterance.onend = () => {
        if (!cancelled) onFinished();
      };
      utterance.onerror = () => {
        if (!cancelled) onFinished();
      };
      window.speechSynthesis.speak(utterance);
    };
    const rootValue = node?.value;
    const rootPhrase = typeof rootValue === "string"
      ? `Nodo 1. Raíz, operador ${rootValue}.`
      : `Nodo 1. Raíz, número ${rootValue}.`;
    const start = () => {
      if (connections.length === 0) {
        setIsBuilding(false);
        return;
      }
      if (!("speechSynthesis" in window)) {
        advance(0);
        return;
      }
      const rootUtterance = new SpeechSynthesisUtterance(rootPhrase);
      rootUtterance.lang = "es-ES";
      rootUtterance.rate = 0.9;
      rootUtterance.pitch = 1.05;
      rootUtterance.onend = () => advance(0);
      rootUtterance.onerror = () => advance(0);
      window.speechSynthesis.speak(rootUtterance);
    };
    const startTimer = window.setTimeout(start, 350);
    return () => {
      cancelled = true;
      window.clearTimeout(startTimer);
      if (fallbackTimer) window.clearTimeout(fallbackTimer);
      if ("speechSynthesis" in window) window.speechSynthesis.cancel();
    };
  }, [node]);
  function moveNode(event) {
    if (!dragRef.current) return;
    const rect = event.currentTarget.getBoundingClientRect();
    const scaleX = svgWidth / rect.width;
    const scaleY = height / rect.height;
    const dx = (event.clientX - dragRef.current.clientX) * scaleX;
    const dy = (event.clientY - dragRef.current.clientY) * scaleY;
    const movedPaths = nodes.filter((item) => item.path === dragRef.current.path || item.path.startsWith(`${dragRef.current.path}.`));
    setPositions((current) => {
      const next = { ...current };
      movedPaths.forEach((item) => {
        const currentPosition = current[item.path] || { x: item.x, y: item.y };
        next[item.path] = { x: currentPosition.x + dx, y: currentPosition.y + dy };
      });
      return next;
    });
    dragRef.current.clientX = event.clientX;
    dragRef.current.clientY = event.clientY;
  }
  function stopMoving() {
    dragRef.current = null;
  }
  return (
    <div className="ast-3d-scene">
      <div className="ast-3d-grid" />
      {isBuilding && <div className="ast-build-status">
        <span className="ast-pulse" />
        {connectionStep < 0
          ? "Preparando conexiones..."
          : connectionStep < connections.length
            ? `Nodo ${nodes.indexOf(connections[connectionStep].parent) + 1} conectando a nodo ${nodes.indexOf(connections[connectionStep]) + 1} · voz IA activa`
            : "Conexiones completas"}
      </div>}
      <svg className="ast-svg" viewBox={`0 0 ${svgWidth} ${height}`} role="img" aria-label="Árbol de sintaxis abstracta" onPointerMove={moveNode} onPointerUp={stopMoving} onPointerLeave={stopMoving}>
      {connections.map((item, connectionIndex) => {
        const isConnected = connectionIndex < connectionStep;
        const isConnecting = connectionIndex === connectionStep;
        const parentIndex = nodes.indexOf(item.parent);
        const childIndex = nodes.indexOf(item);
        const labelX = (item.parent.x + item.x) / 2;
        const labelY = (item.parent.y + item.y) / 2 - 7;
        return <g key={`connection-${item.path}`}>
          <line pathLength="1" x1={item.parent.x} y1={item.parent.y + 23} x2={item.x} y2={item.y - 23} className={`ast-edge ${isConnecting ? "connecting" : isConnected ? "connected" : "pending"}`} />
          {isConnecting && <text x={labelX} y={labelY} className="ast-connection-label">Nodo {parentIndex + 1} → Nodo {childIndex + 1}</text>}
        </g>;
      })}
      {nodes.map((item) => {
        const isOperator = typeof item.value === "string";
        const active = activeToken !== null && String(item.value) === String(activeToken);
        const nodeIndex = nodes.indexOf(item);
        const parentConnection = item.parent ? connections.indexOf(item) : -1;
        const assembled = !item.parent || parentConnection < connectionStep;
        const connecting = parentConnection === connectionStep;
        const nodeState = connecting ? "building" : assembled ? "assembled" : "waiting";
        return <g key={item.path} className={`ast-node ${nodeState}${active ? " active" : ""}`} onPointerDown={(event) => { event.currentTarget.setPointerCapture(event.pointerId); dragRef.current = { path: item.path, clientX: event.clientX, clientY: event.clientY }; }} >
          <circle cx={item.x} cy={item.y} r="23" className={isOperator ? "operator-node" : "number-node"} style={{ animationDelay: `${nodeIndex * 140}ms` }} />
          <text x={item.x} y={item.y + 5} textAnchor="middle" style={{ animationDelay: `${nodeIndex * 140 + 180}ms` }}>{item.value}</text>
          <text x={item.x} y={item.y + 39} textAnchor="middle" className="ast-node-id" style={{ animationDelay: `${nodeIndex * 140 + 260}ms` }}>N{nodeIndex + 1}</text>
        </g>;
      })}
      </svg>
      <span className="ast-depth-label">{isBuilding ? "AST / CONSTRUYENDO" : "AST / ARRASTRA LAS BOLITAS"}</span>
    </div>
  );
}

function Metric({ label, value, tone = "" }) {
  return <div className="metric-card"><span>{label}</span><strong className={tone}>{value}</strong></div>;
}

function AnimatedTitle({ children }) {
  return <span className="animated-title" aria-label={children}>
    {Array.from(children).map((character, index) => (
      <span className="animated-title-letter" style={{ animationDelay: `${index * 55}ms` }} key={`${character}-${index}`}>
        {character === " " ? "\u00a0" : character}
      </span>
    ))}
  </span>;
}

function BrandIcon() {
  return <svg className="brand-icon" viewBox="0 0 64 64" role="img" aria-label="Icono de ArithLab">
    <defs>
      <linearGradient id="brand-flask-gradient" x1="10" y1="8" x2="54" y2="58">
        <stop offset="0" stopColor="#5edbff" />
        <stop offset=".52" stopColor="#bd9cff" />
        <stop offset="1" stopColor="#f6dfa3" />
      </linearGradient>
      <filter id="brand-icon-glow"><feGaussianBlur stdDeviation="1.8" result="blur" /><feMerge><feMergeNode in="blur" /><feMergeNode in="SourceGraphic" /></feMerge></filter>
    </defs>
    <g fill="none" stroke="url(#brand-flask-gradient)" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" filter="url(#brand-icon-glow)">
      <path d="M25 8h14M29 8v17L14 49c-2 4 1 7 6 7h24c5 0 8-3 6-7L35 25V8" />
      <path d="M18 45c6-4 9 3 14-1s8-5 14 0" opacity=".8" />
    </g>
    <g fill="#bd9cff" stroke="#f7f8ff" strokeWidth="1.2">
      <circle cx="27" cy="37" r="3.2" /><circle cx="37" cy="31" r="3.2" /><circle cx="42" cy="43" r="3.2" />
    </g>
    <path d="M27 37l10-6 5 12" fill="none" stroke="#5edbff" strokeWidth="1.4" opacity=".9" />
    <path d="M50 12v12M44 18h12" stroke="#f6dfa3" strokeWidth="2.5" strokeLinecap="round" />
  </svg>;
}

function Table({ title, headers, rows, empty = "Sin datos todavía" }) {
  return <div className="panel table-panel">
    <div className="panel-heading"><h3>{title}</h3><span className="section-index">●</span></div>
    <div className="table-responsive"><table><thead><tr>{headers.map((header) => <th key={header}>{header}</th>)}</tr></thead>
      <tbody>{rows.length ? rows.map((row, index) => <tr key={index}>{row.map((cell, cellIndex) => <td key={cellIndex}>{cell}</td>)}</tr>) : <tr><td colSpan={headers.length} className="empty">{empty}</td></tr>}</tbody>
    </table></div>
  </div>;
}

function createReport(result, source) {
  const rows = result.tokens.map((token, index) => `<tr><td>${index + 1}</td><td>${token.type}</td><td>${token.value}</td></tr>`).join("");
  const symbols = result.simbolos.map((item) => `<tr><td>${item.symbol}</td><td>${item.address}</td></tr>`).join("");
  const types = result.tipos.map((item) => `<tr><td>${item.symbol}</td><td>${item.type}</td></tr>`).join("");
  const errors = result.errores.length ? `<section class="error"><h2>Errores</h2>${result.errores.map((error) => `<p>${error}</p>`).join("")}</section>` : "";
  function reportAstSvg(current, x, y, gap, lines = [], circles = [], path = "root") {
    if (!current) return { lines, circles };
    circles.push(`<circle cx="${x}" cy="${y}" r="22" class="${typeof current.value === "string" ? "op" : "num"}"/><text x="${x}" y="${y + 5}" text-anchor="middle">${current.value}</text>`);
    if (current.left) { lines.push(`<line x1="${x}" y1="${y + 22}" x2="${x - gap}" y2="${y + 78 - 22}"/>`); reportAstSvg(current.left, x - gap, y + 78, Math.max(28, gap / 1.8), lines, circles, `${path}.left`); }
    if (current.right) { lines.push(`<line x1="${x}" y1="${y + 22}" x2="${x + gap}" y2="${y + 78 - 22}"/>`); reportAstSvg(current.right, x + gap, y + 78, Math.max(28, gap / 1.8), lines, circles, `${path}.right`); }
    return { lines, circles };
  }
  const reportTree = result.ast ? reportAstSvg(result.ast, 300, 35, 155) : { lines: [], circles: [] };
  const summary = result.ast
    ? `La expresión ${source} se tokenizó correctamente. El parser aplicó precedencia: primero * y /, después + y -, y agrupó operaciones del mismo nivel de izquierda a derecha. El AST tiene ${countNodes(result.ast)} nodos. Finalmente, la máquina de pila ejecutó ${result.codigo_maquina.length} instrucciones y obtuvo ${result.resultado}.`
    : "No se pudo construir el AST porque la entrada contiene errores.";
  const resolution = (result.pasos_resolucion || []).map((step, index) => `<p><b>${index + 1}. ${step.priority === "prioritaria" ? "Operación prioritaria" : "Operación de izquierda a derecha"}:</b> ${step.calculation}<br>La expresión queda: <code>${step.expression}</code></p>`).join("");
  const semanticExplanation = result.ast
    ? `Se recorrió el AST para identificar cada número literal. Los valores únicos encontrados fueron ${result.simbolos.map((item) => item.symbol).join(", ") || "ninguno"}.
<br>Cada número aparece una sola vez en la tabla semántica y recibe una dirección simulada de memoria. Esto evita registros duplicados y permite identificar cada símbolo de forma única.`
    : "No se pudo construir la tabla semántica porque la expresión contiene errores.";
  const machineSteps = (result.codigo_maquina || []).map((instruction, index) => {
    const number = instruction.startsWith("PUSH ") ? instruction.slice(5) : "";
    const explanation = instruction === "ADD"
      ? "Retira los dos últimos valores de la pila y coloca su suma."
      : instruction === "SUB"
        ? "Retira los dos últimos valores y coloca el resultado de la resta."
        : instruction === "MUL"
          ? "Retira los dos últimos valores y coloca su producto."
          : instruction === "DIV"
            ? "Retira los dos últimos valores y coloca el cociente."
            : instruction === "STORE R0"
              ? "Guarda el resultado final de la pila en el registro R0."
              : `Carga el número ${number} en la pila como operando.`;
    return `<tr><td>${String(index + 1).padStart(2, "0")}</td><td><code>${instruction}</code></td><td>${explanation}</td></tr>`;
  }).join("");
  const html = `<!doctype html><html lang="es"><head><meta charset="utf-8"><title>Reporte ArithLab+</title>
    <style>
      *{box-sizing:border-box}@page{size:A4;margin:14mm}body{font-family:Arial,sans-serif;color:#202124;margin:0;background:white}main{padding:28px 38px}.brand{border-bottom:2px solid #d8ba78;padding-bottom:14px;margin-bottom:22px}h1{color:#604c2d;margin:0 0 5px;font-family:Georgia,serif}h2{color:#604c2d;border-bottom:1px solid #dfd3b8;padding-bottom:7px;margin:24px 0 12px;font-size:18px}.formula{font:18px monospace;background:#f8f2e7;border-left:4px solid #c6a665;padding:15px;border-radius:7px}.step-badge{display:inline-block;background:#604c2d;color:white;border-radius:20px;padding:5px 9px;font-size:11px;margin-right:8px}p,td,th{font-size:12px;line-height:1.6}table{border-collapse:collapse;width:100%;margin-bottom:16px}th{background:#604c2d;color:white}td,th{padding:9px;border:1px solid #ddd;text-align:left}.note{background:#f4f7ff;border:1px solid #bbc7df;border-radius:8px;padding:13px}.error{color:#a7353c;background:#fff0f0;border:1px solid #e6a4a8;padding:14px;border-radius:8px}.report-ast{width:100%;height:430px;background:#171718;border-radius:12px;border:1px solid #ddd}.report-ast line{stroke:#777;stroke-width:1.5}.report-ast circle{fill:#202022;stroke-width:2}.report-ast .num{stroke:#c79b42}.report-ast .op{stroke:#806bb0}.report-ast text{fill:white;font:14px monospace}.ast-text{background:#202124;color:#f4dfb0;border-radius:8px;padding:14px;white-space:pre-wrap;font:12px monospace}.resolution p{margin:7px 0}.result-box{background:#edf8f1;border:2px solid #6da785;border-radius:10px;padding:18px}.result-box strong{display:block;color:#28724a;font:700 34px monospace;margin-top:5px}@media print{main{padding:20px}.report-ast{break-inside:avoid}}
    </style></head>
    <body><main>
      <header class="brand"><h1>ArithLab+</h1><p>Proyecto final · Teoría de Compiladores · Reporte completo</p></header>
      ${errors}

      <h2><span class="step-badge">01</span>Entrada de expresión</h2>
      <p class="formula">${source || "(entrada vacía)"}</p>

      <h2><span class="step-badge">02</span>Tokens identificados</h2>
      <table><thead><tr><th>N.º</th><th>Tipo</th><th>Valor</th></tr></thead><tbody>${rows || '<tr><td colspan="3">Sin tokens disponibles</td></tr>'}</tbody></table>

      <h2><span class="step-badge">03</span>Árbol de Sintaxis Abstracta</h2>
      ${result.ast ? `<svg class="report-ast" viewBox="0 0 600 430">${reportTree.lines.join("")}${reportTree.circles.join("")}</svg><pre class="ast-text">${result.ast_text || "No disponible"}</pre><p class="note">El AST aplica primero <b>*</b> y <b>/</b>, después <b>+</b> y <b>-</b>, y agrupa las operaciones del mismo nivel de izquierda a derecha. Los operadores son nodos internos y los números son hojas.</p>` : '<p class="error">No se generó el AST porque la expresión contiene errores.</p>'}

      <h2><span class="step-badge">04</span>Tabla semántica y explicación</h2>
      <table><thead><tr><th>Símbolo</th><th>Dirección</th></tr></thead><tbody>${symbols || '<tr><td colspan="2">Sin símbolos disponibles</td></tr>'}</tbody></table>
      <p class="note">${semanticExplanation}</p>

      <h2><span class="step-badge">05</span>Cómo se construye la fórmula</h2>
      <div class="resolution">${resolution || "<p>No hay pasos de resolución disponibles.</p>"}</div>
      <p class="note">${summary}</p>

      <h2><span class="step-badge">06</span>Tabla de tipos</h2>
      <table><thead><tr><th>Símbolo</th><th>Tipo</th></tr></thead><tbody>${types || '<tr><td colspan="2">Sin tipos disponibles</td></tr>'}</tbody></table>

      <h2><span class="step-badge">07</span>Código máquina y explicación</h2>
      <p class="note">Las instrucciones se generan mediante recorrido postorden: primero se visitan los hijos izquierdo y derecho del nodo y al final se genera la operación del operador.</p>
      <table><thead><tr><th>N.º</th><th>Instrucción</th><th>Explicación</th></tr></thead><tbody>${machineSteps || '<tr><td colspan="3">No se generó código máquina</td></tr>'}</tbody></table>

      <h2><span class="step-badge">08</span>Resultado final</h2>
      <div class="result-box">Resultado obtenido<strong>${result.resultado ?? "No disponible"}</strong></div>
    </main><script>window.onload=()=>window.print()</script></body></html>`;
  const reportWindow = window.open("", "_blank");
  if (reportWindow) { reportWindow.document.write(html); reportWindow.document.close(); }
}

function downloadSectionReport(section, result, source) {
  const content = {
    Entrada: `<h2>Entrada</h2><p class="formula">${source || "(entrada vacía)"}</p>`,
    Tokens: `<h2>Tokens identificados</h2><table><tr><th>N.º</th><th>Tipo</th><th>Valor</th></tr>${result.tokens.map((token, index) => `<tr><td>${index + 1}</td><td>${token.type}</td><td>${token.value}</td></tr>`).join("")}</table>`,
    AST: `<h2>Árbol de Sintaxis Abstracta</h2><pre>${result.ast_text || "No generado"}</pre><p>El AST respeta la precedencia de * y / sobre + y -, y la asociatividad izquierda.</p>`,
    Semántica: `<h2>Tabla semántica</h2><table><tr><th>Símbolo</th><th>Dirección</th></tr>${result.simbolos.map((item) => `<tr><td>${item.symbol}</td><td>${item.address}</td></tr>`).join("")}</table><p>Los números únicos reciben una dirección simulada en orden de aparición.</p>`,
    Construcción: `<h2>Construcción paso a paso</h2>${(result.pasos_resolucion || []).map((stepItem, index) => `<p><b>${index + 1}.</b> ${stepItem.calculation}<br>Expresión: <code>${stepItem.expression}</code></p>`).join("")}`,
    Tipos: `<h2>Tabla de tipos</h2><table><tr><th>Símbolo</th><th>Tipo</th></tr>${result.tipos.map((item) => `<tr><td>${item.symbol}</td><td>${item.type}</td></tr>`).join("")}</table>`,
    "Código máquina": `<h2>Código máquina</h2><table><tr><th>N.º</th><th>Instrucción</th></tr>${(result.codigo_maquina || []).map((instruction, index) => `<tr><td>${index + 1}</td><td><code>${instruction}</code></td></tr>`).join("")}</table>`,
    Resultado: `<h2>Resultado final</h2><p><strong>${result.resultado ?? "No disponible"}</strong></p>`,
    Tablas: `<h2>Tabla de símbolos</h2><table><tr><th>Símbolo</th><th>Dirección</th></tr>${result.simbolos.map((item) => `<tr><td>${item.symbol}</td><td>${item.address}</td></tr>`).join("")}</table><h2>Tabla de tipos</h2><table><tr><th>Símbolo</th><th>Tipo</th></tr>${result.tipos.map((item) => `<tr><td>${item.symbol}</td><td>${item.type}</td></tr>`).join("")}</table>`,
    Errores: `<h2>Errores detectados</h2>${result.errores.length ? result.errores.map((error) => `<p class="error">${error}</p>`).join("") : "<p>No hay errores. La expresión es válida.</p>"}`,
    Teoría: `<h2>Fases del compilador</h2><ol><li>Léxico: convierte caracteres en tokens.</li><li>Sintáctico: construye el AST aplicando precedencia.</li><li>Semántico: crea símbolos y tipos.</li><li>Generación: produce código máquina de pila.</li></ol>`,
  }[section] || "";
  const reportWindow = window.open("", "_blank");
  if (!reportWindow) return;
  reportWindow.document.write(`<!doctype html><html lang="es"><head><meta charset="utf-8"><title>${section} - ArithLab+</title><style>body{font-family:Arial;color:#202124;margin:38px}h1{color:#8e6e3a}h2{border-bottom:2px solid #d5b77b;padding-bottom:7px;color:#604c2d}table{border-collapse:collapse;width:100%}td,th{padding:9px;border:1px solid #ddd;text-align:left}th{background:#604c2d;color:white}.formula{font:18px monospace;background:#f8f2e7;padding:15px}.error{color:#a7353c;background:#fff0f0;padding:12px}</style></head><body><h1>ArithLab+ · ${section}</h1><p class="formula">${source || "(entrada vacía)"}</p>${content}<script>window.onload=()=>window.print()</script></body></html>`);
  reportWindow.document.close();
}

function SectionDownload({ section, result, source }) {
  return <button className="download-button section-download" onClick={() => downloadSectionReport(section, result, source)}>↓ Descargar {section}</button>;
}

export default function App() {
  const [source, setSource] = useState("10 + 25 * 10 - 4");
  const [result, setResult] = useState(emptyResult);
  const [loading, setLoading] = useState(false);
  const [activeToken, setActiveToken] = useState(null);
  const [step, setStep] = useState(0);
  const [zeroBased, setZeroBased] = useState(false);
  const [section, setSection] = useState("Simulador");
  const [typedProcess, setTypedProcess] = useState("");

  const processText = result.ast
    ? (result.explicacion_ia || `El resultado final de la operación es ${result.resultado}.\n\nResolución paso a paso\nSiguiendo la jerarquía de las operaciones, primero resolvemos * y / y luego las sumas y restas de izquierda a derecha:\n\n${result.pasos_resolucion.map((stepItem, index) => `${index + 1}. ${stepItem.priority === "prioritaria" ? "Operación prioritaria" : "Operación de izquierda a derecha"}:\n${stepItem.calculation}\nLa expresión queda: ${stepItem.expression}`).join("\n\n")}\n\nEl AST representa este mismo orden: los operadores son nodos internos y los números son hojas. La máquina de pila traduce cada reducción a instrucciones y guarda el resultado final en R0.`)
    : "";
  const semanticExplanation = result.ast
    ? (result.explicacion_semantica || `Se recorrió el AST para identificar cada número literal. Los valores únicos encontrados fueron ${result.simbolos.map((item) => item.symbol).join(", ") || "ninguno"}.\n\nCada número aparece una sola vez en la tabla semántica. Su dirección simulada representa el lugar que ocuparía en memoria: ${result.simbolos.map((item) => `${item.symbol} → ${item.address}`).join(", ") || "sin símbolos"}.\n\nEsto permite reutilizar el mismo símbolo si el número vuelve a aparecer y evita crear registros duplicados.`)
    : "";
  const machineExplanation = result.codigo_maquina?.length
    ? (result.explicacion_codigo_maquina || `El AST se convierte a código máquina mediante recorrido postorden: primero se visita el hijo izquierdo, luego el hijo derecho y al final el operador.\n\n${result.codigo_maquina.map((instruction, index) => {
      const number = instruction.startsWith("PUSH ") ? instruction.slice(5) : "";
      const explanation = instruction === "ADD"
        ? "Retira los dos últimos valores de la pila y coloca su suma."
        : instruction === "SUB"
          ? "Retira los dos últimos valores y coloca el resultado de la resta."
          : instruction === "MUL"
            ? "Retira los dos últimos valores y coloca su producto."
            : instruction === "DIV"
              ? "Retira los dos últimos valores y coloca el cociente."
              : instruction === "STORE R0"
                ? "Guarda el resultado final de la pila en el registro R0."
                : `Carga el número ${number} en la pila como operando.`;
      return `${index + 1}. ${instruction}: ${explanation}`;
    }).join("\n\n")}\n\nPor esta razón, la pila representa los operandos temporalmente y cada instrucción reduce dos valores hasta obtener un resultado final.`)
    : "";

  useEffect(() => {
    setTypedProcess("");
    if (!processText) return undefined;
    let position = 0;
    const timer = window.setInterval(() => {
      position += 2;
      setTypedProcess(processText.slice(0, position));
      if (position >= processText.length) window.clearInterval(timer);
    }, 16);
    return () => window.clearInterval(timer);
  }, [processText]);

  async function compile() {
    setLoading(true);
    try {
      const response = await fetch(`${API_URL}/compilar`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ source, zero_based: zeroBased }) });
      if (!response.ok) {
        const detail = await response.text();
        throw new Error(`HTTP ${response.status}${detail ? `: ${detail.slice(0, 120)}` : ""}`);
      }
      const compiled = await response.json();
      setResult(compiled);
      const endpoint = compiled.errores.length ? "/explicar-error" : "/explicar";
      const controller = new AbortController();
      const timeout = window.setTimeout(() => controller.abort(), 5000);
      fetch(`${API_URL}${endpoint}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ source, zero_based: zeroBased }),
        signal: controller.signal,
      })
        .then((explanationResponse) => explanationResponse.ok ? explanationResponse.json() : null)
        .then((improved) => {
          if (!improved) return;
          setResult((current) => ({
            ...current,
            explicacion_ia: improved.explicacion_ia || current.explicacion_ia,
            explicacion_semantica: improved.explicacion_semantica || current.explicacion_semantica,
            explicacion_codigo_maquina: improved.explicacion_codigo_maquina || current.explicacion_codigo_maquina,
            explicacion_error: improved.explicacion_error || current.explicacion_error,
            modelo_ia: improved.modelo_ia || current.modelo_ia,
          }));
        })
        .catch(() => undefined)
        .finally(() => window.clearTimeout(timeout));
    } catch (error) {
      setResult({ ...emptyResult, errores: [`Backend no disponible. Ejecuta: python -m uvicorn backend.main:app --reload --port 8000 (${error.message})`] });
    } finally { setLoading(false); }
  }

  const metrics = useMemo(() => ({
    tokens: result.tokens.length,
    symbols: result.simbolos.length,
    nodes: countNodes(result.ast),
    status: result.errores.length ? "Error" : result.ast ? "Listo" : "—",
  }), [result]);
  const pipeline = ["Entrada", "Tokens", "AST", "Semántica", "Construcción", "Tipos", "Código", "Resultado"];
  const hasErrors = result.errores.length > 0;
  const stepMenu = [
    ["Entrada", "entrada-step", "▦"],
    ["Tokens", "tokens-step", "⌘"],
    ["AST", "ast-step", "⌁"],
    ["Semántica", "semantic-step", "Σ"],
    ["Construcción", "construction-step", "⚙"],
    ["Tipos", "types-step", "T"],
    ["Código máquina", "machine-step", "</>"],
    ["Resultado", "result-step", "✓"],
  ];
  function openStep(label, targetId) {
    const entry = stepMenu.findIndex(([name]) => name === label);
    setStep(entry);
    setSection("Simulador");
    window.setTimeout(() => {
      document.getElementById(targetId)?.scrollIntoView({ behavior: "smooth", block: "start" });
    }, 40);
    downloadSectionReport(label, result, source);
  }
  function moveStep(nextStep) {
    const bounded = Math.max(0, Math.min(7, nextStep));
    setStep(bounded);
    setSection("Simulador");
    window.setTimeout(() => {
      document.getElementById(stepMenu[bounded][1])?.scrollIntoView({ behavior: "smooth", block: "start" });
    }, 40);
  }

  return <div className="app-shell">
    <aside className="sidebar">
      <div className="brand"><div className="brand-mark"><BrandIcon /></div><div><h1>ArithLab<span>+</span></h1><p>Tokeniza. Parsea.<br />Entiende.</p></div></div>
      <nav>{stepMenu.map(([item, targetId, icon], index) => <button key={item} className={step === index ? "nav-item active" : "nav-item"} onClick={() => openStep(item, targetId)}><span className="nav-icon nav-step-icon" aria-hidden="true">{icon}</span><span className="nav-step-number">{String(index + 1).padStart(2, "0")}</span><span>{item}</span></button>)}</nav>
      <div className="sidebar-tools"><button className={section === "Errores" ? "nav-item active" : "nav-item"} onClick={() => setSection("Errores")}><span className="nav-icon" aria-hidden="true">⚠</span><span>Errores</span></button><button className={section === "Teoría" ? "nav-item active" : "nav-item"} onClick={() => setSection("Teoría")}><span className="nav-icon" aria-hidden="true">◈</span><span>Teoría</span></button></div>
      <div className="sidebar-foot"><span className="status-dot" /> API Python conectable<br /><small>IA: {result.modelo_ia || "determinista"}</small></div>
    </aside>
    <main className="main-content">
      <header className="topbar"><div><p className="eyebrow">LABORATORIO / {section.toUpperCase()}</p><h2><AnimatedTitle>Simulador de compilador aritmético</AnimatedTitle></h2></div><button className="download-button" onClick={() => createReport(result, source)}>↓ Descargar reporte</button></header>
      <section className="metrics"><Metric label="Tokens" value={metrics.tokens.toString().padStart(2, "0")} /><Metric label="Operandos únicos" value={metrics.symbols.toString().padStart(2, "0")} /><Metric label="Nodos del AST" value={metrics.nodes.toString().padStart(2, "0")} /><Metric label="Estado" value={metrics.status} tone={hasErrors ? "error-text" : "success-text"} /></section>
      <section className="pipeline panel"><div className="pipeline-line">{pipeline.map((item, index) => <button key={item} className={index <= step ? "pipeline-stage reached" : "pipeline-stage"} onClick={() => moveStep(index)}><span>{String(index + 1).padStart(2, "0")}</span><b>{item}</b>{index < pipeline.length - 1 && <i />}</button>)}</div><div className="step-controls"><span>Modo paso a paso</span><button onClick={() => moveStep(step - 1)}>←</button><button onClick={() => moveStep(step + 1)}>→</button></div></section>
      {section !== "Simulador" && <section className="section-view panel">
        <div className="section-view-header"><div><span className="kicker">VISTA / {section.toUpperCase()}</span><h3>{section === "Teoría" ? "Guía de teoría de compiladores" : `Resultados de ${section}`}</h3></div><SectionDownload section={section} result={result} source={source} /></div>
        {section === "Entrada" && <div className="step-view entry-step-view">
          <p className="view-description">Escribe una expresión aritmética con números enteros y los operadores +, -, * o /.</p>
          <textarea className="step-entry" value={source} onChange={(event) => setSource(event.target.value)} aria-label="Expresión aritmética" placeholder="Ej. 10 + 25 * 10 - 4" />
          <div className="quick-examples">{examples.map(([label, value]) => <button key={label} onClick={() => setSource(value)}>{label}: {value}</button>)}</div>
          <div className="input-actions"><button className="compile-button" onClick={compile} disabled={loading}>{loading ? "Compilando..." : "Compilar expresión  →"}</button><label className="switch-label"><input type="checkbox" checked={zeroBased} onChange={(e) => setZeroBased(e.target.checked)} /><span className="switch" /> Posiciones desde {zeroBased ? "0" : "1"}</label></div>
          {hasErrors && <div className="error-box">{result.errores.map((error) => <p key={error}>{error}</p>)}
            {result.explicacion_error && <p className="error-ai"><b>Explicación IA:</b> {result.explicacion_error}</p>}
          </div>}
        </div>}
        {section === "Tokens" && <><p className="view-description">Cada token representa una unidad reconocida por el analizador léxico.</p><Table title="Tokens identificados" headers={["N.º", "Tipo", "Valor", "Posición"]} rows={result.tokens.map((token, index) => [index + 1, token.type, token.value, token.position])} /></>}
        {section === "AST" && <><p className="view-description">Arrastra las bolitas para ordenar el árbol. Los operadores lilas son nodos internos y los números crema son hojas.</p><div className="ast-stage large-ast">{result.ast ? <AstSvg node={result.ast} activeToken={activeToken} /> : <div className="empty-ast"><p>Compila una expresión para visualizar el AST.</p></div>}</div><pre className="ast-text">{result.ast_text || "No hay AST generado."}</pre></>}
        {section === "Semántica" && <div className="semantic-grid"><Table title="Tabla semántica" headers={["Símbolo", "Dirección"]} rows={result.simbolos.map((item) => [item.symbol, <code>{item.address}</code>])} /><div className="panel semantic-explanation"><div className="panel-heading"><div><span className="kicker">ANÁLISIS SEMÁNTICO</span><h3>Cómo se construyó la tabla</h3></div><span className="ai-badge">✦ SEMÁNTICA</span></div><div className="formula-banner"><span>FÓRMULA</span><code>{source || "—"}</code></div><pre className="semantic-process">{semanticExplanation || "Compila una expresión para explicar los símbolos únicos."}</pre></div></div>}
        {section === "Construcción" && <><p className="view-description">El proceso reduce primero multiplicaciones y divisiones, y después suma y resta de izquierda a derecha.</p><div className="formula-banner"><span>FÓRMULA</span><code>{source || "—"}</code></div><pre className="typed-process">{typedProcess || "Compila una expresión para ver la construcción paso a paso."}</pre></>}
        {section === "Tipos" && <><p className="view-description">La tabla de tipos clasifica cada símbolo único identificado por el análisis semántico.</p><Table title="Tabla de tipos" headers={["Símbolo", "Tipo"]} rows={result.tipos.map((item) => [item.symbol, <span className="type-pill">{item.type}</span>])} /></>}
        {section === "Código máquina" && <><p className="view-description">La traducción usa una máquina de pila y recorrido postorden sobre el AST.</p><div className="machine-grid"><div className="panel machine-panel"><div className="panel-heading"><div><span className="kicker">CÓDIGO MÁQUINA</span><h3>Instrucciones</h3></div><span className="machine-badge">STACK VM</span></div><div className="machine-code">{result.codigo_maquina?.length ? result.codigo_maquina.map((instruction, index) => <div className="machine-line" key={`${instruction}-${index}`}><span>{String(index + 1).padStart(2, "0")}</span><code>{instruction}</code><i>{instruction.startsWith("PUSH") ? "cargar" : instruction === "STORE R0" ? "guardar" : "operar"}</i></div>) : <span className="muted">Las instrucciones aparecerán después de compilar.</span>}</div></div><div className="panel machine-explanation"><div className="panel-heading"><div><span className="kicker">CONSTRUCCIÓN GUIADA</span><h3>Cómo se arma</h3></div><span className="ai-badge">✦ POSTORDEN</span></div><pre className="machine-process">{machineExplanation || "Compila una expresión para explicar el código máquina."}</pre></div></div></>}
        {section === "Resultado" && <div className="result-card step-result"><span className="kicker">08 / RESULTADO FINAL</span><h3>Valor obtenido</h3><strong>{result.resultado ?? "—"}</strong><p>{result.resultado !== null ? "El AST fue evaluado correctamente." : "Compila una expresión válida para obtener el resultado."}</p></div>}
        {section === "Tablas" && <div className="tables-grid section-tables"><Table title="Tabla de símbolos" headers={["Símbolo", "Dirección"]} rows={result.simbolos.map((item) => [item.symbol, <code>{item.address}</code>])} /><Table title="Tabla de tipos" headers={["Símbolo", "Tipo"]} rows={result.tipos.map((item) => [item.symbol, <span className="type-pill">{item.type}</span>])} /></div>}
        {section === "Errores" && <div className="error-view">{result.errores.length ? <>
          {result.errores.map((error) => <div className="error-box" key={error}>{error}</div>)}
          <div className="panel ai-error-explanation"><div className="panel-heading"><div><span className="kicker">ANÁLISIS IA DEL ERROR</span><h3>Por qué ocurrió el error</h3></div><span className="ai-badge">✦ GEMINI</span></div><pre className="semantic-process">{result.explicacion_error || "La IA está preparando una explicación del error..."}</pre></div>
        </> : <div className="success-box">No hay errores. La expresión es válida.</div>}</div>}
        {section === "Teoría" && <div className="theory-view"><article><h4>1. Análisis léxico</h4><p>Lee la fórmula, ignora espacios y reconoce números y operadores válidos. Los caracteres desconocidos se reportan con su posición.</p></article><article><h4>2. Análisis sintáctico</h4><p>El parser de descenso recursivo aplica precedencia: primero multiplicación/división y luego suma/resta. Las operaciones iguales se agrupan de izquierda a derecha.</p></article><article><h4>3. Semántica y código máquina</h4><p>Los números únicos reciben direcciones simuladas y el AST se traduce a instrucciones PUSH, ADD, SUB, MUL, DIV y STORE R0.</p></article></div>}
      </section>}
      {section === "Simulador" && <>
      <section id="entrada-step" className="panel input-panel"><div className="panel-heading"><div><span className="kicker">01 / ENTRADA</span><h3>Escribe tu expresión</h3></div><span className="live-badge"><span /> EN VIVO</span></div>
          <textarea value={source} onChange={(event) => setSource(event.target.value)} aria-label="Expresión aritmética" placeholder="Ej. 10 + 25 * 10 - 4" />
          <div className="quick-examples"><span>Ejemplos rápidos</span>{examples.map(([label, value]) => <button key={label} onClick={() => setSource(value)}>{label}</button>)}</div>
          <div className="input-actions"><button className="compile-button" onClick={compile} disabled={loading}>{loading ? "Compilando..." : "Compilar expresión  →"}</button><label className="switch-label"><input type="checkbox" checked={zeroBased} onChange={(e) => setZeroBased(e.target.checked)} /><span className="switch" /> Posiciones desde {zeroBased ? "0" : "1"}</label></div>
          {hasErrors && <div className="error-box"><strong>! Se encontraron {result.errores.length} error{result.errores.length > 1 ? "es" : ""}</strong>{result.errores.map((error) => <p key={error}>{error}</p>)}
            {result.explicacion_error && <p className="error-ai"><b>Explicación IA:</b> {result.explicacion_error}</p>}
          </div>}
      </section>
      <section id="tokens-step" className="section-block"><div className="section-title"><span className="kicker">02 / LÉXICO</span><h3>Tokens identificados</h3></div><div className="token-list">{result.tokens.length ? result.tokens.map((token, index) => <button className={`token-chip ${token.type === "NÚMERO" ? "number-chip" : "operator-chip"}`} key={`${token.position}-${index}`} onMouseEnter={() => setActiveToken(token.value)} onMouseLeave={() => setActiveToken(null)}><small>{String(index + 1).padStart(2, "0")}</small>{token.value}<em>{token.type}</em></button>) : <span className="muted">Los tokens aparecerán después de compilar.</span>}</div></section>
      <section id="ast-step" className="panel ast-panel"><div className="panel-heading"><div><span className="kicker">03 / SINTAXIS</span><h3>Árbol de sintaxis abstracta <span className="mini-tag">SVG</span></h3></div><span className="ast-legend"><i className="cream-dot" /> número <i className="lilac-dot" /> operador</span></div>
        <div className="ast-stage">{result.ast ? <AstSvg node={result.ast} activeToken={activeToken} /> : <div className="empty-ast"><div>⌁</div><p>El AST aparecerá aquí</p><small>Compila una expresión para visualizar su estructura.</small></div>}</div>
        <pre className="ast-text">{result.ast_text || "└── esperando entrada..."}</pre>
      </section>
      <section id="semantic-step" className="semantic-grid">
        <Table title="04 / Tabla semántica" headers={["Símbolo", "Dirección"]} rows={result.simbolos.map((item) => [item.symbol, <code>{item.address}</code>])} />
        <div className="panel semantic-explanation"><div className="panel-heading"><div><span className="kicker">04 / ANÁLISIS SEMÁNTICO</span><h3>Cómo se construyó la tabla</h3></div><span className="ai-badge">✦ SEMÁNTICA</span></div>
          <div className="formula-banner"><span>FÓRMULA</span><code>{source || "—"}</code></div>
          <pre className="semantic-process">{semanticExplanation || "Compila una expresión para explicar cómo se crean los símbolos únicos y sus direcciones."}</pre>
        </div>
      </section>
      <section id="construction-step" className="panel process-panel"><div className="panel-heading"><div><span className="kicker">05 / EJECUCIÓN GUIADA</span><h3>Cómo se construye el AST</h3></div><span className="ai-badge">✦ EXPLICACIÓN IA</span></div>
          <div className="formula-banner"><span>FÓRMULA</span><code>{source || "—"}</code></div>
          <pre className="typed-process">{typedProcess || "Compila una expresión y te explicaré el proceso paso a paso..."}</pre>
      </section>
      <section id="types-step" className="types-grid"><Table title="06 / Tabla de tipos" headers={["Símbolo", "Tipo"]} rows={result.tipos.map((item) => [item.symbol, <span className="type-pill">{item.type}</span>])} /></section>
      <section id="machine-step" className="machine-grid">
        <div className="panel machine-panel"><div className="panel-heading"><div><span className="kicker">07 / GENERACIÓN</span><h3>Código máquina</h3></div><span className="machine-badge">STACK VM</span></div>
          <div className="machine-code">{result.codigo_maquina?.length ? result.codigo_maquina.map((instruction, index) => <div className="machine-line" key={`${instruction}-${index}`}><span>{String(index + 1).padStart(2, "0")}</span><code>{instruction}</code><i>{instruction.startsWith("PUSH") ? "cargar" : instruction === "STORE R0" ? "guardar" : "operar"}</i></div>) : <span className="muted">Las instrucciones aparecerán después de compilar.</span>}</div>
        </div>
        <div className="panel machine-explanation"><div className="panel-heading"><div><span className="kicker">07 / CONSTRUCCIÓN GUIADA</span><h3>Cómo se arma el código máquina</h3></div><span className="ai-badge">✦ RECORRIDO POSTORDEN</span></div>
          <pre className="machine-process">{machineExplanation || "Compila una expresión para explicar el recorrido del AST y la construcción de cada instrucción."}</pre>
        </div>
      </section>
      <section id="result-step" className="result-card"><span className="kicker">08 / RESULTADO</span><h3>Resultado final</h3><strong>{result.resultado ?? "—"}</strong><p>{result.resultado !== null ? "AST evaluado correctamente" : "Sin resultado disponible"}</p></section>
      </>}
      <footer>ArithLab+ · Simulador educativo de teoría de compiladores <span>Lexer · Parser · Semántica</span></footer>
    </main>
  </div>;
}
