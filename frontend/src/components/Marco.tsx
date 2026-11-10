import { useEffect, useState, type ReactNode } from "react";
import type { Baki } from "../useBaki";
import {
  IcoAltavoz, IcoChat, IcoConector, IcoError, IcoHistorial, IcoMando, IcoMicro, IcoMudo, IcoOk, IcoParar,
  IcoReloj, IcoSkills, IcoTareas,
} from "./Iconos";

export type Vista = "chat" | "dashboard" | "conversaciones" | "tareas" | "skills" | "integraciones";

// ------------------------------------------------------------------ cabecera

export function Cabecera({ baki }: { baki: Baki }) {
  const [ahora, setAhora] = useState(() => new Date());
  useEffect(() => {
    const t = window.setInterval(() => setAhora(new Date()), 1000);
    return () => window.clearInterval(t);
  }, []);
  const fecha = ahora.toLocaleDateString("es-ES", { weekday: "long", day: "numeric", month: "long", year: "numeric" });
  const horaTxt = ahora.toLocaleTimeString("es-ES", { hour: "2-digit", minute: "2-digit", second: "2-digit" });

  return (
    <header className="cabecera">
      <div className="marca">
        <div className="logo-anillo" />
        <div>
          <strong>BAKI</strong>
          <small>COMMAND CENTER</small>
        </div>
      </div>
      <div className={`estado-sistema ${baki.conectado ? "ok" : "mal"}`}>
        <span className="punto" />
        SISTEMA <b>{baki.conectado ? "EN LÍNEA" : "SIN CONEXIÓN"}</b>
      </div>
      <div className="reloj">
        <small>{fecha.charAt(0).toUpperCase() + fecha.slice(1)}</small>
        <strong>{horaTxt}</strong>
      </div>
      <div className="cabecera-derecha">
        <span className="chip">{baki.estado?.modelo.replace("claude-", "").replace(/-/g, " ") ?? "—"}</span>
        <span className="chip operador">{baki.trabajando ? "Trabajando…" : baki.hablando ? "Hablando" : baki.microActivo ? "Escuchando" : "En espera"}</span>
      </div>
    </header>
  );
}

// ------------------------------------------------------------------ menú lateral

export function Lateral({ baki, vista, setVista, numSkills }: {
  baki: Baki; vista: Vista; setVista: (v: Vista) => void; numSkills: number;
}) {
  const enCurso = baki.tareas.filter((t) => t.estado === "en_curso").length;
  const items: { id: Vista; nombre: string; icono: ReactNode; insignia?: number }[] = [
    { id: "chat", nombre: "Centro de mando", icono: <IcoChat /> },
    { id: "dashboard", nombre: "Dashboard", icono: <IcoMando /> },
    { id: "conversaciones", nombre: "Conversaciones", icono: <IcoHistorial /> },
    { id: "tareas", nombre: "Tareas", icono: <IcoTareas />, insignia: baki.pendientes.length + enCurso },
    { id: "skills", nombre: "Skills", icono: <IcoSkills />, insignia: numSkills },
    { id: "integraciones", nombre: "Conectores", icono: <IcoConector /> },
  ];
  const estadoVoz = baki.hablando ? "Hablando" : baki.microActivo ? (baki.manosLibres ? "Manos libres" : "Escuchando…") : "En espera";

  return (
    <nav className="lateral panel">
      <ul>
        {items.map((it) => (
          <li key={it.id}>
            <button className={vista === it.id ? "activo" : ""} onClick={() => setVista(it.id)}>
              {it.icono}
              <span>{it.nombre}</span>
              {Boolean(it.insignia) && <em>{it.insignia}</em>}
            </button>
          </li>
        ))}
      </ul>
      <div className="tarjeta-voz">
        <span className="titulo-panel">ESTADO DE VOZ</span>
        <div className={`onda ${baki.microActivo || baki.hablando ? "viva" : ""}`}>
          {Array.from({ length: 18 }, (_, i) => <i key={i} style={{ animationDelay: `${(i % 6) * 0.09}s` }} />)}
        </div>
        <p>{estadoVoz}</p>
        <small>{baki.estado ? `Voz: ${baki.estado.voz}` : ""}</small>
      </div>
    </nav>
  );
}

// ------------------------------------------------------------------ panel derecho

function Anillo({ valor, etiqueta, detalle }: { valor: number | null; etiqueta: string; detalle: string }) {
  const r = 30;
  const c = 2 * Math.PI * r;
  const v = valor === null ? 0 : Math.max(0, Math.min(100, valor));
  const color = v >= 85 ? "var(--rojo)" : v >= 65 ? "var(--ambar)" : "var(--cian)";
  return (
    <div className="anillo">
      <svg width="78" height="78" viewBox="0 0 78 78">
        <circle cx="39" cy="39" r={r} className="anillo-fondo" />
        <circle cx="39" cy="39" r={r} className="anillo-valor" stroke={color}
          strokeDasharray={c} strokeDashoffset={c - (c * v) / 100} transform="rotate(-90 39 39)" />
        <text x="39" y="44" textAnchor="middle">{valor === null ? "—" : `${Math.round(v)}%`}</text>
      </svg>
      <b>{etiqueta}</b>
      <small>{detalle}</small>
    </div>
  );
}

