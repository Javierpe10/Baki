import { useEffect, useState } from "react";
import "./App.css";
import { Chat } from "./components/Chat";
import { BarraVoz, Cabecera, Lateral, PanelDerecho, type Vista } from "./components/Marco";
import { Conversaciones, Dashboard, Integraciones, Skills, Tareas } from "./components/Vistas";
import { leer, type Skill } from "./lib/api";
import { useBaki } from "./useBaki";

const VISTA_GUARDADA = "baki:vista";

function vistaInicial(): Vista {
  try {
    const v = localStorage.getItem(VISTA_GUARDADA);
    if (v && ["chat", "dashboard", "conversaciones", "tareas", "skills", "integraciones"].includes(v)) return v as Vista;
  } catch {
    /* almacenamiento no disponible */
  }
  return "chat";
}

function App() {
  const baki = useBaki();
  const [vista, setVista] = useState<Vista>(vistaInicial);
  const [skills, setSkills] = useState<Skill[] | null>(null);

  useEffect(() => {
    try {
      localStorage.setItem(VISTA_GUARDADA, vista);
    } catch {
      /* sin almacenamiento */
    }
  }, [vista]);

  useEffect(() => {
    if (baki.conectado) leer<Skill[]>("/skills").then(setSkills);
  }, [baki.conectado]);

  // Aviso visible si llega una aprobación mientras miras otra vista.
  const avisoAprobacion = baki.pendientes.length > 0 && vista !== "chat" && vista !== "tareas";

  return (
    <main className="app-baki">
      <Cabecera baki={baki} />
      <div className="cuerpo">
        <Lateral baki={baki} vista={vista} setVista={setVista} numSkills={skills?.length ?? 0} />
        <div className="centro">
          {avisoAprobacion && (
            <button className="aviso-aprobacion" onClick={() => setVista("chat")}>
              ⚠ BAKI espera tu aprobación ({baki.pendientes.length}). Ver en el chat →
            </button>
          )}
          {vista === "chat" && <Chat baki={baki} />}
          {vista === "dashboard" && <Dashboard baki={baki} ir={setVista} />}
          {vista === "conversaciones" && <Conversaciones baki={baki} ir={setVista} />}
          {vista === "tareas" && <Tareas baki={baki} />}
          {vista === "skills" && <Skills baki={baki} ir={setVista} skills={skills} />}
          {vista === "integraciones" && <Integraciones baki={baki} />}
        </div>
        <PanelDerecho baki={baki} />
      </div>
      <BarraVoz baki={baki} />
    </main>
  );
}

export default App;
