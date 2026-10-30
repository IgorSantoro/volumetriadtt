"""Componentes visuais em HTML/SVG puro (sem dependências de gráficos)."""
from __future__ import annotations

from html import escape

import pandas as pd

# ============================== CONSTANTES ==============================
NAVY = "#1B2A4A"
TEAL = "#0F8B8D"
ORANGE = "#F28C28"
RED = "#C0392B"
GRAY = "#8A94A6"
LIGHT = "#F4F6FA"
BORDER = "#E1E5EE"

COR_GRUPO = {"Concluída": TEAL, "Em análise da auditoria": NAVY, "Pendente Energisa": ORANGE, "Cancelada / N.A.": GRAY}
COR_PRAZO = {"Antecipada": TEAL, "No dia": "#5FB3B3", "Em atraso": ORANGE, "Aberta no prazo": GRAY, "Aberta vencida": RED}
COR_CURVA = {"Vencimentos": GRAY, "Solicitadas": NAVY, "Entregues": ORANGE, "Aceitas": TEAL}

CSS = f"""
<style>
html, body, [class*="css"], .stMarkdown, .stDataFrame {{ font-family: Arial, Helvetica, sans-serif; }}
.block-container {{ padding-top: 1.4rem; }}
.cab {{ background:{NAVY}; color:#fff; border-radius:10px; padding:16px 22px; margin-bottom:14px;
        display:flex; justify-content:space-between; align-items:center; }}
.cab h1 {{ font-size:1.35rem; margin:0; color:#fff; }}
.cab .sub {{ font-size:.85rem; opacity:.85; }}
.cab .tag {{ background:{ORANGE}; padding:4px 12px; border-radius:14px; font-weight:bold; font-size:.85rem; }}
.kpi {{ background:#fff; border:1px solid {BORDER}; border-left:5px solid var(--c); border-radius:8px;
        padding:12px 14px; height:100%; }}
.kpi .rot {{ font-size:.74rem; color:{GRAY}; text-transform:uppercase; letter-spacing:.03em; }}
.kpi .val {{ font-size:1.65rem; font-weight:bold; color:{NAVY}; line-height:1.25; }}
.kpi .det {{ font-size:.76rem; color:#5A6475; }}
.painel {{ background:#fff; border:1px solid {BORDER}; border-radius:8px; padding:14px 16px; margin-bottom:12px; }}
.painel h4 {{ margin:0 0 10px 0; font-size:.95rem; color:{NAVY}; }}
.barra {{ display:flex; align-items:center; gap:8px; margin:5px 0; font-size:.82rem; }}
.barra .n {{ width:42%; color:#333; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }}
.barra .t {{ flex:1; background:{LIGHT}; border-radius:4px; height:16px; }}
.barra .f {{ height:16px; border-radius:4px; }}
.barra .v {{ width:44px; text-align:right; font-weight:bold; color:{NAVY}; }}
.badge {{ display:inline-block; padding:2px 9px; border-radius:10px; color:#fff; font-size:.75rem; font-weight:bold; }}
.alerta {{ border-left:4px solid {ORANGE}; background:#FFF6EC; padding:8px 12px; border-radius:6px;
           margin:6px 0; font-size:.85rem; }}
.alerta.r {{ border-color:{RED}; background:#FDEDEC; }}
.alerta.n {{ border-color:{NAVY}; background:#EEF1F7; }}
.leg {{ font-size:.78rem; color:#444; margin-top:4px; }}
.leg span {{ margin-right:14px; }}
.leg i {{ display:inline-block; width:10px; height:10px; border-radius:2px; margin-right:4px; }}
</style>
"""


# ============================== COMPONENTES ==============================
def cabecalho(ciclo: str, data_extracao, n_bases: int) -> str:
    return (f'<div class="cab"><div><h1>Acompanhamento de Solicitações da Auditoria</h1>'
            f'<div class="sub">Impostos Diretos · base extraída em {data_extracao:%d/%m/%Y}'
            f' · {n_bases} base(s) carregada(s)</div></div><div class="tag">{escape(ciclo)}</div></div>')


def kpi(rotulo: str, valor: str, detalhe: str = "", cor: str = NAVY) -> str:
    return (f'<div class="kpi" style="--c:{cor}"><div class="rot">{escape(rotulo)}</div>'
            f'<div class="val">{escape(valor)}</div><div class="det">{escape(detalhe)}</div></div>')


def badge(texto: str, cor: str) -> str:
    return f'<span class="badge" style="background:{cor}">{escape(texto)}</span>'


def barras(titulo: str, serie: pd.Series, cores: dict | None = None, cor_padrao: str = TEAL, sufixo: str = "") -> str:
    maximo = max(float(serie.max()) if len(serie) else 0, 1)
    linhas = []
    for nome, valor in serie.items():
        cor = (cores or {}).get(nome, cor_padrao)
        pct = float(valor) / maximo * 100
        txt = f"{valor:,.0f}".replace(",", ".") if float(valor).is_integer() else f"{valor:,.1f}".replace(",", "X").replace(".", ",").replace("X", ".")
        linhas.append(f'<div class="barra"><div class="n" title="{escape(str(nome))}">{escape(str(nome))}</div>'
                      f'<div class="t"><div class="f" style="width:{pct:.1f}%;background:{cor}"></div></div>'
                      f'<div class="v">{txt}{sufixo}</div></div>')
    corpo = "".join(linhas) or '<div class="leg">Sem dados.</div>'
    return f'<div class="painel"><h4>{escape(titulo)}</h4>{corpo}</div>'


