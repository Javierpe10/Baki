// Iconos de línea (24x24) que heredan el color del texto.
import type { ReactNode } from "react";

type P = { tam?: number };

const Base = ({ tam = 18, children }: P & { children: ReactNode }) => (
  <svg width={tam} height={tam} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"
    strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    {children}
  </svg>
);

export const IcoMando = (p: P) => <Base {...p}><rect x="3" y="3" width="7" height="7" rx="1.5" /><rect x="14" y="3" width="7" height="7" rx="1.5" /><rect x="3" y="14" width="7" height="7" rx="1.5" /><rect x="14" y="14" width="7" height="7" rx="1.5" /></Base>;
export const IcoChat = (p: P) => <Base {...p}><path d="M21 12a8 8 0 0 1-11.6 7.1L4 20l1-4.4A8 8 0 1 1 21 12z" /></Base>;
export const IcoHistorial = (p: P) => <Base {...p}><path d="M3 12a9 9 0 1 0 3-6.7L3 8" /><path d="M3 3v5h5" /><path d="M12 7v5l3 2" /></Base>;
export const IcoTareas = (p: P) => <Base {...p}><path d="M9 6h11M9 12h11M9 18h11" /><path d="m3 6 1.5 1.5L7 5M3 12l1.5 1.5L7 11M3 18l1.5 1.5L7 17" /></Base>;
export const IcoSkills = (p: P) => <Base {...p}><path d="M12 3 4 7v6c0 4.4 3.4 7.8 8 8 4.6-.2 8-3.6 8-8V7l-8-4z" /><path d="m9 12 2 2 4-4" /></Base>;
export const IcoConector = (p: P) => <Base {...p}><path d="M9 7V3M15 7V3" /><rect x="6" y="7" width="12" height="6" rx="2" /><path d="M12 13v3a4 4 0 0 1-4 4H6" /></Base>;
export const IcoMicro = (p: P) => <Base {...p}><rect x="9" y="3" width="6" height="11" rx="3" /><path d="M5 11a7 7 0 0 0 14 0M12 18v3" /></Base>;
export const IcoEnviar = (p: P) => <Base {...p}><path d="M5 12h14M13 6l6 6-6 6" /></Base>;
export const IcoParar = (p: P) => <Base {...p}><rect x="6" y="6" width="12" height="12" rx="2" /></Base>;
export const IcoAltavoz = (p: P) => <Base {...p}><path d="M4 9v6h4l5 4V5L8 9H4z" /><path d="M17 9a4 4 0 0 1 0 6" /></Base>;
export const IcoMudo = (p: P) => <Base {...p}><path d="M4 9v6h4l5 4V5L8 9H4z" /><path d="m17 9 4 6M21 9l-4 6" /></Base>;
export const IcoMas = (p: P) => <Base {...p}><path d="M12 5v14M5 12h14" /></Base>;
export const IcoReloj = (p: P) => <Base {...p}><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" /></Base>;
export const IcoOk = (p: P) => <Base {...p}><path d="m5 12 4.5 4.5L19 7" /></Base>;
export const IcoError = (p: P) => <Base {...p}><circle cx="12" cy="12" r="9" /><path d="M12 7v6M12 17h.01" /></Base>;
export const IcoLapiz = (p: P) => <Base {...p}><path d="M4 20h4L19 9l-4-4L4 16v4z" /><path d="m13.5 6.5 4 4" /></Base>;
