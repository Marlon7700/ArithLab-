// Punto de entrada del frontend. Monta App en #root.
// Si se elimina createRoot, la página queda en blanco: ningún componente se dibuja.
import React from "react";
import { createRoot } from "react-dom/client";
import "bootstrap/dist/css/bootstrap.min.css";
import "./styles.css";
import App from "./App";

createRoot(document.getElementById("root")).render(
  <React.StrictMode><App /></React.StrictMode>
);
