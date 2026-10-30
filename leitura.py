"""Leitura e normalização do export de solicitações do portal da auditoria (Deloitte).

Responsabilidade única: transformar o .xlsx exportado em três tabelas limpas
(solicitações, arquivos enviados e comentários) + metadados do ciclo.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

import pandas as pd

# ============================== CONSTANTES ==============================
# Cabeçalho do portal (apenas a 1ª linha de cada célula) -> nome interno
MAPA_COLUNAS = {
    "ID": "id",
    "Tags": "tags",
    "Categoria": "categoria",
    "Área": "area",
    "Solicitação": "solicitacao",
    "Anotações": "anotacoes",
    "Status": "status",
    "Motivo do reenvio": "motivo_reenvio",
    "Cálculo da frequência de reenvio": "freq_reenvio",
    "Data de apresentação do cliente": "dt_apresentacao",
    "Solicitação Data aceita": "dt_aceite",
    "Data de vencimento": "dt_vencimento",
    "Mudanças de data de vencimento": "mudancas_venc",
    "Dias remanescentes": "dias_txt",
    "Vencido há dias": "vencido_txt",
    "Endereço de e-mail do contato do cliente": "contatos_cliente",
    "Endereço de e-mail do responsável pelo cliente": "resp_cliente",
    "Endereço de e-mail do contato da Deloitte": "contatos_auditoria",
    "Endereço de e-mail do Responsável Deloitte": "resp_auditoria",
    "Criado por": "criado_por",
    "Arquivos inseridos": "arquivos",
    "Comentários": "comentarios",
    "Segurança de Solicitação de Itens": "seguranca",
    "Arquivos determinados como contendo PHI": "phi",
    "Data de criação": "dt_criacao",
    "ID's vínculados": "ids_vinculados",
}
COLUNAS_DATA = ["dt_apresentacao", "dt_aceite", "dt_vencimento", "dt_criacao"]
COLUNAS_OBRIGATORIAS = ["id", "solicitacao", "status", "dt_vencimento"]

MESES_PT = {"jan": 1, "fev": 2, "mar": 3, "abr": 4, "mai": 5, "jun": 6,
            "jul": 7, "ago": 8, "set": 9, "out": 10, "nov": 11, "dez": 12}

RE_ARQUIVO = re.compile(
    r'"(?P<nome>[^"]+)",\s*(?P<tam>[\d\.,]+)\s*(?P<un>GB|MB|KB|B)\s+em\s+'
    r'(?P<data>\d{2}/\d{2}/\d{4}\s+\d{2}:\d{2})\s+CT\s+por\s+(?P<por>[^;\n]+)',
    re.IGNORECASE,
)
RE_COMENTARIO = re.compile(
    r'"(?P<texto>.*?)"\s+em\s+(?P<data>\d{2}/\d{2}/\d{4}\s+\d{2}:\d{2})\s+CT\s+Por\s+(?P<por>[^\n]+)',
    re.DOTALL | re.IGNORECASE,
)
RE_CICLO = re.compile(r"Energisa\s+(?P<ciclo>.+?)\s+-\s+FY\s?(?P<fy>\d{2,4})", re.IGNORECASE)
RE_DATA_ARQ = re.compile(r"\b(?P<mes>jan|fev|mar|abr|mai|jun|jul|ago|set|out|nov|dez)\s+(?P<dia>\d{1,2})\s+(?P<ano>\d{4})", re.IGNORECASE)
FATOR_MB = {"B": 1 / 1024 ** 2, "KB": 1 / 1024, "MB": 1.0, "GB": 1024.0}


# ============================== ESTRUTURA ==============================
@dataclass
class BaseAuditoria:
    nome_arquivo: str
    ciclo: str
    data_extracao: date
    solicitacoes: pd.DataFrame
    arquivos: pd.DataFrame = field(default_factory=pd.DataFrame)
    comentarios: pd.DataFrame = field(default_factory=pd.DataFrame)


class ErroLeitura(Exception):
    """Arquivo não reconhecido como export de solicitações."""


# ============================== AUXILIARES ==============================
def _primeira_linha(txt) -> str:
    return str(txt).split("\n")[0].strip() if txt is not None else ""


def _sem_acento(txt: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", txt) if not unicodedata.combining(c)).lower()


def _tamanho_mb(valor: str, unidade: str) -> float:
    numero = float(valor.replace(".", "").replace(",", "."))
    return numero * FATOR_MB.get(unidade.upper(), 1.0)


def metadados_do_nome(nome: str) -> tuple[str, date | None]:
    """'Requests_-_Energisa_3ITR_-_FY26_out_30_2026.xlsx' -> ('3ITR FY26', 2026-10-30)."""
    limpo = Path(nome).stem.replace("_", " ")
    m = RE_CICLO.search(limpo)
    ciclo = f"{m['ciclo'].strip()} FY{m['fy'][-2:]}" if m else Path(nome).stem
    d = RE_DATA_ARQ.search(limpo)
    data = date(int(d["ano"]), MESES_PT[d["mes"].lower()], int(d["dia"])) if d else None
    return ciclo, data


def _localizar_cabecalho(bruto: pd.DataFrame) -> int:
    for i, valor in enumerate(bruto.iloc[:30, 0].tolist()):
        if _primeira_linha(valor) == "ID":
            return i
    raise ErroLeitura("Não encontrei a linha de cabeçalho com 'ID' na primeira coluna.")


def _explodir_arquivos(df: pd.DataFrame) -> pd.DataFrame:
    linhas = []
    for _, r in df.iterrows():
        for m in RE_ARQUIVO.finditer(str(r.get("arquivos") or "")):
            linhas.append({
                "id": r["id"],
                "arquivo": m["nome"].strip(),
                "tamanho_mb": _tamanho_mb(m["tam"], m["un"]),
                "dt_envio": datetime.strptime(m["data"], "%d/%m/%Y %H:%M"),
                "enviado_por": m["por"].strip(),
            })
    cols = ["id", "arquivo", "tamanho_mb", "dt_envio", "enviado_por"]
    return pd.DataFrame(linhas, columns=cols)


def _explodir_comentarios(df: pd.DataFrame) -> pd.DataFrame:
    linhas = []
    for _, r in df.iterrows():
        for m in RE_COMENTARIO.finditer(str(r.get("comentarios") or "")):
            linhas.append({
                "id": r["id"],
                "comentario": m["texto"].strip(),
                "dt_comentario": datetime.strptime(m["data"], "%d/%m/%Y %H:%M"),
                "autor": m["por"].strip(),
            })
    return pd.DataFrame(linhas, columns=["id", "comentario", "dt_comentario", "autor"])


# ============================== API ==============================
def ler_export(origem, nome_arquivo: str | None = None) -> BaseAuditoria:
    """Lê o export (caminho ou arquivo em memória) e devolve a base normalizada."""
    nome = nome_arquivo or getattr(origem, "name", None) or str(origem)
    try:
        bruto = pd.read_excel(origem, header=None, dtype=object)
    except Exception as exc:  # noqa: BLE001
        raise ErroLeitura(f"Não foi possível abrir '{nome}': {exc}") from exc

    lin = _localizar_cabecalho(bruto)
    cabecalho = [_primeira_linha(c) for c in bruto.iloc[lin].tolist()]
    df = bruto.iloc[lin + 1:].copy()
    df.columns = [MAPA_COLUNAS.get(c, _sem_acento(c) or f"col_{i}") for i, c in enumerate(cabecalho)]

    faltantes = [c for c in COLUNAS_OBRIGATORIAS if c not in df.columns]
    if faltantes:
        raise ErroLeitura(f"Colunas obrigatórias ausentes: {', '.join(faltantes)}")

    # Mantém só linhas de solicitação (descarta vazios e rodapé "© Deloitte...")
    df["id"] = df["id"].astype(str).str.strip()
    df = df[df["id"].str.fullmatch(r"\d+") & df["solicitacao"].notna()].copy()
    df["id"] = df["id"].str.zfill(4)

    for c in COLUNAS_DATA:
        if c in df.columns:
            df[c] = pd.to_datetime(df[c], errors="coerce")
    for c in MAPA_COLUNAS.values():
        if c not in df.columns:
            df[c] = None

    ciclo, data_nome = metadados_do_nome(nome)
    data_extracao = data_nome or date.today()

    return BaseAuditoria(
        nome_arquivo=Path(nome).name,
        ciclo=ciclo,
        data_extracao=data_extracao,
        solicitacoes=df.reset_index(drop=True),
        arquivos=_explodir_arquivos(df),
        comentarios=_explodir_comentarios(df),
    )
