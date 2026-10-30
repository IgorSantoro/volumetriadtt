"""Regras de negócio: classificação de status, prazo, lead time e indicadores."""
from __future__ import annotations

import re
from datetime import date

import pandas as pd

from leitura import BaseAuditoria

# ============================== CONSTANTES ==============================
# Status do portal -> grupo gerencial (chave em minúsculas, sem espaços extras)
GRUPO_STATUS = {
    "pedido aceito": "Concluída",
    "aceito": "Concluída",
    "submetido pelo cliente": "Em análise da auditoria",
    "submetido": "Em análise da auditoria",
    "reenviado": "Pendente Energisa",
    "devolvido": "Pendente Energisa",
    "rejeitado": "Pendente Energisa",
    "aberto": "Pendente Energisa",
    "pendente": "Pendente Energisa",
    "enviado ao cliente": "Pendente Energisa",
    "não iniciado": "Pendente Energisa",
    "em andamento": "Pendente Energisa",
    "não aplicável": "Cancelada / N.A.",
    "cancelado": "Cancelada / N.A.",
}
GRUPO_PADRAO = "Pendente Energisa"
ORDEM_GRUPOS = ["Concluída", "Em análise da auditoria", "Pendente Energisa", "Cancelada / N.A."]

ORDEM_PRAZO = ["Antecipada", "No dia", "Em atraso", "Aberta no prazo", "Aberta vencida"]
RE_EMPRESA = re.compile(r"^\s*\[(?P<emp>[^\]]+)\]")
EMPRESA_PADRAO = "Diversas"
DIAS_ANTES_CURVA = 3  # dias exibidos antes do 1º evento operacional na curva


# ============================== AUXILIARES ==============================
def _grupo(status) -> str:
    if status is None or (isinstance(status, float) and pd.isna(status)):
        return GRUPO_PADRAO
    return GRUPO_STATUS.get(str(status).strip().lower(), GRUPO_PADRAO)


def _empresa(txt) -> str:
    m = RE_EMPRESA.match(str(txt or ""))
    return m["emp"].strip() if m else EMPRESA_PADRAO


def _dias(fim: pd.Series, ini: pd.Series) -> pd.Series:
    """Diferença em dias corridos entre datas (ignora horário)."""
    return (fim.dt.normalize() - ini.dt.normalize()).dt.days


def _classe_prazo(dias_vs_venc, vencimento, hoje: pd.Timestamp) -> str:
    if pd.isna(dias_vs_venc):
        if pd.isna(vencimento):
            return "Aberta no prazo"
        return "Aberta vencida" if hoje.normalize() > vencimento.normalize() else "Aberta no prazo"
    if dias_vs_venc < 0:
        return "Antecipada"
    return "No dia" if dias_vs_venc == 0 else "Em atraso"


def _titulo(txt, limite: int = 90) -> str:
    t = " ".join(str(txt or "").split())
    return t if len(t) <= limite else t[: limite - 1] + "…"