const miles = (n?: number | null) => (n === undefined || n === null ? "—" : n >= 1_000_000 ? `${(n / 1_000_000).toFixed(1)} M` : n >= 1000 ? `${Math.round(n / 1000)} k` : String(n));

export function PanelDerecho({ baki }: { baki: Baki }) {
  const u = baki.uso;
  const limitePct = u?.limite?.uso !== undefined && u?.limite?.uso !== null ? (u.limite.uso as number) * 100 : null;
  const reinicio = u?.limite?.reinicia ? new Date(u.limite.reinicia * 1000).toLocaleTimeString("es-ES", { hour: "2-digit", minute: "2-digit" }) : null;
  const tareas = [...baki.tareas].reverse();

  return (
    <aside className="derecho">
      <section className="panel uso">
        <span className="titulo-panel">USO DE CLAUDE</span>
        <div className="anillos">
          <Anillo valor={u?.contexto?.porcentaje ?? null} etiqueta="Contexto"
            detalle={u?.contexto ? `${miles(u.contexto.tokens)} / ${miles(u.contexto.maximo)}` : "tras la 1ª respuesta"} />
          <Anillo valor={limitePct} etiqueta="Límite del plan"
            detalle={limitePct !== null ? (reinicio ? `se renueva ${reinicio}` : "ventana actual") : "Claude aún no lo ha informado"} />
        </div>
        <div className="uso-hoy">
          <div><b>{u?.hoy.turnos ?? "—"}</b><small>peticiones hoy</small></div>
          <div><b>{miles(u?.hoy.tokens_procesados)}</b><small>tokens procesados</small></div>
          <div><b>{miles(u?.hoy.tokens_generados)}</b><small>tokens escritos</small></div>
        </div>
        {u?.limite?.estado && u.limite.estado !== "allowed" && (
          <p className="aviso-limite">⚠ Cerca del límite de tu plan.</p>
        )}
      </section>

      <section className="panel tareas-conversacion">
        <span className="titulo-panel">TAREAS DE ESTA CONVERSACIÓN <em>{baki.tareas.length}</em></span>
        <ul>
          {tareas.length === 0 && <li className="tenue">Aún no hay tareas en esta conversación.</li>}
          {tareas.map((t) => (
            <li key={t.id} className={t.estado} title={t.resumen}>
              <span className="icono-estado">
                {t.estado === "en_curso" ? <IcoReloj tam={15} /> : t.estado === "error" ? <IcoError tam={15} /> : <IcoOk tam={15} />}
              </span>
              <div>
                <b>{t.nombre}</b>
                <small>{t.resumen}</small>
              </div>
              {t.nivel === 2 && <em className="nivel2">APR</em>}
            </li>
          ))}
        </ul>
      </section>
    </aside>
  );
}

// ------------------------------------------------------------------ barra inferior

export function BarraVoz({ baki }: { baki: Baki }) {
  const hablarActivo = baki.microActivo && !baki.manosLibres;
  return (
    <footer className="barra-voz">
      <button className={`manos-libres ${baki.manosLibres ? "activo" : ""}`} onClick={baki.alternarManosLibres}
        title="Escucha continua: di «Baki» y tu orden">
        <span className="punto" /> Manos libres {baki.manosLibres ? "ON" : "OFF"}
      </button>

      <button className={`hablar ${hablarActivo || baki.manosLibres ? "escuchando" : ""}`} onClick={baki.pulsarMicro}
        disabled={baki.manosLibres}>
        <span className="onda pequena viva">{Array.from({ length: 7 }, (_, i) => <i key={i} style={{ animationDelay: `${i * 0.08}s` }} />)}</span>
        <span className="hablar-texto">
          <strong>HABLAR CON BAKI</strong>
          <small>{baki.manosLibres ? "Manos libres activo · di «Baki, …»" : hablarActivo ? "Te escucho…" : "Pulsa y habla"}</small>
        </span>
        <IcoMicro tam={20} />
      </button>

      <div className="barra-derecha">
        <button className="secundario" onClick={() => baki.setVozActiva(!baki.vozActiva)}
          title="Respuesta hablada (solo cuando la orden es por voz)">
          {baki.vozActiva ? <IcoAltavoz /> : <IcoMudo />} {baki.vozActiva ? "Voz" : "Mudo"}
        </button>
        {(baki.trabajando || baki.hablando) && (
          <button className="detener" onClick={baki.detenerTodo}><IcoParar /> Detener</button>
        )}
      </div>
    </footer>
  );
}
