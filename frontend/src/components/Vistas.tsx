import { useEffect, useState } from "react";
import { enviarPost, leer, type Conversacion, type Rutina, type Skill } from "../lib/api";
import type { Baki } from "../useBaki";
import { IcoLapiz, IcoMas } from "./Iconos";
import type { Vista } from "./Marco";

type Ir = (v: Vista) => void;

const fechaCorta = (ms?: number | null) =>
  ms ? new Date(ms).toLocaleString("es-ES", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" }) : "";

function useDatos<T>(ruta: string, dependencias: unknown[] = []) {
  const [datos, setDatos] = useState<T | null>(null);
  useEffect(() => {
    let vivo = true;
    leer<T>(ruta).then((d) => vivo && setDatos(d));
    return () => {
      vivo = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ruta, ...dependencias]);
  return datos;
}

const INTEGRACIONES = [
  { clave: "google", nombre: "Gmail y Google Calendar", hace: "Leer, buscar y enviar correos; ver y crear eventos.", comando: 'python -m app.secrets_cli autorizar-google "ruta\\client_secret.json"' },
  { clave: "crm_ghl", nombre: "CRM GoHighLevel", hace: "Contactos, oportunidades, SMS/email/Instagram/WhatsApp y redes sociales.", comando: "python -m app.secrets_cli conectar-ghl" },
  { clave: "n8n", nombre: "n8n", hace: "Crear, probar y activar automatizaciones y agentes.", comando: "python -m app.secrets_cli conectar-n8n" },
];

// ------------------------------------------------------------------ Dashboard

export function Dashboard({ baki, ir }: { baki: Baki; ir: Ir }) {
  const conv = useDatos<{ lista: Conversacion[] }>("/conversaciones", [baki.conversacionId]);
  const tareasSrv = useDatos<{ rutinas: Rutina[] }>("/tareas", [baki.pendientes.length]);
  const integ = baki.estado?.integraciones ?? {};
  const conectadas = Object.values(integ).filter(Boolean).length;
  const ordenRapida = (texto: string) => {
    baki.setBorrador(texto);
    ir("chat");
  };

  return (
    <section className="vista panel">
      <h2>Dashboard</h2>
      <div className="rejilla-dash">
        <div className="tarjeta nucleo-tarjeta">
          <div className={`orbe ${baki.trabajando ? "trabajando" : baki.hablando ? "hablando" : baki.microActivo ? "escuchando" : ""}`}>
            <span>BAKI</span><small>AI CORE</small>
          </div>
          <ul className="lista-estado">
            <li><span className={`punto ${baki.conectado ? "ok" : "mal"}`} /> Núcleo {baki.conectado ? "activo" : "desconectado"}</li>
            <li><span className="punto ok" /> Modelo {baki.estado?.modelo.replace("claude-", "") ?? "—"}</li>
            <li><span className={`punto ${baki.estado?.voz !== "navegador" ? "ok" : "medio"}`} /> Voz {baki.estado?.voz ?? "—"}</li>
            <li><span className={`punto ${conectadas ? "ok" : "medio"}`} /> {conectadas}/{Object.keys(integ).length} integraciones</li>
          </ul>
        </div>

        <div className="tarjeta">
          <span className="titulo-panel">ÓRDENES RÁPIDAS</span>
          <div className="ordenes">
            <button onClick={() => { baki.nuevaConversacion(); ir("chat"); }}><IcoMas tam={15} /> Nueva conversación</button>
            <button onClick={() => ordenRapida("Nuevo proyecto: ")}>Nuevo proyecto</button>
            <button onClick={() => ordenRapida("Créame en n8n una automatización que ")}>Automatización n8n</button>
            <button onClick={() => ordenRapida("Diseña un agente de IA para la empresa ")}>Agente para una empresa</button>
            <button onClick={() => ordenRapida("Resume mis correos sin leer y mi agenda de hoy.")}>Resumen del día</button>
          </div>
        </div>

        <div className="tarjeta">
          <span className="titulo-panel">ACTIVIDAD</span>
          <div className="cifras">
            <div><b>{baki.pendientes.length}</b><small>pendientes de aprobar</small></div>
            <div><b>{baki.tareas.filter((t) => t.estado === "en_curso").length}</b><small>en curso</small></div>
            <div><b>{tareasSrv?.rutinas.length ?? "—"}</b><small>rutinas programadas</small></div>
            <div><b>{baki.uso?.hoy.turnos ?? "—"}</b><small>peticiones hoy</small></div>
          </div>
          <button className="enlace" onClick={() => ir("tareas")}>Ver tareas →</button>
        </div>

        <div className="tarjeta">
          <span className="titulo-panel">CONVERSACIONES RECIENTES</span>
          <ul className="lista-simple">
            {(conv?.lista ?? []).slice(0, 5).map((c) => (
              <li key={c.id}>
                <button onClick={() => { void baki.abrirConversacion(c.id); ir("chat"); }}>
                  <span>{c.titulo}</span><small>{fechaCorta(c.actualizada)}</small>
                </button>
              </li>
            ))}
          </ul>
          <button className="enlace" onClick={() => ir("conversaciones")}>Ver todas →</button>
        </div>
      </div>
    </section>
  );
}

// ------------------------------------------------------------------ Conversaciones

function FilaConversacion({ c, actual, abrir, renombrada }: {
  c: Conversacion; actual: boolean; abrir: () => void; renombrada: () => void;
}) {
  const [editando, setEditando] = useState(false);
  const [titulo, setTitulo] = useState(c.titulo);
  const [error, setError] = useState("");

  const guardar = async () => {
    const limpio = titulo.trim();
    if (!limpio || limpio === c.titulo) {
      setEditando(false);
      setTitulo(c.titulo);
      return;
    }
    const r = await enviarPost<{ ok: boolean }>(`/conversaciones/${c.id}/renombrar`, { titulo: limpio });
    if (r?.ok) {
      setEditando(false);
      setError("");
      renombrada();
    } else {
      setError("No se pudo renombrar.");
    }
  };

  return (
    <li className={actual ? "actual" : ""}>
      {editando ? (
        <div className="fila-editando">
          <input autoFocus value={titulo} maxLength={90} onChange={(e) => setTitulo(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") void guardar();
              if (e.key === "Escape") { setEditando(false); setTitulo(c.titulo); }
            }} />
          <button className="aprobar" onClick={() => void guardar()}>Guardar</button>
          <button onClick={() => { setEditando(false); setTitulo(c.titulo); }}>Cancelar</button>
          {error && <small className="error-texto">{error}</small>}
        </div>
      ) : (
        <div className="fila-conversacion">
          <button className="abrir" onClick={abrir}>
            <span>{c.titulo}</span>
            <small>{actual ? "Actual · " : ""}{fechaCorta(c.actualizada)}</small>
          </button>
          <button className="boton-icono" title="Renombrar" onClick={() => { setTitulo(c.titulo); setEditando(true); }}>
            <IcoLapiz tam={15} />
          </button>
        </div>
      )}
    </li>
  );
}

export function Conversaciones({ baki, ir }: { baki: Baki; ir: Ir }) {
  const [version, setVersion] = useState(0);
  const datos = useDatos<{ actual: string | null; lista: Conversacion[] }>("/conversaciones", [baki.conversacionId, version]);
  const [filtro, setFiltro] = useState("");
  const lista = (datos?.lista ?? []).filter((c) => c.titulo.toLowerCase().includes(filtro.toLowerCase()));
  return (
    <section className="vista panel">
      <div className="vista-cabecera">
        <h2>Conversaciones</h2>
        <input className="buscador" placeholder="Buscar…" value={filtro} onChange={(e) => setFiltro(e.target.value)} />
        <button className="primario" onClick={() => { baki.nuevaConversacion(); ir("chat"); }}><IcoMas tam={15} /> Nueva</button>
      </div>
      <ul className="lista-conversaciones">
        {datos === null && <li className="tenue">Cargando…</li>}
        {datos && lista.length === 0 && <li className="tenue">No hay conversaciones.</li>}
        {lista.map((c) => (
          <FilaConversacion key={`${c.id}-${c.titulo}`} c={c} actual={c.id === baki.conversacionId}
            abrir={() => { void baki.abrirConversacion(c.id); ir("chat"); }}
            renombrada={() => setVersion((v) => v + 1)} />
        ))}
      </ul>
      <p className="tenue pista-renombrar">Para renombrar una conversación, pulsa el lápiz ✎ a su derecha.</p>
    </section>
  );
}

// ------------------------------------------------------------------ Tareas

export function Tareas({ baki }: { baki: Baki }) {
  const datos = useDatos<{ rutinas: Rutina[] }>("/tareas", [baki.pendientes.length, baki.trabajando]);
  const enCurso = baki.tareas.filter((t) => t.estado === "en_curso");
  return (
    <section className="vista panel">
      <h2>Tareas</h2>
      <div className="columnas-tareas">
        <div className="tarjeta">
          <span className="titulo-panel">EN EJECUCIÓN</span>
          {!baki.trabajando && enCurso.length === 0 && <p className="tenue">BAKI no está trabajando en nada ahora.</p>}
          {baki.trabajando && enCurso.length === 0 && <p>BAKI está pensando…</p>}
          <ul className="lista-tareas">
            {enCurso.map((t) => <li key={t.id}><b>{t.nombre}</b><small>{t.resumen}</small></li>)}
          </ul>
          {baki.trabajando && <button className="detener" onClick={baki.detenerTodo}>Detener</button>}
        </div>

        <div className="tarjeta">
          <span className="titulo-panel">PENDIENTES DE TU APROBACIÓN</span>
          {baki.pendientes.length === 0 && <p className="tenue">Nada pendiente.</p>}
          <ul className="lista-tareas">
            {baki.pendientes.map((p) => (
              <li key={p.id}>
                <b>{p.herramienta}</b>
                <small className="pre">{p.resumen}</small>
                <div className="botones">
                  <button className="aprobar" onClick={() => baki.responder(p.id, true)}>Aprobar</button>
                  <button className="rechazar" onClick={() => baki.responder(p.id, false)}>Rechazar</button>
                </div>
              </li>
            ))}
          </ul>
        </div>

        <div className="tarjeta">
          <span className="titulo-panel">RUTINAS PROGRAMADAS</span>
          {datos?.rutinas.length === 0 && <p className="tenue">No hay rutinas. Pídelas: «cada laborable a las 8:30, resume mi correo».</p>}
          <ul className="lista-tareas">
            {(datos?.rutinas ?? []).map((r) => (
              <li key={r.id}>
                <b>{r.nombre} · {r.hora}</b>
                <small>{r.dias.join(", ")} — {r.instruccion}</small>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </section>
  );
}

// ------------------------------------------------------------------ Skills

export function Skills({ baki, ir, skills }: { baki: Baki; ir: Ir; skills: Skill[] | null }) {
  const usar = (s: Skill) => {
    baki.setBorrador(`Usa la skill ${s.nombre === "grill-me" ? "grilling" : s.nombre}: `);
    ir("chat");
  };
  return (
    <section className="vista panel">
      <div className="vista-cabecera">
        <h2>Skills</h2>
        <span className="tenue">Se activan solas cuando encajan con lo que pides. Guía completa: GUIA_SKILLS.md</span>
      </div>
      <div className="rejilla-skills">
        {(skills ?? []).map((s) => (
          <div key={s.nombre} className="tarjeta skill">
            <div className="skill-cabecera">
              <b>{s.nombre}</b>
              <em className={s.automatica ? "auto" : "manual"}>{s.automatica ? "Automática" : "Manual"}</em>
            </div>
            <small className="origen">{s.origen}</small>
            <p>{s.descripcion}</p>
            <button onClick={() => usar(s)}>Usar</button>
          </div>
        ))}
      </div>
    </section>
  );
}

// ------------------------------------------------------------------ Conectores

export function Integraciones({ baki }: { baki: Baki }) {
  const integ = baki.estado?.integraciones ?? {};
  const [copiado, setCopiado] = useState<string | null>(null);
  const copiar = async (clave: string, texto: string) => {
    try {
      await navigator.clipboard.writeText(texto);
      setCopiado(clave);
      window.setTimeout(() => setCopiado(null), 1500);
    } catch {
      /* sin permiso de portapapeles */
    }
  };
  return (
    <section className="vista panel">
      <div className="vista-cabecera">
        <h2>Conectores e integraciones</h2>
        <span className="tenue">Los comandos se ejecutan en PowerShell desde la carpeta BAKI\backend. Detalle: docs\GUIA_CONEXIONES.md</span>
      </div>
      <div className="rejilla-skills">
        {INTEGRACIONES.map((i) => (
          <div key={i.clave} className="tarjeta skill">
            <div className="skill-cabecera">
              <b>{i.nombre}</b>
              <em className={integ[i.clave] ? "auto" : "manual"}>{integ[i.clave] ? "Conectado" : "Sin conectar"}</em>
            </div>
            <p>{i.hace}</p>
            {!integ[i.clave] && (
              <>
                <code className="comando">..\.venv\Scripts\{i.comando}</code>
                <button onClick={() => copiar(i.clave, `..\\.venv\\Scripts\\${i.comando}`)}>{copiado === i.clave ? "¡Copiado!" : "Copiar comando"}</button>
              </>
            )}
          </div>
        ))}
        <div className="tarjeta skill">
          <div className="skill-cabecera"><b>Archivos, web y PowerShell</b><em className="auto">Siempre activo</em></div>
          <p>Leer y organizar archivos, buscar en internet, extraer datos de webs y ejecutar comandos (con tu aprobación).</p>
        </div>
        <div className="tarjeta skill">
          <div className="skill-cabecera"><b>Voz</b><em className={baki.estado?.voz !== "navegador" ? "auto" : "manual"}>{baki.estado?.voz ?? "—"}</em></div>
          <p>Voz del navegador (Edge natural) por defecto. Para ElevenLabs: <code>..\.venv\Scripts\python -m app.secrets_cli conectar-elevenlabs</code></p>
        </div>
      </div>
    </section>
  );
}
