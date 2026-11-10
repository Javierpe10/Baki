import type { ReactNode } from "react";

// Markdown mínimo y seguro: se construyen elementos React, nunca HTML crudo.
function enLinea(texto: string, clave: string): ReactNode[] {
  const partes: ReactNode[] = [];
  const re = /(\[[^\]]+\]\(https?:\/\/[^\s)]+\)|\*\*[^*]+\*\*|`[^`]+`|\*[^*\s][^*]*\*)/g;
  let ultimo = 0;
  let m: RegExpExecArray | null;
  let i = 0;
  while ((m = re.exec(texto)) !== null) {
    if (m.index > ultimo) partes.push(texto.slice(ultimo, m.index));
    const t = m[0];
    const k = `${clave}-${i++}`;
    const enlace = t.match(/^\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)$/);
    if (enlace) partes.push(<a key={k} href={enlace[2]} target="_blank" rel="noopener noreferrer">{enlace[1]}</a>);
    else if (t.startsWith("**")) partes.push(<strong key={k}>{t.slice(2, -2)}</strong>);
    else if (t.startsWith("`")) partes.push(<code key={k}>{t.slice(1, -1)}</code>);
    else partes.push(<em key={k}>{t.slice(1, -1)}</em>);
    ultimo = m.index + t.length;
  }
  if (ultimo < texto.length) partes.push(texto.slice(ultimo));
  return partes;
}

export function Markdown({ texto }: { texto: string }) {
  const lineas = texto.split("\n");
  const bloques: ReactNode[] = [];
  let lista: { ordenada: boolean; items: string[] } | null = null;
  let codigo: string[] | null = null;

  const cerrarLista = () => {
    if (!lista) return;
    const k = `l${bloques.length}`;
    const items = lista.items.map((it, i) => <li key={i}>{enLinea(it, `${k}-${i}`)}</li>);
    bloques.push(lista.ordenada ? <ol key={k}>{items}</ol> : <ul key={k}>{items}</ul>);
    lista = null;
  };

  lineas.forEach((linea, n) => {
    if (linea.trim().startsWith("```")) {
      if (codigo) {
        bloques.push(<pre key={`c${n}`}><code>{codigo.join("\n")}</code></pre>);
        codigo = null;
      } else {
        cerrarLista();
        codigo = [];
      }
      return;
    }
    if (codigo) {
      codigo.push(linea);
      return;
    }
    const vineta = linea.match(/^\s*[-*•]\s+(.*)$/);
    const numero = linea.match(/^\s*\d+[.)]\s+(.*)$/);
    if (vineta || numero) {
      const ordenada = Boolean(numero);
      if (!lista || lista.ordenada !== ordenada) {
        cerrarLista();
        lista = { ordenada, items: [] };
      }
      lista.items.push((vineta ?? numero)![1]);
      return;
    }
    cerrarLista();
    const titulo = linea.match(/^(#{1,4})\s+(.*)$/);
    if (titulo) {
      bloques.push(<p key={`h${n}`} className="md-titulo">{enLinea(titulo[2], `h${n}`)}</p>);
    } else if (/^\s*\|.*\|\s*$/.test(linea)) {
      if (!/^\s*\|[\s:|-]+\|\s*$/.test(linea)) {
        const celdas = linea.trim().slice(1, -1).split("|").map((c) => c.trim());
        bloques.push(<div key={`t${n}`} className="md-fila">{celdas.map((c, i) => <span key={i}>{enLinea(c, `t${n}-${i}`)}</span>)}</div>);
      }
    } else if (linea.trim()) {
      bloques.push(<p key={`p${n}`}>{enLinea(linea, `p${n}`)}</p>);
    } else {
      bloques.push(<div key={`e${n}`} className="md-espacio" />);
    }
  });
  if (codigo) bloques.push(<pre key="c-fin"><code>{(codigo as string[]).join("\n")}</code></pre>);
  cerrarLista();
  return <div className="md">{bloques}</div>;
}