# ============================== ENRIQUECIMENTO ==============================
def enriquecer(base: BaseAuditoria) -> pd.DataFrame:
    """Devolve a tabela de solicitações com todas as colunas gerenciais calculadas."""
    df = base.solicitacoes.copy()
    hoje = pd.Timestamp(base.data_extracao)
    arq = base.arquivos

    df["ciclo"] = base.ciclo
    df["data_extracao"] = hoje
    df["empresa"] = df["solicitacao"].map(_empresa)
    df["titulo"] = df["solicitacao"].map(_titulo)
    df["area"] = df["area"].fillna("Sem área")
    df["grupo_status"] = df["status"].map(_grupo)
    df["teve_devolucao"] = df["motivo_reenvio"].notna() & (df["motivo_reenvio"].astype(str).str.strip() != "")

    if not arq.empty:
        agg = arq.groupby("id").agg(
            n_arquivos=("arquivo", "count"),
            volume_mb=("tamanho_mb", "sum"),
            primeira_entrega=("dt_envio", "min"),
            ultima_entrega=("dt_envio", "max"),
            dias_com_envio=("dt_envio", lambda s: s.dt.normalize().nunique()),
        )
        df = df.merge(agg, how="left", left_on="id", right_index=True)
    else:
        for c in ["n_arquivos", "volume_mb", "primeira_entrega", "ultima_entrega", "dias_com_envio"]:
            df[c] = pd.NA
    df["n_arquivos"] = df["n_arquivos"].fillna(0).astype(int)
    df["volume_mb"] = df["volume_mb"].fillna(0.0).astype(float)
    df["dias_com_envio"] = df["dias_com_envio"].fillna(0).astype(int)
    df["primeira_entrega"] = pd.to_datetime(df["primeira_entrega"]).fillna(df["dt_apresentacao"])
    df["ultima_entrega"] = pd.to_datetime(df["ultima_entrega"]).fillna(df["dt_apresentacao"])

    com = base.comentarios
    df["n_comentarios"] = df["id"].map(com.groupby("id").size() if not com.empty else {}).fillna(0).astype(int)

    # Prazo: portal (data de apresentação atual) x 1ª entrega efetiva (1º arquivo)
    df["dias_vs_venc_portal"] = _dias(df["dt_apresentacao"], df["dt_vencimento"])
    df["dias_vs_venc_1a"] = _dias(df["primeira_entrega"], df["dt_vencimento"])
    df["prazo_portal"] = [_classe_prazo(d, v, hoje) for d, v in zip(df["dias_vs_venc_portal"], df["dt_vencimento"])]
    df["prazo_1a_entrega"] = [_classe_prazo(d, v, hoje) for d, v in zip(df["dias_vs_venc_1a"], df["dt_vencimento"])]

    # Tempos
    df["lead_atendimento_dias"] = _dias(df["primeira_entrega"], df["dt_criacao"])
    df["dias_analise_auditoria"] = _dias(df["dt_aceite"], df["dt_apresentacao"])
    aguardando = df["grupo_status"].eq("Em análise da auditoria")
    df["dias_aguardando_auditoria"] = (hoje.normalize() - df["dt_apresentacao"].dt.normalize()).dt.days.where(aguardando)
    pend = df["grupo_status"].eq("Pendente Energisa")
    df["dias_vencida_aberta"] = (hoje.normalize() - df["dt_vencimento"].dt.normalize()).dt.days.where(pend).clip(lower=0)
    return df


# ============================== INDICADORES ==============================
def kpis(df: pd.DataFrame, arquivos: pd.DataFrame) -> dict:
    total = len(df)
    entregues = df["primeira_entrega"].notna()
    no_prazo_1a = df["prazo_1a_entrega"].isin(["Antecipada", "No dia"]).sum()
    no_prazo_portal = df["prazo_portal"].isin(["Antecipada", "No dia"]).sum()
    n_entregues = int(entregues.sum())
    atrasos = df.loc[df["dias_vs_venc_1a"] > 0, "dias_vs_venc_1a"]
    return {
        "total": total,
        "concluidas": int(df["grupo_status"].eq("Concluída").sum()),
        "em_analise": int(df["grupo_status"].eq("Em análise da auditoria").sum()),
        "pendentes": int(df["grupo_status"].eq("Pendente Energisa").sum()),
        "devolvidas": int(df["teve_devolucao"].sum()),
        "entregues": n_entregues,
        "pct_conclusao": (df["grupo_status"].eq("Concluída").sum() / total * 100) if total else 0.0,
        "pct_prazo_1a": (no_prazo_1a / n_entregues * 100) if n_entregues else 0.0,
        "pct_prazo_portal": (no_prazo_portal / n_entregues * 100) if n_entregues else 0.0,
        "atraso_medio": float(atrasos.mean()) if len(atrasos) else 0.0,
        "arquivos": int(len(arquivos)),
        "volume_mb": float(arquivos["tamanho_mb"].sum()) if len(arquivos) else 0.0,
        "lead_medio": float(df["lead_atendimento_dias"].dropna().mean()) if df["lead_atendimento_dias"].notna().any() else 0.0,
        "analise_media": float(df["dias_analise_auditoria"].dropna().mean()) if df["dias_analise_auditoria"].notna().any() else 0.0,
    }


