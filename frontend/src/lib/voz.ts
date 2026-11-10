import { ACTION_HEADERS, API } from "./api";

export type ProveedorVoz = "elevenlabs" | "local" | "navegador";

/** Limpia Markdown y URLs para que la voz no lea símbolos. */
export function paraHablar(texto: string): string {
  return texto
    .replace(/```[\s\S]*?```/g, " ")
    .replace(/https?:\/\/\S+/g, "el enlace")
    .replace(/[*_#`>|~]/g, "")
    .replace(/\[([^\]]+)\]\([^)]*\)/g, "$1")
    .replace(/\s+/g, " ")
    .trim();
}

/** Extrae frases completas de un búfer en streaming. Devuelve [frases, resto]. */
export function cortarFrases(buffer: string): [string[], string] {
  const frases: string[] = [];
  const re = /[^.!?…\n]+[.!?…]+["»)]?\s+|[^\n]+\n+/g;
  let ultimo = 0;
  let m: RegExpExecArray | null;
  while ((m = re.exec(buffer)) !== null) {
    if (m.index !== ultimo) break;
    ultimo = re.lastIndex;
    const f = m[0].trim();
    if (f) frases.push(f);
  }
  return [frases, buffer.slice(ultimo)];
}

// La voz se elige una vez y se mantiene. Las voces del navegador cargan tarde:
// sin esperar, la primera frase saldría con la voz por defecto y el resto con la
// natural, y sonarían dos voces distintas.
let vozElegida: SpeechSynthesisVoice | null = null;

function elegirVoz(): SpeechSynthesisVoice | null {
  const voces = window.speechSynthesis.getVoices().filter((v) => v.lang.toLowerCase().startsWith("es"));
  if (!voces.length) return null;
  const puntuar = (v: SpeechSynthesisVoice) =>
    (/natural|online|neural/i.test(v.name) ? 10 : 0) +
    (v.lang === "es-ES" ? 3 : 0) +
    (/google/i.test(v.name) ? 2 : 0);
  return [...voces].sort((a, b) => puntuar(b) - puntuar(a))[0];
}

if (typeof window !== "undefined" && "speechSynthesis" in window) {
  vozElegida = elegirVoz();
  window.speechSynthesis.addEventListener("voiceschanged", () => {
    const mejor = elegirVoz();
    // Solo se cambia si la nueva es mejor (por ejemplo, llegan las voces naturales).
    if (mejor && (!vozElegida || (/natural|online|neural/i.test(mejor.name) && !/natural|online|neural/i.test(vozElegida.name)))) {
      vozElegida = mejor;
    }
  });
}

function esperarVoces(): Promise<void> {
  if (vozElegida) return Promise.resolve();
  return new Promise((resolve) => {
    const fin = () => {
      vozElegida = vozElegida ?? elegirVoz();
      resolve();
    };
    window.speechSynthesis.addEventListener("voiceschanged", fin, { once: true });
    window.setTimeout(fin, 1500);
  });
}

const normalizarEco = (t: string) =>
  t.toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "").replace(/[^a-z0-9ñ\s]/g, " ").split(/\s+/).filter(Boolean);

/**
 * Detector de eco: el micrófono oye los altavoces, así que lo que BAKI acaba de
 * decir vuelve como si lo hubieras dicho tú. Se compara cada frase oída con lo
 * dicho en los últimos segundos; si casi todas sus palabras coinciden, es eco.
 */
export class MemoriaEco {
  private dichas: { palabras: Set<string>; t: number }[] = [];
  private ventanaMs: number;

  constructor(ventanaMs = 20_000) {
    this.ventanaMs = ventanaMs;
  }

  registrar(texto: string, ahora = Date.now()) {
    this.dichas.push({ palabras: new Set(normalizarEco(texto)), t: ahora });
    this.dichas = this.dichas.filter((d) => ahora - d.t < this.ventanaMs);
  }

  esEco(oido: string, ahora = Date.now()): boolean {
    const palabras = normalizarEco(oido);
    if (!palabras.length) return true;
    const recientes = new Set<string>();
    for (const d of this.dichas) if (ahora - d.t < this.ventanaMs) d.palabras.forEach((p) => recientes.add(p));
    if (!recientes.size) return false;
    const coinciden = palabras.filter((p) => recientes.has(p)).length;
    // Frases cortas: todas deben coincidir. Largas: el 60 % basta (el reconocedor se equivoca).
    return palabras.length <= 2 ? coinciden === palabras.length : coinciden / palabras.length >= 0.6;
  }
}

export class Hablante {
  proveedor: ProveedorVoz = "navegador";
  readonly eco = new MemoriaEco();
  /** Momento en que BAKI terminó de hablar por última vez (para la cola del eco). */
  finUltimaFrase = 0;
  private cola: Promise<string | null>[] = [];
  private reproduciendo = false;
  private audio: HTMLAudioElement | null = null;
  private generacion = 0;
  onCambio: (hablando: boolean) => void = () => {};

  get hablando() {
    return this.reproduciendo;
  }

  encolar(texto: string) {
    const limpio = paraHablar(texto);
    if (!limpio) return;
    this.eco.registrar(limpio);
    // Se pide el audio en cuanto llega la frase (precarga), y se reproduce en orden.
    this.cola.push(this.proveedor === "navegador" ? Promise.resolve(`tts:${limpio}`) : this.pedirAudio(limpio));
    if (!this.reproduciendo) void this.bucle();
  }