def barra_empilhada(titulo: str, serie: pd.Series, cores: dict) -> str:
    total = max(int(serie.sum()), 1)
    blocos = "".join(
        f'<div title="{escape(str(n))}: {v}" style="width:{v / total * 100:.2f}%;background:{cores.get(n, GRAY)};'
        f'height:26px;display:flex;align-items:center;justify-content:center;color:#fff;font-size:.78rem;font-weight:bold">'
        f'{v if v / total > .06 else ""}</div>'
        for n, v in serie.items() if v > 0)
    leg = "".join(f'<span><i style="background:{cores.get(n, GRAY)}"></i>{escape(str(n))} ({v})</span>' for n, v in serie.items())
    return (f'<div class="painel"><h4>{escape(titulo)}</h4>'
            f'<div style="display:flex;border-radius:6px;overflow:hidden">{blocos}</div><div class="leg">{leg}</div></div>')


def curva_svg(curva: pd.DataFrame, titulo: str, largura: int = 900, altura: int = 260) -> str:
    if curva.empty:
        return f'<div class="painel"><h4>{escape(titulo)}</h4><div class="leg">Sem dados.</div></div>'
    m_esq, m_dir, m_top, m_base = 34, 12, 12, 28
    w, h = largura - m_esq - m_dir, altura - m_top - m_base
    n = len(curva)
    ymax = max(int(curva.values.max()), 1)

    def x(i): return m_esq + (i / max(n - 1, 1)) * w
    def y(v): return m_top + h - (v / ymax) * h

    grade = []
    passo = max(1, round(ymax / 4))
    for v in range(0, ymax + 1, passo):
        grade.append(f'<line x1="{m_esq}" x2="{m_esq + w}" y1="{y(v):.1f}" y2="{y(v):.1f}" stroke="{BORDER}"/>'
                     f'<text x="{m_esq - 6}" y="{y(v) + 4:.1f}" font-size="10" text-anchor="end" fill="{GRAY}">{v}</text>')
    rot = []
    salto = max(1, n // 10)
    for i, d in enumerate(curva.index):
        if i % salto == 0 or i == n - 1:
            rot.append(f'<text x="{x(i):.1f}" y="{altura - 8}" font-size="10" text-anchor="middle" fill="{GRAY}">{d:%d/%m}</text>')
    linhas = []
    for col in curva.columns:
        pts = " ".join(f"{x(i):.1f},{y(v):.1f}" for i, v in enumerate(curva[col].tolist()))
        traco = 'stroke-dasharray="5 4"' if col == "Vencimentos" else ""
        linhas.append(f'<polyline points="{pts}" fill="none" stroke="{COR_CURVA.get(col, NAVY)}" stroke-width="2.4" {traco}/>')
        ult = curva[col].iloc[-1]
        linhas.append(f'<circle cx="{x(n - 1):.1f}" cy="{y(ult):.1f}" r="3.5" fill="{COR_CURVA.get(col, NAVY)}"/>')
    leg = "".join(f'<span><i style="background:{COR_CURVA.get(c, NAVY)}"></i>{c} ({int(curva[c].iloc[-1])})</span>' for c in curva.columns)
    svg = (f'<svg viewBox="0 0 {largura} {altura}" width="100%" xmlns="http://www.w3.org/2000/svg" font-family="Arial">'
           f'{"".join(grade)}{"".join(rot)}{"".join(linhas)}</svg>')
    return f'<div class="painel"><h4>{escape(titulo)}</h4>{svg}<div class="leg">{leg}</div></div>'


def colunas_svg(dados: pd.DataFrame, col_x: str, col_y: str, titulo: str, cor: str = TEAL,
                largura: int = 900, altura: int = 220) -> str:
    if dados.empty:
        return f'<div class="painel"><h4>{escape(titulo)}</h4><div class="leg">Sem dados.</div></div>'
    m_esq, m_top, m_base = 30, 16, 28
    w, h = largura - m_esq - 10, altura - m_top - m_base
    n = len(dados)
    ymax = max(float(dados[col_y].max()), 1)
    larg = w / n
    barras_ = []
    for i, (_, r) in enumerate(dados.iterrows()):
        v = float(r[col_y])
        bh = v / ymax * h
        bx = m_esq + i * larg + larg * .15
        by = m_top + h - bh
        rotulo = r[col_x].strftime("%d/%m") if hasattr(r[col_x], "strftime") else str(r[col_x])
        barras_.append(
            f'<rect x="{bx:.1f}" y="{by:.1f}" width="{larg * .7:.1f}" height="{bh:.1f}" rx="3" fill="{cor}">'
            f'<title>{rotulo}: {v:,.0f}</title></rect>'
            f'<text x="{bx + larg * .35:.1f}" y="{by - 4:.1f}" font-size="10" text-anchor="middle" fill="{NAVY}" font-weight="bold">{v:,.0f}</text>'
            f'<text x="{bx + larg * .35:.1f}" y="{altura - 8}" font-size="10" text-anchor="middle" fill="{GRAY}">{escape(rotulo)}</text>')
    svg = (f'<svg viewBox="0 0 {largura} {altura}" width="100%" xmlns="http://www.w3.org/2000/svg" font-family="Arial">'
           f'<line x1="{m_esq}" x2="{m_esq + w}" y1="{m_top + h}" y2="{m_top + h}" stroke="{BORDER}"/>{"".join(barras_)}</svg>')
    return f'<div class="painel"><h4>{escape(titulo)}</h4>{svg}</div>'


def alerta(texto_html: str, tipo: str = "") -> str:
    return f'<div class="alerta {tipo}">{texto_html}</div>'
