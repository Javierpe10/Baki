import { useEffect, useLayoutEffect, useRef } from "react";
import type { Baki } from "../useBaki";
import { IcoEnviar, IcoMicro, IcoParar } from "./Iconos";
import { Markdown } from "./Markdown";

const MODELOS = [
  { id: "claude-sonnet-5-5", nombre: "Sonnet 5.5" },
  { id: "claude-opus-5-5", nombre: "Opus 5.5" },
  { id: "claude-haiku-5-5", nombre: "Haiku 5.5" },
];

const EJEMPLOS = [
  "¿Qué tengo hoy en la agenda?",
  "Resume mis correos sin leer",
  "Nuevo proyecto: agente de WhatsApp para clínicas dentales. Grill me",
  "Créame en n8n un flujo que avise por email cuando entre un lead nuevo",
];

/** Continúa listas al pulsar Mayús+Intro: «- », «* », «• » o «1. ». Una viñeta vacía cierra la lista. */
function saltoDeLinea(valor: string, inicio: number, fin: number): { valor: string; cursor: number } {
  const antes = valor.slice(0, inicio);
  const despues = valor.slice(fin);
  const lineaActual = antes.slice(antes.lastIndexOf("\n") + 1);
  const vineta = lineaActual.match(/^(\s*)([-*•])\s+(.*)$/);
  const numero = lineaActual.match(/^(\s*)(\d+)([.)])\s+(.*)$/);
  if ((vineta && !vineta[3]) || (numero && !numero[4])) {
    // Viñeta vacía: se quita y se termina la lista.
    const limpio = antes.slice(0, antes.length - lineaActual.length);
    return { valor: limpio + "\n" + despues, cursor: limpio.length + 1 };
  }
  let prefijo = "";
  if (vineta) prefijo = `${vineta[1]}${vineta[2]} `;
  else if (numero) prefijo = `${numero[1]}${Number(numero[2]) + 1}${numero[3]} `;
  const insertado = "\n" + prefijo;
  return { valor: antes + insertado + despues, cursor: inicio + insertado.length };
}

function Compositor({ baki }: { baki: Baki }) {
  const area = useRef<HTMLTextAreaElement | null>(null);
  const seleccion = useRef<{ inicio: number; fin: number; scroll: number; enfocado: boolean }>({
    inicio: 0, fin: 0, scroll: 0, enfocado: false,
  });
  const cursorPendiente = useRef<number | null>(null);

  // Altura automática (hasta ~10 líneas; luego desplazamiento interno).
  useLayoutEffect(() => {
    const el = area.current;
    if (!el) return;
    el.style.height = "auto";
    // +2 por el borde: sin ello aparece una barra de desplazamiento con una sola línea.
    const alto = el.scrollHeight + 2;
    el.style.height = `${Math.min(alto, 260)}px`;
    el.style.overflowY = alto > 260 ? "auto" : "hidden";
    if (cursorPendiente.current !== null) {
      el.setSelectionRange(cursorPendiente.current, cursorPendiente.current);
      cursorPendiente.current = null;
    }
  }, [baki.borrador]);

  // Al volver a la ventana, el cursor y el desplazamiento quedan donde estaban.
  useEffect(() => {
    const alVolver = () => {
      const el = area.current;
      const s = seleccion.current;
      if (!el || !s.enfocado) return;
      el.focus({ preventScroll: true });
      el.setSelectionRange(s.inicio, s.fin);
      el.scrollTop = s.scroll;
    };
    window.addEventListener("focus", alVolver);
    return () => window.removeEventListener("focus", alVolver);
  }, []);

  const guardarSeleccion = (enfocado: boolean) => {
    const el = area.current;
    if (!el) return;
    seleccion.current = { inicio: el.selectionStart, fin: el.selectionEnd, scroll: el.scrollTop, enfocado };
  };

  const enviar = () => {
    if (baki.enviar(baki.borrador)) {
      baki.setBorrador("");
      seleccion.current = { inicio: 0, fin: 0, scroll: 0, enfocado: true };
    }
  };

  return (
    <div className="compositor">
      {baki.parcial && baki.microActivo && <div className="transcripcion">🎙 {baki.parcial}</div>}
      <textarea
        ref={area}
        rows={1}
        value={baki.borrador}
        placeholder={baki.manosLibres ? "Escuchando… di «Baki» y tu orden, o escribe aquí" : "Escribe una orden para BAKI   (Mayús + Intro para nueva línea)"}
        onChange={(e) => baki.setBorrador(e.target.value)}
        onSelect={() => guardarSeleccion(true)}
        onBlur={() => guardarSeleccion(document.hasFocus() ? false : true)}
        onKeyDown={(e) => {
          if (e.key !== "Enter" || e.nativeEvent.isComposing) return;
          e.preventDefault();
          if (e.shiftKey) {
            const el = e.currentTarget;
            const r = saltoDeLinea(el.value, el.selectionStart, el.selectionEnd);
            cursorPendiente.current = r.cursor;
            baki.setBorrador(r.valor);
          } else {
            enviar();
          }
        }}
      />
      <div className="compositor-pie">
        <select className="selector-modelo" value={baki.estado?.modelo ?? ""} disabled={!baki.estado}
          onChange={(e) => baki.elegirModelo(e.target.value)} title="Modelo de Claude">
          {MODELOS.map((m) => <option key={m.id} value={m.id}>{m.nombre}</option>)}
        </select>
        <span className="pista">Intro envía · Mayús+Intro nueva línea</span>
        <div className="compositor-botones">
          {baki.trabajando && (
            <button className="boton-icono peligro" onClick={baki.detenerTodo} title="Detener"><IcoParar /></button>
          )}
          <button className={`boton-icono ${baki.microActivo && !baki.manosLibres ? "activo" : ""}`}
            onClick={baki.pulsarMicro} disabled={baki.manosLibres} title="Dictar una orden"><IcoMicro /></button>
          <button className="boton-enviar" onClick={enviar} disabled={!baki.borrador.trim()} title="Enviar"><IcoEnviar /></button>
        </div>
      </div>
    </div>
  );
}

