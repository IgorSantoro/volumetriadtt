# Painel de Solicitações da Auditoria — Impostos Diretos

App Streamlit para acompanhamento gerencial da volumetria de solicitações da auditoria
(export do portal da Deloitte) e do atendimento realizado pela Energisa.

## Como rodar
```
pip install -r requirements.txt
streamlit run app.py
```
Arraste o(s) export(s) na barra lateral **ou** salve-os na pasta `bases/` (lida automaticamente).
Mantenha o nome original do export (`Requests - Energisa 3ITR - FY26 out 30 2026.xlsx`):
o app tira dele o **ciclo** (3ITR FY26) e a **data de extração** (30/10/2026), que é a data-base
para calcular atrasos e dias aguardando.

## Estrutura
| Arquivo | Responsabilidade |
|---|---|
| `leitura.py` | Lê o export, localiza o cabeçalho, descarta rodapé e explode **Arquivos inseridos** e **Comentários** em tabelas |
| `metricas.py` | Regras de negócio: grupo de status, prazo, lead time, KPIs, curvas e resumos |
| `componentes.py` | Cards, barras e gráficos em HTML/SVG (paleta navy/teal/laranja) |
| `exportacao.py` | Excel do acompanhamento (Solicitações, Resumo por área, Arquivos, Comentários) |
| `app.py` | Tela: filtros + abas Visão geral, Pendências, Solicitações, Atendimento, Comparativo |

## Regras usadas
- **Situação**: `Pedido Aceito` → Concluída · `Submetido pelo cliente` → Em análise da auditoria ·
  demais → Pendente Energisa. Novos status do portal: ajuste o dicionário `GRUPO_STATUS` em `metricas.py`.
- **Devolução**: "Motivo do reenvio" preenchido.
- **1ª entrega**: data do primeiro arquivo enviado (coluna "Arquivos inseridos").
  O portal regrava a "Data de apresentação" a cada reenvio, então o prazo do portal penaliza
  reenvios pedidos pela auditoria; o painel mostra os dois e usa a 1ª entrega como principal.
- **Prazo**: vencimento vale até 23h59 do dia → entrega no próprio dia = "No dia" (no prazo).
- **Empresa**: texto entre colchetes no início da solicitação (`[EMT] ...`); sem colchete → "Diversas".
- **Comparativo**: carregue exports de outros ciclos (1ITR, 2ITR, DFP) ou várias extrações do mesmo ciclo.
