# =============================================================================
# report.py — Gera relatório HTML a partir do JSON de análise
# =============================================================================

from pathlib import Path
from datetime import datetime


CORES = {
    "CRITICO":        "#ff4444",
    "MEDIO":          "#ff8800",
    "BAIXO":          "#ffcc00",
    "SUGESTAO":       "#4488ff",
    "ADVERTENCIA":    "#aa44ff",
    "FALSO_POSITIVO": "#44aa44",
}

ICONES = {
    "CRITICO":        "🔴",
    "MEDIO":          "🟠",
    "BAIXO":          "🟡",
    "SUGESTAO":       "🔵",
    "ADVERTENCIA":    "🟣",
    "FALSO_POSITIVO": "🟢",
}


def _badge(sev: str) -> str:
    cor   = CORES.get(sev, "#888")
    icone = ICONES.get(sev, "⚪")
    return (
        f'<span style="background:{cor};color:#fff;padding:2px 8px;'
        f'border-radius:4px;font-size:12px;font-weight:bold;">'
        f'{icone} {sev}</span>'
    )


def _card(bug: dict) -> str:
    sev    = bug.get("severidade", "")
    borda  = CORES.get(sev, "#444")
    cor_bg = "#1a1a2e" if sev == "CRITICO" else "#0d1117"

    correcao_html = ""
    if bug.get("correcao"):
        correcao_html = f"""
        <div style="margin-top:10px;padding:8px;background:#0a2a0a;border-radius:4px;">
          <strong style="color:#44cc44;">✅ Correção sugerida:</strong>
          <pre style="color:#88ff88;margin:4px 0 0 0;white-space:pre-wrap;">{bug['correcao']}</pre>
        </div>"""

    return f"""
    <div style="border-left:4px solid {borda};background:{cor_bg};
                padding:16px;margin-bottom:16px;border-radius:4px;">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
        <span style="color:#ccc;font-family:monospace;">
          📄 {bug.get('arquivo','')} <span style="color:#888;">linha {bug.get('linha','')}</span>
        </span>
        {_badge(sev)}
      </div>
      <div style="color:#e0e0e0;margin-bottom:8px;">{bug.get('descricao','')}</div>
      <code style="color:#ff8888;font-size:13px;">{bug.get('tipo','')}</code>
      {correcao_html}
    </div>"""


def gerar_html(resultado: dict, output_path: str) -> None:
    modulo  = resultado.get("modulo", "?")
    resumo  = resultado.get("resumo", {})
    bugs    = resultado.get("bugs", [])
    usage   = resultado.get("_usage", {})
    agora   = datetime.now().strftime("%d/%m/%Y %H:%M")

    # Agrupa por severidade
    grupos: dict[str, list] = {}
    for bug in bugs:
        sev = bug.get("severidade", "OUTRO")
        grupos.setdefault(sev, []).append(bug)

    # Seções por severidade (ordem de prioridade)
    ordem = ["CRITICO", "MEDIO", "BAIXO", "SUGESTAO", "ADVERTENCIA", "FALSO_POSITIVO"]
    secoes_html = ""
    for sev in ordem:
        lista = grupos.get(sev, [])
        if not lista:
            continue
        cards = "".join(_card(b) for b in lista)
        secoes_html += f"""
        <h2 style="color:{CORES[sev]};margin-top:32px;">
          {ICONES[sev]} {sev} ({len(lista)})
        </h2>
        {cards}"""

    # Estatísticas de uso/custo
    cache_read    = usage.get("cache_read_tokens", 0)
    cache_created = usage.get("cache_creation_tokens", 0)
    input_tok     = usage.get("input_tokens", 0)
    output_tok    = usage.get("output_tokens", 0)

    # Estimativa de custo (Sonnet 4.6: $3/MTok input, $15/MTok output, cache read $0.30/MTok)
    custo_input   = (input_tok / 1_000_000) * 3.00
    custo_output  = (output_tok / 1_000_000) * 15.00
    custo_cache   = (cache_read / 1_000_000) * 0.30
    custo_total   = custo_input + custo_output + custo_cache

    html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <title>Análise CNPJ — {modulo}</title>
  <style>
    body      {{ background:#0d1117; color:#e0e0e0; font-family:sans-serif;
                max-width:960px; margin:0 auto; padding:32px 16px; }}
    pre       {{ background:#161b22; padding:12px; border-radius:4px;
                overflow-x:auto; font-size:13px; }}
    table     {{ border-collapse:collapse; width:100%; }}
    th,td     {{ border:1px solid #30363d; padding:8px 12px; text-align:left; }}
    th        {{ background:#161b22; }}
    .stat     {{ display:inline-block; padding:8px 16px; border-radius:6px;
                margin:4px; font-size:20px; font-weight:bold; }}
  </style>
</head>
<body>

<h1>🔍 Análise CNPJ Alfanumérico — <span style="color:#4488ff;">{modulo}</span></h1>
<p style="color:#888;">Gerado em {agora}</p>

<hr style="border-color:#30363d;">

<h2>📊 Dashboard</h2>
<div>
  <div class="stat" style="background:#ff4444;">{resumo.get('criticos',0)} Críticos</div>
  <div class="stat" style="background:#ff8800;">{resumo.get('medios',0)} Médios</div>
  <div class="stat" style="background:#ffcc00;color:#000;">{resumo.get('baixos',0)} Baixos</div>
  <div class="stat" style="background:#4488ff;">{resumo.get('sugestoes',0)} Sugestões</div>
  <div class="stat" style="background:#aa44ff;">{resumo.get('advertencias',0)} Advertências</div>
  <div class="stat" style="background:#44aa44;">{resumo.get('falsos_positivos',0)} Falsos+</div>
</div>

<h3 style="color:#888;margin-top:24px;">Uso de tokens nesta análise</h3>
<table>
  <tr><th>Métrica</th><th>Tokens</th><th>Custo (USD)</th></tr>
  <tr><td>Input (não cacheado)</td><td>{input_tok:,}</td><td>${custo_input:.4f}</td></tr>
  <tr><td>Output</td><td>{output_tok:,}</td><td>${custo_output:.4f}</td></tr>
  <tr><td>Cache read</td><td>{cache_read:,}</td><td>${custo_cache:.4f}</td></tr>
  <tr><td>Cache criado</td><td>{cache_created:,}</td><td>—</td></tr>
  <tr style="font-weight:bold;"><td>Total</td><td>{input_tok+output_tok:,}</td><td>${custo_total:.4f}</td></tr>
</table>

<hr style="border-color:#30363d;margin-top:32px;">

{secoes_html}

<hr style="border-color:#30363d;margin-top:32px;">
<p style="color:#555;font-size:12px;">
  Análise automatizada — revisar manualmente os itens CRÍTICOS antes do merge.
</p>
</body>
</html>"""

    Path(output_path).write_text(html, encoding="utf-8")
    print(f"      Relatório salvo: {output_path}")
