"""Exportação do acompanhamento para Excel (openpyxl), com layout padrão navy."""
from __future__ import annotations

from io import BytesIO

import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

# ============================== CONSTANTES ==============================
FILL_CAB = PatternFill("solid", fgColor="1B2A4A")
FONTE_CAB = Font(name="Arial", bold=True, color="FFFFFF", size=10)
FONTE = Font(name="Arial", size=10)
LARG_MAX = 60

COLUNAS_SOLIC = {
    "ciclo": "Ciclo", "id": "ID", "area": "Área", "empresa": "Empresa", "titulo": "Solicitação",
    "status": "Status portal", "grupo_status": "Situação", "teve_devolucao": "Teve devolução",
    "dt_criacao": "Criada em", "dt_vencimento": "Vencimento", "primeira_entrega": "1ª entrega",
    "dt_apresentacao": "Apresentação (portal)", "dt_aceite": "Aceite",
    "dias_vs_venc_1a": "Dias vs venc. (1ª entrega)", "prazo_1a_entrega": "Prazo (1ª entrega)",
    "dias_vs_venc_portal": "Dias vs venc. (portal)", "prazo_portal": "Prazo (portal)",
    "lead_atendimento_dias": "Lead time atendimento (d)", "dias_analise_auditoria": "Análise auditoria (d)",
    "n_arquivos": "Arquivos", "volume_mb": "Volume (MB)", "n_comentarios": "Comentários",
}


def _aba(wb: Workbook, nome: str, df: pd.DataFrame) -> None:
    ws = wb.create_sheet(nome)
    ws.append(list(df.columns))
    for linha in df.itertuples(index=False):
        ws.append([None if (not isinstance(v, str) and pd.isna(v)) else
                   (v.to_pydatetime() if isinstance(v, pd.Timestamp) else v) for v in linha])
    for c in ws[1]:
        c.fill, c.font = FILL_CAB, FONTE_CAB
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    ws.row_dimensions[1].height = 30
    for i, col in enumerate(df.columns, start=1):
        letra = get_column_letter(i)
        serie = df[col]
        if pd.api.types.is_datetime64_any_dtype(serie):
            fmt, larg = "dd/mm/yyyy hh:mm", 17
        elif pd.api.types.is_float_dtype(serie):
            fmt, larg = "#,##0.0", 12
        else:
            fmt = None
            larg = min(max([len(str(col))] + [len(str(v)) for v in serie.head(200)]) + 2, LARG_MAX)
        ws.column_dimensions[letra].width = larg
        for cel in ws[letra][1:]:
            cel.font = FONTE
            if fmt:
                cel.number_format = fmt
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions


def gerar_excel(solic: pd.DataFrame, arquivos: pd.DataFrame, comentarios: pd.DataFrame,
                resumo_area: pd.DataFrame) -> bytes:
    wb = Workbook()
    wb.remove(wb.active)
    s = solic[[c for c in COLUNAS_SOLIC if c in solic.columns]].rename(columns=COLUNAS_SOLIC)
    s["Teve devolução"] = s["Teve devolução"].map({True: "Sim", False: "Não"})
    _aba(wb, "Solicitações", s)
    _aba(wb, "Resumo por área", resumo_area.reset_index())
    _aba(wb, "Arquivos enviados", arquivos.rename(columns={
        "id": "ID", "arquivo": "Arquivo", "tamanho_mb": "Tamanho (MB)", "dt_envio": "Enviado em", "enviado_por": "Enviado por"}))
    _aba(wb, "Comentários auditoria", comentarios.rename(columns={
        "id": "ID", "comentario": "Comentário", "dt_comentario": "Data", "autor": "Autor"}))
    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()
