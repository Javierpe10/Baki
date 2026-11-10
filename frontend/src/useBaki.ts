import { useCallback, useEffect, useRef, useState } from "react";
import {
  WS_URL, cambiarConfig, enviarPost, leer, obtenerEstado,
  type Estado, type Mensaje, type Solicitud, type Tarea, type Uso,
} from "./lib/api";
import { Hablante, Oyente, cortarFrases } from "./lib/voz";

const normalizar = (t: string) =>
  t.toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "").replace(/[¿?¡!.,]/g, " ").replace(/\s+/g, " ").trim();

const RE_ACTIVACION = /^(?:.*?\b)?(?:hola |oye |hey )?(?:baki|vaki|baqui|vaqui|waki|paki|backy|baky)\b\s*/;
const RE_PARAR = /^(para|stop|calla|callate|silencio|basta|detente)\b/;
const RE_SI = /^(si|hazlo|adelante|confirmo|confirmado|dale|ok|okay|vale|apruebo|aprobado|venga|correcto)\b/;
const RE_TODO = /\b(todo|todos|todas)\b/;
const RE_NO = /^(no|cancela|cancelar|rechaza|rechazar|nada|mejor no)\b/;

let siguienteId = 1;
const nuevoId = () => siguienteId++;
const hora = () => new Date().toLocaleTimeString("es-ES", { hour: "2-digit", minute: "2-digit" });

type Conversacion = { id: string; mensajes: { rol: "usuario" | "baki"; texto: string }[]; tareas: Tarea[] };

