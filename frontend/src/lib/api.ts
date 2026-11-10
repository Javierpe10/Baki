// Si la interfaz la sirve el propio backend (puerto 8001) se usa el mismo origen;
// en desarrollo (Vite, 5173) se habla con 127.0.0.1:8001.
const mismoOrigen = window.location.port === "8001";

export const API = mismoOrigen ? "" : "http://127.0.0.1:8001";
export const WS_URL = mismoOrigen
  ? `ws://${window.location.host}/ws`
  : "ws://127.0.0.1:8001/ws";

export const ACTION_HEADERS = { "X-BAKI-Action": "1" };

export type Solicitud = {
  id: string;
  herramienta: string;
  resumen: string;
  argumentos: Record<string, unknown>;
  caduca_en_s: number;
  grupo?: string | null;
  etiqueta_grupo?: string | null;
};

export type Estado = {
  modelo: string;
  esfuerzo: string;
  voz: "elevenlabs" | "local" | "navegador";
  palabra_activacion: string;
  integraciones: Record<string, boolean>;
  carpetas_aprobadas: string[];
};

export async function obtenerEstado(): Promise<Estado | null> {
  try {
    const r = await fetch(`${API}/estado`, { headers: ACTION_HEADERS });
    return r.ok ? await r.json() : null;
  } catch {
    return null;
  }
}

export async function cambiarConfig(cambios: { modelo?: string; esfuerzo?: string }) {
  await fetch(`${API}/config`, {
    method: "POST",
    headers: { ...ACTION_HEADERS, "Content-Type": "application/json" },
    body: JSON.stringify(cambios),
  });
}

export type Mensaje = { id: number; rol: "usuario" | "baki" | "sistema"; texto: string };

export type Tarea = {
  id: string;
  nombre: string;
  resumen: string;
  nivel: number;
  estado: "en_curso" | "hecha" | "error";
  hora?: string;
};

export type Uso = {
  limite: { estado?: string; uso?: number | null; reinicia?: number | null; tipo?: string | null } | null;
  hoy: { turnos: number; tokens_procesados: number; tokens_generados: number };
  contexto: { porcentaje: number; tokens?: number; maximo?: number } | null;
};

export type Skill = { nombre: string; descripcion: string; automatica: boolean; origen: string };
export type Conversacion = { id: string; titulo: string; actualizada: number; creada?: number | null };
export type Rutina = { id: string; nombre: string; hora: string; dias: string[]; instruccion: string; activa?: boolean };

export async function leer<T>(ruta: string): Promise<T | null> {
  try {
    const r = await fetch(`${API}${ruta}`, { headers: ACTION_HEADERS });
    return r.ok ? ((await r.json()) as T) : null;
  } catch {
    return null;
  }
}

export async function enviarPost<T>(ruta: string, cuerpo?: object): Promise<T | null> {
  try {
    const r = await fetch(`${API}${ruta}`, {
      method: "POST",
      headers: { ...ACTION_HEADERS, "Content-Type": "application/json" },
      body: cuerpo ? JSON.stringify(cuerpo) : undefined,
    });
    return r.ok ? ((await r.json()) as T) : null;
  } catch {
    return null;
  }
}