  private async pedirAudio(texto: string): Promise<string | null> {
    try {
      const r = await fetch(`${API}/tts`, {
        method: "POST",
        headers: { ...ACTION_HEADERS, "Content-Type": "application/json" },
        body: JSON.stringify({ texto }),
      });
      if (r.status === 200) return URL.createObjectURL(await r.blob());
    } catch {
      /* cae a la voz del navegador */
    }
    return `tts:${texto}`;
  }

  private async bucle() {
    const gen = this.generacion;
    this.reproduciendo = true;
    this.onCambio(true);
    while (this.cola.length && gen === this.generacion) {
      const item = await this.cola.shift()!;
      if (gen !== this.generacion || !item) break;
      if (item.startsWith("tts:")) await this.hablarNavegador(item.slice(4));
      else await this.reproducir(item);
    }
    if (gen === this.generacion) {
      this.reproduciendo = false;
      this.finUltimaFrase = Date.now();
      this.onCambio(false);
    }
  }

  /** Hablando ahora o hace menos de `margenMs` (el reconocedor entrega el eco con retraso). */
  hablandoHace(margenMs = 1500): boolean {
    return this.reproduciendo || Date.now() - this.finUltimaFrase < margenMs;
  }

  // Referencia viva: si el navegador recoge la frase de la memoria, nunca avisa
  // de que ha terminado y la cola se atasca.
  private fraseActual: SpeechSynthesisUtterance | null = null;

  private async hablarNavegador(texto: string): Promise<void> {
    await esperarVoces();
    return new Promise((resolve) => {
      const u = new SpeechSynthesisUtterance(texto);
      this.fraseActual = u;
      const voz = vozElegida;
      if (voz) u.voice = voz;
      u.lang = voz?.lang ?? "es-ES";
      u.rate = 1.05;
      const terminar = () => {
        if (this.fraseActual === u) this.fraseActual = null;
        resolve();
      };
      u.onend = terminar;
      u.onerror = terminar;
      window.speechSynthesis.speak(u);
    });
  }

  private reproducir(url: string): Promise<void> {
    return new Promise((resolve) => {
      const a = new Audio(url);
      this.audio = a;
      const fin = () => {
        URL.revokeObjectURL(url);
        this.audio = null;
        resolve();
      };
      a.onended = fin;
      a.onerror = fin;
      a.play().catch(fin);
    });
  }

  detener() {
    this.generacion++;
    this.cola = [];
    window.speechSynthesis.cancel();
    if (this.audio) {
      this.audio.pause();
      this.audio = null;
    }
    if (this.reproduciendo) {
      this.reproduciendo = false;
      this.finUltimaFrase = Date.now();
      this.onCambio(false);
    }
  }
}

type ResultadoVoz = { isFinal: boolean; 0: { transcript: string } };
type EventoVoz = { resultIndex: number; results: ArrayLike<ResultadoVoz> };
type ErrorVoz = { error: string };
type VentanaVoz = { SpeechRecognition?: new () => Reconocedor; webkitSpeechRecognition?: new () => Reconocedor };

type Reconocedor = {
  lang: string;
  continuous: boolean;
  interimResults: boolean;
  start(): void;
  stop(): void;
  abort(): void;
  onresult: ((e: EventoVoz) => void) | null;
  onend: (() => void) | null;
  onerror: ((e: ErrorVoz) => void) | null;
};

export function vozDisponible(): boolean {
  const w = window as unknown as VentanaVoz;
  return Boolean(w.SpeechRecognition || w.webkitSpeechRecognition);
}

/** Reconocimiento continuo con reinicio automático (Chrome/Edge lo cortan cada cierto tiempo). */
export class Oyente {
  private rec: Reconocedor | null = null;
  private activo = false;
  onFinal: (texto: string) => void = () => {};
  onParcial: (texto: string) => void = () => {};
  onError: (mensaje: string) => void = () => {};

  iniciar() {
    if (this.activo) return;
    const w = window as unknown as VentanaVoz;
    const Clase = w.SpeechRecognition || w.webkitSpeechRecognition;
    if (!Clase) {
      this.onError("Este navegador no tiene reconocimiento de voz. Usa Microsoft Edge o Google Chrome.");
      return;
    }
    this.activo = true;
    const rec: Reconocedor = new Clase();
    rec.lang = "es-ES";
    rec.continuous = true;
    rec.interimResults = true;
    rec.onresult = (e: EventoVoz) => {
      for (let i = e.resultIndex; i < e.results.length; i++) {
        const t = e.results[i][0].transcript.trim();
        if (!t) continue;
        if (e.results[i].isFinal) this.onFinal(t);
        else this.onParcial(t);
      }
    };
    rec.onerror = (e: ErrorVoz) => {
      if (e.error === "not-allowed" || e.error === "service-not-allowed") {
        this.activo = false;
        this.onError("Permiso de micrófono denegado. Actívalo en el candado de la barra de direcciones.");
      }
    };
    rec.onend = () => {
      if (this.activo) {
        setTimeout(() => {
          try {
            rec.start();
          } catch {
            /* ya estaba arrancado */
          }
        }, 250);
      }
    };
    this.rec = rec;
    try {
      rec.start();
    } catch {
      /* ignorar */
    }
  }

  detener() {
    this.activo = false;
    this.rec?.abort();
    this.rec = null;
  }

  get escuchando() {
    return this.activo;
  }
}