export function useBaki() {
  const [conectado, setConectado] = useState(false);
  const [estado, setEstado] = useState<Estado | null>(null);
  const [mensajes, setMensajes] = useState<Mensaje[]>([]);
  const [tareas, setTareas] = useState<Tarea[]>([]);
  const [pendientes, setPendientes] = useState<Solicitud[]>([]);
  const [trabajando, setTrabajando] = useState(false);
  const [manosLibres, setManosLibres] = useState(false);
  const [microActivo, setMicroActivo] = useState(false);
  const [parcial, setParcial] = useState("");
  const [hablando, setHablando] = useState(false);
  const [vozActiva, setVozActiva] = useState(true);
  const [uso, setUso] = useState<Uso | null>(null);
  const [conversacionId, setConversacionId] = useState<string | null>(null);
  const [borrador, setBorrador] = useState("");

  const ws = useRef<WebSocket | null>(null);
  const hablante = useRef(new Hablante());
  const oyente = useRef(new Oyente());
  const bufferVoz = useRef("");
  const idActual = useRef<number | null>(null);
  const ventanaConversacion = useRef(0);
  const ventanaAprobacion = useRef(0);
  const pendientesRef = useRef<Solicitud[]>([]);
  const manosLibresRef = useRef(false);
  const vozActivaRef = useRef(true);
  const trabajandoRef = useRef(false);
  // Solo habla la ventana que el backend designa (la última que usaste)…
  const ventanaHabla = useRef(true);
  // …y solo si la orden se dio por voz. Escribiendo, BAKI responde en silencio.
  const ordenPorVoz = useRef(false);

  useEffect(() => {
    pendientesRef.current = pendientes;
    manosLibresRef.current = manosLibres;
    vozActivaRef.current = vozActiva;
    trabajandoRef.current = trabajando;
  }, [pendientes, manosLibres, vozActiva, trabajando]);

  const decir = useCallback((t: string) => {
    if (vozActivaRef.current && ventanaHabla.current && ordenPorVoz.current) hablante.current.encolar(t);
  }, []);

  const volcarVoz = useCallback((todo: boolean) => {
    const [frases, resto] = cortarFrases(bufferVoz.current);
    frases.forEach(decir);
    bufferVoz.current = resto;
    if (todo && resto.trim()) {
      decir(resto);
      bufferVoz.current = "";
    }
  }, [decir]);

  const anadirSistema = useCallback((t: string) => {
    setMensajes((m) => [...m, { id: nuevoId(), rol: "sistema", texto: t }]);
  }, []);

  const anexarABaki = useCallback((fragmento: string) => {
    const id = idActual.current;
    if (id === null) return;
    setMensajes((m) => m.map((x) => (x.id === id ? { ...x, texto: x.texto + fragmento } : x)));
  }, []);

  const recargarUso = useCallback(async () => {
    const u = await leer<Uso>("/uso");
    if (u) setUso(u);
  }, []);

  const cargarConversacion = useCallback(async (id: string | null) => {
    setConversacionId(id);
    if (!id) {
      setMensajes([]);
      setTareas([]);
      return;
    }
    const c = await leer<Conversacion>(`/conversaciones/${id}`);
    if (!c) return;
    setMensajes(c.mensajes.map((m) => ({ id: nuevoId(), rol: m.rol, texto: m.texto })));
    setTareas(c.tareas);
  }, []);

  // ------------------------------------------------ WebSocket
  useEffect(() => {
    let cerrado = false;
    let reintento: number | undefined;

    const conectar = () => {
      const socket = new WebSocket(WS_URL);
      ws.current = socket;
      socket.onopen = async () => {
        setConectado(true);
        obtenerEstado().then(setEstado);
        void recargarUso();
        const lista = await leer<{ actual: string | null }>("/conversaciones");
        if (lista) await cargarConversacion(lista.actual);
      };
      socket.onclose = () => {
        setConectado(false);
        if (!cerrado) reintento = window.setTimeout(conectar, 2000);
      };
      socket.onmessage = (ev) => {
        const e = JSON.parse(ev.data);
        if (typeof e.hablar === "boolean") {
          ventanaHabla.current = e.hablar;
          if (!e.hablar) hablante.current.detener();
        }
        switch (e.type) {
          case "hola":
            setPendientes(e.pendientes ?? []);
            setTrabajando(Boolean(e.ocupado));
            break;
          case "inicio": {
            setTrabajando(true);
            bufferVoz.current = "";
            const id = nuevoId();
            idActual.current = id;
            setMensajes((m) => [...m, { id, rol: "baki", texto: "" }]);
            break;
          }
          case "segmento":
            volcarVoz(true);
            setMensajes((m) =>
              m.map((x) => (x.id === idActual.current && x.texto && !/\s$/.test(x.texto) ? { ...x, texto: x.texto + "\n\n" } : x)),
            );
            break;
          case "delta":
            anexarABaki(e.texto);
            bufferVoz.current += e.texto;
            volcarVoz(false);
            break;
          case "herramienta":
            volcarVoz(true);
            setTareas((t) => [
              ...t,
              {
                id: e.id ?? `local-${nuevoId()}`,
                nombre: e.nombre,
                resumen: e.resumen,
                nivel: e.nivel,
                estado: e.id ? "en_curso" : "hecha",
                hora: hora(),
              },
            ]);
            break;
          case "herramienta_fin":
            setTareas((t) => t.map((x) => (x.id === e.id ? { ...x, estado: e.ok ? "hecha" : "error" } : x)));
            break;
          case "aprobacion": {
            const s: Solicitud = e.solicitud;
            setPendientes((p) => [...p.filter((x) => x.id !== s.id), s]);
            ventanaAprobacion.current = Date.now() + 90_000;
            volcarVoz(true);
            decir(`Necesito tu aprobación: ${s.resumen.split("\n")[0].slice(0, 140)}. ¿Lo hago?`);
            break;
          }
          case "aprobacion_resuelta":
            setPendientes((p) => p.filter((x) => x.id !== e.id));
            break;
          case "fin": {
            setTrabajando(false);
            volcarVoz(true);
            const id = idActual.current;
            if (e.texto) {
              setMensajes((m) => m.map((x) => (x.id === id && !x.texto.trim() ? { ...x, texto: e.texto } : x)));
            }
            setMensajes((m) => m.filter((x) => x.rol !== "baki" || x.texto.trim() || x.id !== id));
            // Las tareas que no recibieron resultado (turno interrumpido) dejan de estar «en curso».
            setTareas((t) => t.map((x) => (x.estado === "en_curso" ? { ...x, estado: "hecha" } : x)));
            idActual.current = null;
            if (e.conversacion) setConversacionId(e.conversacion);
            ventanaConversacion.current = Date.now() + 12_000;
            break;
          }
          case "uso":
            setUso({ limite: e.limite, hoy: e.hoy, contexto: e.contexto });
            break;
          case "error":
            setTrabajando(false);
            anadirSistema(`⚠ ${e.texto}`);
            decir("Ha habido un error. Te lo dejo en pantalla.");
            break;
          case "aviso":
          case "estado":
            anadirSistema(e.texto);
            break;
          case "rutina": {
            const pend = (e.pendientes_de_aprobacion ?? []) as string[];
            anadirSistema(
              `Rutina «${e.nombre}»:\n${e.informe}` + (pend.length ? `\n\nPendiente de tu aprobación:\n• ${pend.join("\n• ")}` : ""),
            );
            if ("Notification" in window && Notification.permission === "granted") {
              new Notification(`BAKI · ${e.nombre}`, { body: String(e.informe).slice(0, 200) });
            }
            break;
          }
        }
      };
    };

    conectar();
    return () => {
      cerrado = true;
      window.clearTimeout(reintento);
      ws.current?.close();
    };
  }, [anadirSistema, anexarABaki, cargarConversacion, decir, recargarUso, volcarVoz]);

  useEffect(() => {
    hablante.current.onCambio = (h) => {
      setHablando(h);
      if (!h) ventanaConversacion.current = Date.now() + 10_000;
    };
    if (estado) hablante.current.proveedor = estado.voz;
  }, [estado]);

  // ------------------------------------------------ acciones
  const enviarWs = useCallback((datos: object) => {
    if (ws.current?.readyState === WebSocket.OPEN) {
      ws.current.send(JSON.stringify(datos));
      return true;
    }
    return false;
  }, []);

  const enviar = useCallback((t: string, porVoz = false) => {
    const limpio = t.trim();
    if (!limpio) return false;
    hablante.current.detener();
    ordenPorVoz.current = porVoz;
    if (!enviarWs({ type: "mensaje", texto: limpio })) {
      anadirSistema("Sin conexión con el backend de BAKI. Pulsa el icono BAKI del escritorio para arrancarlo.");
      return false;
    }
    setMensajes((m) => [...m, { id: nuevoId(), rol: "usuario", texto: limpio }]);
    return true;
  }, [anadirSistema, enviarWs]);

  const responder = useCallback((id: string, aprobar: boolean, todoElGrupo = false) => {
    enviarWs({ type: aprobar ? "aprobar" : "rechazar", id, grupo: todoElGrupo });
    setPendientes((p) => {
      const grupo = p.find((x) => x.id === id)?.grupo;
      return p.filter((x) => x.id !== id && !(todoElGrupo && grupo && x.grupo === grupo));
    });
  }, [enviarWs]);

  const detenerTodo = useCallback(() => {
    hablante.current.detener();
    enviarWs({ type: "interrumpir" });
  }, [enviarWs]);

  const nuevaConversacion = useCallback(() => {
    hablante.current.detener();
    enviarWs({ type: "nueva_conversacion" });
    setMensajes([]);
    setTareas([]);
    setConversacionId(null);
    setUso((u) => (u ? { ...u, contexto: null } : u));
  }, [enviarWs]);

  const abrirConversacion = useCallback(async (id: string) => {
    hablante.current.detener();
    const r = await enviarPost<{ ok: boolean }>(`/conversaciones/${id}/abrir`);
    if (r?.ok) {
      await cargarConversacion(id);
      setUso((u) => (u ? { ...u, contexto: null } : u));
    }
  }, [cargarConversacion]);

  const elegirModelo = useCallback(async (modelo: string) => {
    await cambiarConfig({ modelo });
    setEstado(await obtenerEstado());
  }, []);

  // ------------------------------------------------ voz
  const alOirFinal = useCallback((bruto: string) => {
    setParcial("");
    const t = normalizar(bruto);
    const activacion = t.match(RE_ACTIVACION);
    const resto = activacion ? t.slice(activacion.index! + activacion[0].length).trim() : t;
    const restoOriginal = activacion
      ? bruto.trim().split(/\s+/).slice(activacion[0].trim().split(/\s+/).length).join(" ")
      : bruto.trim();
    const h = hablante.current;

    // 0. Eco: lo que el micrófono oye de los altavoces mientras BAKI habla (o justo después) se descarta.
    if (h.hablandoHace() && h.eco.esEco(bruto)) return;

    const esParar = RE_PARAR.test(resto) && resto.split(" ").length <= 3;

    // 1. Aprobación por voz cuando BAKI ya ha terminado de preguntar.
    if (pendientesRef.current.length && Date.now() < ventanaAprobacion.current && !h.hablando) {
      const ultima = pendientesRef.current[pendientesRef.current.length - 1];
      if (RE_SI.test(resto)) return responder(ultima.id, true, Boolean(ultima.grupo) && RE_TODO.test(resto));
      if (RE_NO.test(resto)) return responder(ultima.id, false);
    }

    // 2. Mientras BAKI habla o trabaja, solo cuentan «Baki, …» o «para».
    if (h.hablandoHace() || trabajandoRef.current) {
      if (esParar) {
        h.detener();
        if (activacion && trabajandoRef.current) enviarWs({ type: "interrumpir" });
      } else if (activacion) {
        h.detener();
        if (resto) enviar(restoOriginal, true);
      }
      return;
    }

    // 3. Palabra de activación o continuación de la conversación.
    if (activacion) {
      if (resto) enviar(restoOriginal, true);
      else {
        ventanaConversacion.current = Date.now() + 8_000;
        ordenPorVoz.current = true;
        decir("¿Sí?");
      }
      return;
    }
    if (Date.now() < ventanaConversacion.current || !manosLibresRef.current) {
      enviar(bruto, true);
      if (!manosLibresRef.current) {
        oyente.current.detener();
        setMicroActivo(false);
      }
    }
  }, [decir, enviar, enviarWs, responder]);

  useEffect(() => {
    const o = oyente.current;
    o.onFinal = alOirFinal;
    o.onParcial = (p) => {
      setParcial(p);
      const h = hablante.current;
      if (h.hablando && RE_ACTIVACION.test(normalizar(p)) && !h.eco.esEco(p)) h.detener();
    };
    o.onError = (m) => {
      anadirSistema(m);
      setMicroActivo(false);
      setManosLibres(false);
    };
  }, [alOirFinal, anadirSistema]);

  const alternarManosLibres = useCallback(() => {
    if (manosLibresRef.current) {
      oyente.current.detener();
      setManosLibres(false);
      setMicroActivo(false);
      setParcial("");
    } else {
      setManosLibres(true);
      setMicroActivo(true);
      oyente.current.iniciar();
      if ("Notification" in window && Notification.permission === "default") void Notification.requestPermission();
    }
  }, []);

  const pulsarMicro = useCallback(() => {
    if (manosLibresRef.current) return;
    if (oyente.current.escuchando) {
      oyente.current.detener();
      setMicroActivo(false);
      setParcial("");
    } else {
      hablante.current.detener();
      setMicroActivo(true);
      oyente.current.iniciar();
    }
  }, []);

  return {
    conectado, estado, mensajes, tareas, pendientes, trabajando, manosLibres, microActivo, parcial,
    hablando, vozActiva, uso, conversacionId, borrador,
    setBorrador, setVozActiva, enviar, responder, detenerTodo, nuevaConversacion, abrirConversacion,
    elegirModelo, alternarManosLibres, pulsarMicro, recargarUso,
  };
}

export type Baki = ReturnType<typeof useBaki>;
