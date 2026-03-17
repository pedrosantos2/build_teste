# =============================================================================
# report.py — Gera relatorio HTML sem estilos inline (compativel com CSP Jenkins)
# Usa apenas classes CSS definidas no <head>
# =============================================================================

from pathlib import Path
from datetime import datetime

CORES = {
    "CRITICO":        "#ff4444",
    "MEDIO":          "#ff8800",
    "BAIXO":          "#e6b800",
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

ORDEM = ["CRITICO", "MEDIO", "BAIXO", "SUGESTAO", "ADVERTENCIA", "FALSO_POSITIVO"]


def _card(bug: dict) -> str:
    sev      = bug.get("severidade", "")
    arquivo  = bug.get("arquivo", "")
    linha    = bug.get("linha", "")
    tipo     = bug.get("tipo", "")
    descricao= bug.get("descricao", "")
    correcao = bug.get("correcao", "")
    icone    = ICONES.get(sev, "")

    correcao_html = ""
    if correcao:
        correcao_html = f"""
        <div class="correcao">
          <strong>Correcao sugerida:</strong>
          <pre>{correcao}</pre>
        </div>"""

    return f"""
    <div class="card card-{sev.lower()}">
      <div class="card-header">
        <span class="arquivo">📄 {arquivo} — linha {linha}</span>
        <span class="badge badge-{sev.lower()}">{icone} {sev}</span>
      </div>
      <div class="descricao">{descricao}</div>
      <code class="tipo">{tipo}</code>
      {correcao_html}
    </div>"""


def gerar_html(resultado: dict, output_path: str) -> None:
    modulo  = resultado.get("modulo", "?")
    resumo  = resultado.get("resumo", {})
    bugs    = resultado.get("bugs", [])
    usage   = resultado.get("_usage", {})
    agora   = datetime.now().strftime("%d/%m/%Y %H:%M")

    grupos = {}
    for bug in bugs:
        sev = bug.get("severidade", "OUTRO")
        grupos.setdefault(sev, []).append(bug)

    # Secoes
    if not bugs:
        secoes_html = """
        <div class="sucesso">
          <div class="sucesso-icone">✅</div>
          <h2>Nenhum bug encontrado</h2>
          <p>A analise nao encontrou problemas criticos neste modulo.</p>
        </div>"""
    else:
        secoes_html = ""
        for sev in ORDEM:
            lista = grupos.get(sev, [])
            if not lista:
                continue
            cards = "".join(_card(b) for b in lista)
            icone = ICONES.get(sev, "")
            secoes_html += f"""
            <h2 class="secao-titulo secao-{sev.lower()}">{icone} {sev} ({len(lista)})</h2>
            {cards}"""

    # Tokens e custo
    cache_read    = usage.get("cache_read_tokens", 0)
    cache_created = usage.get("cache_creation_tokens", 0)
    input_tok     = usage.get("input_tokens", 0)
    output_tok    = usage.get("output_tokens", 0)
    custo_input   = (input_tok  / 1_000_000) * 3.00
    custo_output  = (output_tok / 1_000_000) * 15.00
    custo_cache   = (cache_read / 1_000_000) * 0.30
    custo_total   = custo_input + custo_output + custo_cache

    html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <title>Analise CNPJ - {modulo}</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ background: #0d1117; color: #e0e0e0; font-family: Arial, sans-serif; max-width: 960px; margin: 0 auto; padding: 32px 16px; }}
    h1 {{ color: #4488ff; margin-bottom: 4px; }}
    h2 {{ margin: 24px 0 12px 0; }}
    hr {{ border: none; border-top: 1px solid #30363d; margin: 24px 0; }}
    p {{ color: #888; }}
    pre {{ background: #161b22; padding: 12px; border-radius: 4px; overflow-x: auto; font-size: 13px; white-space: pre-wrap; word-break: break-word; }}
    code {{ color: #ff8888; font-size: 13px; }}
    table {{ border-collapse: collapse; width: 100%; margin-top: 12px; }}
    th, td {{ border: 1px solid #30363d; padding: 8px 12px; text-align: left; }}
    th {{ background: #161b22; }}
    .subtitulo {{ color: #888; margin-bottom: 24px; }}

    /* Dashboard */
    .dashboard {{ display: flex; flex-wrap: wrap; gap: 8px; margin: 16px 0; }}
    .stat {{ padding: 10px 18px; border-radius: 6px; font-size: 18px; font-weight: bold; color: #fff; }}
    .stat-critico {{ background: #ff4444; }}
    .stat-medio {{ background: #ff8800; }}
    .stat-baixo {{ background: #e6b800; color: #000; }}
    .stat-sugestao {{ background: #4488ff; }}
    .stat-advertencia {{ background: #aa44ff; }}
    .stat-falso {{ background: #44aa44; }}

    /* Cards */
    .card {{ border-radius: 4px; padding: 16px; margin-bottom: 16px; border-left: 4px solid #444; }}
    .card-critico {{ background: #1a0a0a; border-left-color: #ff4444; }}
    .card-medio {{ background: #1a110a; border-left-color: #ff8800; }}
    .card-baixo {{ background: #1a1a0a; border-left-color: #e6b800; }}
    .card-sugestao {{ background: #0a0f1a; border-left-color: #4488ff; }}
    .card-advertencia {{ background: #110a1a; border-left-color: #aa44ff; }}
    .card-falso_positivo {{ background: #0a1a0a; border-left-color: #44aa44; }}
    .card-header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; flex-wrap: wrap; gap: 8px; }}
    .arquivo {{ font-family: monospace; color: #ccc; }}
    .descricao {{ color: #e0e0e0; margin: 8px 0; }}
    .correcao {{ margin-top: 10px; padding: 10px; background: #0a1a0a; border-radius: 4px; }}
    .correcao strong {{ color: #44cc44; }}

    /* Badges */
    .badge {{ padding: 2px 10px; border-radius: 4px; font-size: 12px; font-weight: bold; color: #fff; }}
    .badge-critico {{ background: #ff4444; }}
    .badge-medio {{ background: #ff8800; }}
    .badge-baixo {{ background: #e6b800; color: #000; }}
    .badge-sugestao {{ background: #4488ff; }}
    .badge-advertencia {{ background: #aa44ff; }}
    .badge-falso_positivo {{ background: #44aa44; }}

    /* Titulos de secao */
    .secao-titulo {{ margin: 32px 0 12px 0; }}
    .secao-critico {{ color: #ff4444; }}
    .secao-medio {{ color: #ff8800; }}
    .secao-baixo {{ color: #e6b800; }}
    .secao-sugestao {{ color: #4488ff; }}
    .secao-advertencia {{ color: #aa44ff; }}
    .secao-falso_positivo {{ color: #44aa44; }}

    /* Sucesso */
    .sucesso {{ text-align: center; padding: 60px; background: #0a1a0a; border-radius: 8px; border: 2px solid #44aa44; margin-top: 32px; }}
    .sucesso-icone {{ font-size: 64px; margin-bottom: 16px; }}
    .sucesso h2 {{ color: #44cc44; margin-bottom: 8px; }}
    .rodape {{ color: #555; font-size: 12px; margin-top: 32px; }}
  </style>
</head>
<body>

<h1>Analise CNPJ Alfanumerico - {modulo}</h1>
<p class="subtitulo">Gerado em {agora}</p>

<hr>

<h2>Dashboard</h2>
<div class="dashboard">
  <div class="stat stat-critico">{resumo.get('criticos', 0)} Criticos</div>
  <div class="stat stat-medio">{resumo.get('medios', 0)} Medios</div>
  <div class="stat stat-baixo">{resumo.get('baixos', 0)} Baixos</div>
  <div class="stat stat-sugestao">{resumo.get('sugestoes', 0)} Sugestoes</div>
  <div class="stat stat-advertencia">{resumo.get('advertencias', 0)} Advertencias</div>
  <div class="stat stat-falso">{resumo.get('falsos_positivos', 0)} Falsos+</div>
</div>

<h3>Uso de tokens nesta analise</h3>
<table>
  <tr><th>Metrica</th><th>Tokens</th><th>Custo (USD)</th></tr>
  <tr><td>Input (nao cacheado)</td><td>{input_tok:,}</td><td>${custo_input:.4f}</td></tr>
  <tr><td>Output</td><td>{output_tok:,}</td><td>${custo_output:.4f}</td></tr>
  <tr><td>Cache read</td><td>{cache_read:,}</td><td>${custo_cache:.4f}</td></tr>
  <tr><td>Cache criado</td><td>{cache_created:,}</td><td>-</td></tr>
  <tr><td><strong>Total</strong></td><td><strong>{input_tok + output_tok:,}</strong></td><td><strong>${custo_total:.4f}</strong></td></tr>
</table>

<hr>

{secoes_html}

<hr>
<p class="rodape">Analise automatizada - revisar manualmente os itens CRITICOS antes do merge.</p>
</body>
</html>"""

    Path(output_path).write_text(html, encoding="utf-8")
    print(f"      Relatorio salvo: {output_path}")