def contagem(df: pd.DataFrame, coluna: str, ordem: list[str] | None = None) -> pd.Series:
    s = df[coluna].fillna("—").value_counts()
    if ordem:
        s = s.reindex([o for o in ordem if o in s.index] + [i for i in s.index if i not in ordem])
    return s


def curva_acumulada(df: pd.DataFrame, hoje: date) -> pd.DataFrame:
    """Série diária acumulada: solicitadas, vencidas, entregues (1ª entrega) e aceitas."""
    eventos = {
        "Solicitadas": df["dt_criacao"],
        "Vencimentos": df["dt_vencimento"],
        "Entregues": df["primeira_entrega"],
        "Aceitas": df["dt_aceite"],
    }
    datas = pd.concat([s.dropna().dt.normalize() for s in eventos.values()])
    if datas.empty:
        return pd.DataFrame()
    fim = max(datas.max(), pd.Timestamp(hoje).normalize())
    idx = pd.date_range(datas.min(), fim, freq="D")
    out = pd.DataFrame(index=idx)
    for nome, s in eventos.items():
        out[nome] = s.dropna().dt.normalize().value_counts().reindex(idx, fill_value=0).cumsum()
    # Recorta o período sem movimento (ex.: solicitações abertas semanas antes do 1º vencimento)
    operacionais = pd.concat([df[c].dropna().dt.normalize() for c in ("dt_vencimento", "primeira_entrega", "dt_aceite")])
    if not operacionais.empty:
        inicio = max(datas.min(), operacionais.min() - pd.Timedelta(days=DIAS_ANTES_CURVA))
        out = out.loc[inicio:]
    return out


def envios_por_dia(arquivos: pd.DataFrame) -> pd.DataFrame:
    if arquivos.empty:
        return pd.DataFrame(columns=["dia", "arquivos", "solicitacoes", "volume_mb"])
    a = arquivos.assign(dia=arquivos["dt_envio"].dt.normalize())
    return (a.groupby("dia")
             .agg(arquivos=("arquivo", "count"), solicitacoes=("id", "nunique"), volume_mb=("tamanho_mb", "sum"))
             .reset_index())


def envios_por_pessoa(arquivos: pd.DataFrame) -> pd.DataFrame:
    if arquivos.empty:
        return pd.DataFrame(columns=["enviado_por", "arquivos", "solicitacoes", "volume_mb"])
    return (arquivos.groupby("enviado_por")
                    .agg(arquivos=("arquivo", "count"), solicitacoes=("id", "nunique"), volume_mb=("tamanho_mb", "sum"))
                    .sort_values("arquivos", ascending=False).reset_index())


def resumo_por(df: pd.DataFrame, coluna: str) -> pd.DataFrame:
    g = df.groupby(coluna)
    out = pd.DataFrame({
        "Solicitações": g.size(),
        "Concluídas": g["grupo_status"].apply(lambda s: (s == "Concluída").sum()),
        "Em análise": g["grupo_status"].apply(lambda s: (s == "Em análise da auditoria").sum()),
        "Pendentes": g["grupo_status"].apply(lambda s: (s == "Pendente Energisa").sum()),
        "Devolvidas": g["teve_devolucao"].sum(),
        "No prazo (1ª entrega)": g["prazo_1a_entrega"].apply(lambda s: s.isin(["Antecipada", "No dia"]).sum()),
        "Arquivos": g["n_arquivos"].sum(),
        "Volume (MB)": g["volume_mb"].sum().round(1),
    })
    out.index.name = {"area": "Área", "empresa": "Empresa"}.get(coluna, coluna)
    return out.sort_values("Solicitações", ascending=False)