export function Chat({ baki }: { baki: Baki }) {
  const fin = useRef<HTMLDivElement | null>(null);
  const contenedor = useRef<HTMLDivElement | null>(null);
  const cuantos = useRef(0);
  // «Pegado al final»: mientras estés abajo, el chat sigue a BAKI mientras escribe.
  // Si subes para leer algo anterior, no te arrastra hacia abajo.
  const pegado = useRef(true);
  useEffect(() => {
    const el = contenedor.current;
    if (!el) return;
    const alDesplazar = () => {
      pegado.current = el.scrollHeight - el.scrollTop - el.clientHeight < 140;
    };
    el.addEventListener("scroll", alDesplazar, { passive: true });
    return () => el.removeEventListener("scroll", alDesplazar);
  }, []);
  useEffect(() => {
    const el = contenedor.current;
    if (!el) return;
    const nuevos = baki.mensajes.length - cuantos.current;
    const ultimo = baki.mensajes[baki.mensajes.length - 1];
    cuantos.current = baki.mensajes.length;
    // Conversación cargada entera, mensaje tuyo o estabas abajo: al final, sin animación
    // (la animación se quedaba por detrás del texto en directo y ocultaba el final).
    if (nuevos > 3 || ultimo?.rol === "usuario" || pegado.current) {
      el.scrollTop = el.scrollHeight;
      pegado.current = true;
    }
  }, [baki.mensajes, baki.pendientes]);

  return (
    <section className="chat panel">
      <div className="chat-mensajes" ref={contenedor}>
        {baki.mensajes.length === 0 && (
          <div className="chat-vacio">
            <div className={`orbe ${baki.trabajando ? "trabajando" : baki.hablando ? "hablando" : baki.microActivo ? "escuchando" : ""}`}>
              <span>BAKI</span><small>AI CORE</small>
            </div>
            <p>Escríbeme o pulsa <b>Hablar con BAKI</b>. En manos libres, di <b>«Baki, …»</b>.</p>
            <div className="ejemplos">
              {EJEMPLOS.map((ej) => <button key={ej} onClick={() => baki.enviar(ej)}>{ej}</button>)}
            </div>
          </div>
        )}
        {baki.mensajes.map((m) => (
          <article key={m.id} className={`mensaje ${m.rol}`}>
            <span className="autor">{m.rol === "usuario" ? "TÚ" : m.rol === "baki" ? "BAKI" : "SISTEMA"}</span>
            {m.rol === "baki" ? (m.texto ? <Markdown texto={m.texto} /> : <p className="escribiendo">● ● ●</p>) : <p>{m.texto}</p>}
          </article>
        ))}
        {baki.pendientes.map((p) => (
          <article key={p.id} className="aprobacion">
            <span className="autor">APROBACIÓN NECESARIA · {p.herramienta}</span>
            <pre>{p.resumen}</pre>
            <details>
              <summary>Ver argumentos exactos</summary>
              <pre>{JSON.stringify(p.argumentos, null, 2)}</pre>
            </details>
            <div className="botones">
              <button className="aprobar" onClick={() => baki.responder(p.id, true)}>Aprobar</button>
              {p.grupo && (
                <button className="aprobar" onClick={() => baki.responder(p.id, true, true)}>
                  Aprobar todos los de esta {p.etiqueta_grupo ?? "tarea"}
                </button>
              )}
              <button className="rechazar" onClick={() => baki.responder(p.id, false)}>Rechazar</button>
              <small>{p.grupo ? "o di «sí», «sí a todo» o «no»" : "o di «sí» / «no»"}</small>
            </div>
          </article>
        ))}
        <div ref={fin} />
      </div>
      <Compositor baki={baki} />
    </section>
  );
}
