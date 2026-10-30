"""Painel gerencial de solicitações da auditoria — Impostos Diretos.

Executar:  streamlit run app.py
Bases: arraste o(s) export(s) do portal na barra lateral ou salve-os na pasta ./bases
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

import componentes as ui
import metricas as mt
from exportacao import gerar_excel
from leitura import BaseAuditoria, ErroLeitura, ler_export

# ============================== CONSTANTES ==============================
PASTA_BASES = Path(__file__).parent / "bases"
EXTENSOES = ("xlsx", "xlsm", "xls")
TITULO_PAGINA = "Solicitações da Auditoria"

st.set_page_config(page_title=TITULO_PAGINA, page_icon="📋", layout="wide")
st.markdown(ui.CSS, unsafe_allow_html=True)


# ============================== CARGA ==============================
@st.cache_data(show_spinner=False)
def _ler_bytes(conteudo: bytes, nome: str) -> BaseAuditoria:
    from io import BytesIO
    return ler_export(BytesIO(conteudo), nome)


def carregar_bases(enviados, ler_pasta: bool) -> tuple[list[BaseAuditoria], list[str]]:
    bases, erros = [], []
    fontes: list[tuple[bytes, str]] = [(f.getvalue(), f.name) for f in (enviados or [])]
    if ler_pasta and PASTA_BASES.exists():
        fontes += [(p.read_bytes(), p.name) for p in sorted(PASTA_BASES.iterdir())
                   if p.suffix.lower().lstrip(".") in EXTENSOES and not p.name.startswith("~$")]
    vistos = set()
    for conteudo, nome in fontes:
        if nome in vistos:
            continue
        vistos.add(nome)
        try:
            bases.append(_ler_bytes(conteudo, nome))
        except ErroLeitura as exc:
            erros.append(f"{nome}: {exc}")
    return bases, erros


def fmt_num(v: float, casas: int = 0) -> str:
    return f"{v:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def fmt_volume(mb: float) -> str:
    return f"{fmt_num(mb / 1024, 2)} GB" if mb >= 1024 else f"{fmt_num(mb, 1)} MB"


# ============================== BARRA LATERAL ==============================
with st.sidebar:
    st.markdown("### 📥 Bases")
    enviados = st.file_uploader("Export(s) do portal da auditoria", type=list(EXTENSOES), accept_multiple_files=True)
    ler_pasta = st.checkbox(f"Ler também a pasta /{PASTA_BASES.name}", value=True,
                            help="Salve os exports nessa pasta para não precisar arrastar toda vez.")

bases, erros = carregar_bases(enviados, ler_pasta)
for e in erros:
    st.sidebar.error(e)

if not bases:
    st.markdown(ui.cabecalho("—", pd.Timestamp.today(), 0), unsafe_allow_html=True)
    st.info("Carregue o export de solicitações do portal da auditoria na barra lateral "
            f"(ou salve o arquivo na pasta **{PASTA_BASES.name}/** ao lado do app).")
    st.stop()

ciclos = sorted({b.ciclo for b in bases})
with st.sidebar:
    ciclo = st.selectbox("Ciclo", ciclos, index=len(ciclos) - 1)
    snaps = sorted([b for b in bases if b.ciclo == ciclo], key=lambda b: b.data_extracao)
    rotulos = [f"{b.data_extracao:%d/%m/%Y} · {b.nome_arquivo}" for b in snaps]
    i_snap = st.selectbox("Posição (data de extração)", range(len(snaps)), index=len(snaps) - 1,
                          format_func=lambda i: rotulos[i])
base = snaps[i_snap]
completo = mt.enriquecer(base)

with st.sidebar:
    st.markdown("### 🔎 Filtros")
    f_area = st.multiselect("Área", sorted(completo["area"].unique()))
    f_emp = st.multiselect("Empresa", sorted(completo["empresa"].unique()))
    f_sit = st.multiselect("Situação", [g for g in mt.ORDEM_GRUPOS if g in set(completo["grupo_status"])])

df = completo
if f_area:
    df = df[df["area"].isin(f_area)]
if f_emp:
    df = df[df["empresa"].isin(f_emp)]
if f_sit:
    df = df[df["grupo_status"].isin(f_sit)]
arquivos = base.arquivos[base.arquivos["id"].isin(df["id"])]
comentarios = base.comentarios[base.comentarios["id"].isin(df["id"])]
k = mt.kpis(df, arquivos)

with st.sidebar:
    st.markdown("---")
    st.download_button("⬇️ Exportar acompanhamento (Excel)",
                       data=gerar_excel(df, arquivos, comentarios, mt.resumo_por(df, "area")),
                       file_name=f"Acompanhamento_Auditoria_{ciclo.replace(' ', '_')}_{base.data_extracao:%Y%m%d}.xlsx",
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                       width="stretch")

# ============================== CABEÇALHO ==============================
st.markdown(ui.cabecalho(ciclo, base.data_extracao, len(bases)), unsafe_allow_html=True)
if df.empty:
    st.warning("Nenhuma solicitação com os filtros selecionados.")
    st.stop()

aba_geral, aba_pend, aba_solic, aba_atend, aba_comp = st.tabs(
    ["📊 Visão geral", "⚠️ Pendências", "📋 Solicitações", "📤 Atendimento", "📈 Comparativo"])

# ============================== VISÃO GERAL ==============================
with aba_geral:
    c = st.columns(5)
    c[0].markdown(ui.kpi("Solicitações", fmt_num(k["total"]), f"{k['entregues']} com entrega", ui.NAVY), unsafe_allow_html=True)
    c[1].markdown(ui.kpi("Concluídas (aceitas)", fmt_num(k["concluidas"]), f"{fmt_num(k['pct_conclusao'], 0)}% do total", ui.TEAL), unsafe_allow_html=True)
    c[2].markdown(ui.kpi("Em análise da auditoria", fmt_num(k["em_analise"]), "entregues, aguardando aceite", ui.NAVY), unsafe_allow_html=True)
    c[3].markdown(ui.kpi("Pendentes Energisa", fmt_num(k["pendentes"]), "sem entrega / devolvidas", ui.ORANGE), unsafe_allow_html=True)
    c[4].markdown(ui.kpi("Devolvidas pela auditoria", fmt_num(k["devolvidas"]), "com motivo de reenvio", ui.RED), unsafe_allow_html=True)
    st.write("")
    c = st.columns(5)
    c[0].markdown(ui.kpi("No prazo · 1ª entrega", f"{fmt_num(k['pct_prazo_1a'], 0)}%", "pela data do 1º arquivo enviado", ui.TEAL), unsafe_allow_html=True)
    c[1].markdown(ui.kpi("No prazo · portal", f"{fmt_num(k['pct_prazo_portal'], 0)}%", "pela data de apresentação atual", ui.GRAY), unsafe_allow_html=True)
    c[2].markdown(ui.kpi("Atraso médio", f"{fmt_num(k['atraso_medio'], 1)} d", "entre as entregues em atraso", ui.ORANGE), unsafe_allow_html=True)
    c[3].markdown(ui.kpi("Arquivos enviados", fmt_num(k["arquivos"]), fmt_volume(k["volume_mb"]), ui.NAVY), unsafe_allow_html=True)
    c[4].markdown(ui.kpi("Análise da auditoria", f"{fmt_num(k['analise_media'], 1)} d", "média apresentação → aceite", ui.TEAL), unsafe_allow_html=True)
    st.write("")

    st.markdown(ui.barra_empilhada("Situação das solicitações", mt.contagem(df, "grupo_status", mt.ORDEM_GRUPOS), ui.COR_GRUPO),
                unsafe_allow_html=True)
    e, d = st.columns(2)
    e.markdown(ui.barras("Solicitações por área", mt.contagem(df, "area"), cor_padrao=ui.NAVY), unsafe_allow_html=True)
    d.markdown(ui.barras("Cumprimento de prazo (1ª entrega)", mt.contagem(df, "prazo_1a_entrega", mt.ORDEM_PRAZO), ui.COR_PRAZO),
               unsafe_allow_html=True)
    st.markdown(ui.curva_svg(mt.curva_acumulada(df, base.data_extracao), "Evolução acumulada — solicitadas × vencimentos × entregues × aceitas"),
                unsafe_allow_html=True)
    if (df["prazo_portal"] != df["prazo_1a_entrega"]).any():
        n = int((df["prazo_portal"] != df["prazo_1a_entrega"]).sum())
        st.caption(f"ℹ️ {n} solicitação(ões) aparecem com prazo diferente no portal: quando há devolução e reenvio, "
                   "o portal passa a contar a data de apresentação mais recente. O painel usa a data do 1º arquivo enviado como referência principal.")

# ============================== PENDÊNCIAS ==============================
with aba_pend:
    pend = df[df["grupo_status"].eq("Pendente Energisa")].sort_values("dias_vencida_aberta", ascending=False)
    aguard = df[df["grupo_status"].eq("Em análise da auditoria")].sort_values("dias_aguardando_auditoria", ascending=False)
    devol = df[df["teve_devolucao"]]

    st.markdown(f"#### 🟠 Pendentes com a Energisa ({len(pend)})")
    if pend.empty:
        st.success("Nenhuma solicitação pendente de envio.")
    for _, r in pend.iterrows():
        venc = f"{r['dt_vencimento']:%d/%m}" if pd.notna(r["dt_vencimento"]) else "—"
        atraso = int(r["dias_vencida_aberta"]) if pd.notna(r["dias_vencida_aberta"]) else 0
        tipo = "r" if atraso > 0 else ""
        st.markdown(ui.alerta(f"<b>{r['id']}</b> · {r['area']} · {r['titulo']}<br>"
                              f"Vencimento {venc} · <b>{'vencida há ' + str(atraso) + ' dia(s)' if atraso else 'no prazo'}</b>", tipo),
                    unsafe_allow_html=True)

    st.markdown(f"#### 🔵 Entregues aguardando aceite da auditoria ({len(aguard)})")
    if aguard.empty:
        st.success("Nenhuma entrega aguardando aceite.")
    for _, r in aguard.iterrows():
        dias = int(r["dias_aguardando_auditoria"]) if pd.notna(r["dias_aguardando_auditoria"]) else 0
        st.markdown(ui.alerta(f"<b>{r['id']}</b> · {r['area']} · {r['titulo']}<br>"
                              f"Apresentada em {r['dt_apresentacao']:%d/%m/%Y} · aguardando há <b>{dias} dia(s)</b>"
                              f" · {r['n_arquivos']} arquivo(s)", "n"), unsafe_allow_html=True)

    st.markdown(f"#### 🔴 Solicitações com devolução / reenvio ({len(devol)})")
    if devol.empty:
        st.success("Nenhuma devolução registrada.")
    for _, r in devol.iterrows():
        ult = comentarios[comentarios["id"] == r["id"]].sort_values("dt_comentario").tail(1)
        txt = (f"“{ult.iloc[0]['comentario']}” — {ult.iloc[0]['autor']}, {ult.iloc[0]['dt_comentario']:%d/%m %H:%M}"
               if not ult.empty else "sem comentário registrado")
        st.markdown(ui.alerta(f"<b>{r['id']}</b> · {r['titulo']}<br>Motivo: {r['motivo_reenvio']} · "
                              f"Situação atual: {r['grupo_status']}<br><i>{txt}</i>", "r"), unsafe_allow_html=True)

# ============================== SOLICITAÇÕES ==============================
with aba_solic:
    vis = df[["id", "area", "empresa", "titulo", "grupo_status", "status", "dt_vencimento", "primeira_entrega",
              "dt_apresentacao", "dt_aceite", "prazo_1a_entrega", "dias_vs_venc_1a", "teve_devolucao",
              "n_arquivos", "volume_mb", "n_comentarios"]].sort_values("id")
    st.dataframe(
        vis, hide_index=True, width="stretch",
        column_config={
            "id": "ID", "area": "Área", "empresa": "Empresa",
            "titulo": st.column_config.TextColumn("Solicitação", width="large"),
            "grupo_status": "Situação", "status": "Status portal",
            "dt_vencimento": st.column_config.DatetimeColumn("Vencimento", format="DD/MM/YYYY"),
            "primeira_entrega": st.column_config.DatetimeColumn("1ª entrega", format="DD/MM/YYYY HH:mm"),
            "dt_apresentacao": st.column_config.DatetimeColumn("Apresentação", format="DD/MM/YYYY HH:mm"),
            "dt_aceite": st.column_config.DatetimeColumn("Aceite", format="DD/MM/YYYY HH:mm"),
            "prazo_1a_entrega": "Prazo", "dias_vs_venc_1a": st.column_config.NumberColumn("Dias vs venc.", help="Negativo = antecipada"),
            "teve_devolucao": st.column_config.CheckboxColumn("Devolvida"),
            "n_arquivos": "Arquivos", "volume_mb": st.column_config.NumberColumn("MB", format="%.1f"),
            "n_comentarios": "Coment.",
        })

    st.markdown("#### 🔍 Detalhe da solicitação")
    escolha = st.selectbox("Solicitação", vis["id"].tolist(),
                           format_func=lambda i: f"{i} · {df.loc[df['id'] == i, 'titulo'].iloc[0]}")
    r = df[df["id"] == escolha].iloc[0]
    e, d = st.columns([3, 2])
    with e:
        st.markdown(f"{ui.badge(r['grupo_status'], ui.COR_GRUPO.get(r['grupo_status'], ui.GRAY))} "
                    f"{ui.badge(r['prazo_1a_entrega'], ui.COR_PRAZO.get(r['prazo_1a_entrega'], ui.GRAY))}",
                    unsafe_allow_html=True)
        st.text(str(r["solicitacao"]).strip())
    with d:
        fmt = lambda v: f"{v:%d/%m/%Y %H:%M}" if pd.notna(v) else "—"
        st.markdown(f"""
| | |
|---|---|
| **Área / Categoria** | {r['area']} / {r['categoria'] or '—'} |
| **Criada em** | {fmt(r['dt_criacao'])} por {r['criado_por'] or '—'} |
| **Vencimento** | {fmt(r['dt_vencimento'])} |
| **1ª entrega** | {fmt(r['primeira_entrega'])} |
| **Apresentação (portal)** | {fmt(r['dt_apresentacao'])} |
| **Aceite** | {fmt(r['dt_aceite'])} |
| **Contatos Energisa** | {str(r['contatos_cliente'] or '—').replace(',', ', ')} |
| **Contatos auditoria** | {str(r['contatos_auditoria'] or '—').replace(',', ', ')} |
""")
    a = base.arquivos[base.arquivos["id"] == escolha].sort_values("dt_envio", ascending=False)
    st.markdown(f"**Arquivos enviados ({len(a)})**")
    st.dataframe(a.drop(columns="id"), hide_index=True, width="stretch",
                 column_config={"arquivo": "Arquivo", "tamanho_mb": st.column_config.NumberColumn("MB", format="%.2f"),
                                "dt_envio": st.column_config.DatetimeColumn("Enviado em", format="DD/MM/YYYY HH:mm"),
                                "enviado_por": "Enviado por"})
    cm = base.comentarios[base.comentarios["id"] == escolha]
    if not cm.empty:
        st.markdown("**Comentários da auditoria**")
        for _, c_ in cm.iterrows():
            st.markdown(ui.alerta(f"“{c_['comentario']}” — {c_['autor']}, {c_['dt_comentario']:%d/%m/%Y %H:%M}", "n"),
                        unsafe_allow_html=True)

# ============================== ATENDIMENTO ==============================
with aba_atend:
    por_dia = mt.envios_por_dia(arquivos)
    st.markdown(ui.colunas_svg(por_dia, "dia", "arquivos", "Arquivos enviados por dia"), unsafe_allow_html=True)
    e, d = st.columns(2)
    pessoas = mt.envios_por_pessoa(arquivos)
    e.markdown(ui.barras("Arquivos enviados por responsável", pessoas.set_index("enviado_por")["arquivos"], cor_padrao=ui.NAVY),
               unsafe_allow_html=True)
    top = df.set_index(df["id"] + " · " + df["empresa"])["n_arquivos"].sort_values(ascending=False).head(10)
    d.markdown(ui.barras("Solicitações com mais arquivos", top, cor_padrao=ui.TEAL), unsafe_allow_html=True)

    st.markdown("#### Resumo por área")
    st.dataframe(mt.resumo_por(df, "area"), width="stretch")
    st.markdown("#### Resumo por empresa")
    st.dataframe(mt.resumo_por(df, "empresa"), width="stretch")
    if not por_dia.empty:
        st.markdown("#### Envios por dia")
        st.dataframe(por_dia, hide_index=True, width="stretch",
                     column_config={"dia": st.column_config.DatetimeColumn("Dia", format="DD/MM/YYYY"),
                                    "arquivos": "Arquivos", "solicitacoes": "Solicitações atendidas",
                                    "volume_mb": st.column_config.NumberColumn("Volume (MB)", format="%.1f")})

# ============================== COMPARATIVO ==============================
with aba_comp:
    if len(bases) == 1:
        st.info("Carregue mais de um export (outros ciclos — 1ITR, 2ITR, DFP — ou outras datas de extração do mesmo ciclo) "
                "para comparar a volumetria e a evolução.")
    linhas = []
    for b in sorted(bases, key=lambda b: (b.ciclo, b.data_extracao)):
        dd = mt.enriquecer(b)
        kk = mt.kpis(dd, b.arquivos)
        linhas.append({"Ciclo": b.ciclo, "Extração": pd.Timestamp(b.data_extracao), "Solicitações": kk["total"],
                       "Concluídas": kk["concluidas"], "Em análise": kk["em_analise"], "Pendentes": kk["pendentes"],
                       "Devolvidas": kk["devolvidas"], "% no prazo (1ª entrega)": round(kk["pct_prazo_1a"], 1),
                       "Arquivos": kk["arquivos"], "Volume (MB)": round(kk["volume_mb"], 1),
                       "Análise auditoria (d)": round(kk["analise_media"], 1)})
    comp = pd.DataFrame(linhas)
    st.dataframe(comp, hide_index=True, width="stretch",
                 column_config={"Extração": st.column_config.DatetimeColumn(format="DD/MM/YYYY")})
    ult = comp.sort_values("Extração").groupby("Ciclo").tail(1)
    if len(ult) > 1:
        e, d = st.columns(2)
        e.markdown(ui.barras("Solicitações por ciclo", ult.set_index("Ciclo")["Solicitações"], cor_padrao=ui.NAVY), unsafe_allow_html=True)
        d.markdown(ui.barras("% no prazo por ciclo", ult.set_index("Ciclo")["% no prazo (1ª entrega)"], cor_padrao=ui.TEAL, sufixo="%"),
                   unsafe_allow_html=True)
