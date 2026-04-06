#!/usr/bin/env python3
# =============================================================================
# apex_analyzer.py — Detector de campos CNPJ numericos em arquivos APEX .sql
# Uso: python apex_analyzer.py [diretorio] [--dir-cnpj DIR] [--output FILE.html]
# =============================================================================

import argparse
import html
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

REGEX_CNPJ_NUMERICO = re.compile(
    r'(CNPJ|CGC|COD_PART|CORRETORA|DESPACHANTE|COURIER|FACC|TRAN|TERC|CONS|CLI|FOR)[_]?[942]',
    re.IGNORECASE
)

REGEX_ALIAS = re.compile(r",p_alias=>'([^']+)'")


def extrair_alias(texto: str) -> Optional[str]:
    m = REGEX_ALIAS.search(texto)
    return m.group(1) if m else None


def analisar_arquivo(path: Path) -> list:
    try:
        texto = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []

    matches = []
    for num, linha in enumerate(texto.splitlines(), 1):
        linha_strip = linha.lstrip()
        if linha_strip.startswith("--"):
            continue
        for m in REGEX_CNPJ_NUMERICO.finditer(linha):
            matches.append({
                "linha": num,
                "trecho": linha.strip(),
                "match": m.group(0),
            })

    return matches


def gerar_html(resultados: list, raiz: Path, total_analisados: int) -> str:
    total_adv = len(resultados)
    agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    linhas_arquivos = []
    for arq in resultados:
        alias_str = f" <span class='alias'>(Pagina: {html.escape(arq['alias'])})</span>" if arq['alias'] else ""
        linhas_items = []
        for item in arq['items']:
            trecho = html.escape(item['trecho'])
            match_esc = html.escape(item['match'])
            trecho_hl = trecho.replace(match_esc, f"<mark>{match_esc}</mark>")
            linhas_items.append(
                f"<tr><td class='ln'>{item['linha']}</td><td class='code'>{trecho_hl}</td></tr>"
            )
        linhas_arquivos.append(f"""
        <div class="arquivo">
          <div class="arq-header">&#x1F7E3; {html.escape(arq['rel'])}{alias_str}</div>
          <table>{''.join(linhas_items)}</table>
          <div class="aviso">Este arquivo precisa ser alterado para suportar CNPJ alfanumerico.</div>
        </div>""")

    cor_resultado = "#c0392b" if total_adv > 0 else "#27ae60"
    texto_resultado = (
        f"{total_adv} arquivo(s) com advertencia(s) | {total_analisados} analisado(s)"
        if total_adv > 0
        else f"Nenhuma advertencia encontrada em {total_analisados} arquivo(s)."
    )

    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <title>APEX CNPJ Analyzer</title>
  <style>
    body {{ font-family: monospace; background: #1e1e1e; color: #d4d4d4; margin: 0; padding: 20px; }}
    h1 {{ color: #9b59b6; }}
    .meta {{ color: #888; margin-bottom: 20px; }}
    .arquivo {{ background: #252526; border-left: 4px solid #9b59b6; margin-bottom: 20px; padding: 12px 16px; border-radius: 4px; }}
    .arq-header {{ font-weight: bold; color: #ce9178; margin-bottom: 8px; }}
    .alias {{ color: #4ec9b0; font-weight: normal; }}
    table {{ border-collapse: collapse; width: 100%; }}
    td {{ padding: 2px 8px; vertical-align: top; }}
    td.ln {{ color: #888; text-align: right; min-width: 50px; user-select: none; }}
    td.code {{ color: #d4d4d4; white-space: pre-wrap; word-break: break-all; }}
    mark {{ background: #6b3a00; color: #ffa500; padding: 0 2px; border-radius: 2px; }}
    .aviso {{ color: #e67e22; font-style: italic; margin-top: 8px; font-size: 0.9em; }}
    .resultado {{ font-size: 1.1em; font-weight: bold; color: {cor_resultado}; margin-top: 20px; padding: 10px; background: #252526; border-radius: 4px; }}
  </style>
</head>
<body>
  <h1>APEX CNPJ Analyzer</h1>
  <div class="meta">Diretorio: {html.escape(str(raiz))} &nbsp;|&nbsp; Gerado em: {agora}</div>
  {''.join(linhas_arquivos)}
  <div class="resultado">RESULTADO: {texto_resultado}</div>
</body>
</html>"""


def main():
    parser = argparse.ArgumentParser(
        description="Detecta campos CNPJ numericos em arquivos APEX .sql"
    )
    parser.add_argument(
        "diretorio",
        nargs="?",
        default=None,
        help="Diretorio a escanear (default: diretorio atual)",
    )
    parser.add_argument(
        "--dir-cnpj",
        dest="dir_cnpj",
        default=None,
        help="Diretorio a escanear (alternativa ao argumento posicional)",
    )
    parser.add_argument(
        "--output",
        dest="output",
        default=None,
        help="Caminho para salvar o relatorio HTML (opcional)",
    )
    args = parser.parse_args()

    # --dir-cnpj tem prioridade; se nenhum for informado usa "."
    dir_escolhido = args.dir_cnpj or args.diretorio or "."
    raiz = Path(dir_escolhido).resolve()
    if not raiz.exists():
        print(f"ERRO: Diretorio nao encontrado: {raiz}")
        sys.exit(2)

    sep = "=" * 60
    print(f"\n{sep}")
    print(f"  APEX CNPJ Analyzer")
    print(f"  Diretorio: {raiz}")
    print(f"{sep}\n")

    arquivos_sql = sorted(raiz.rglob("*.sql"))
    total_analisados = len(arquivos_sql)
    total_com_advertencias = 0
    resultados_html = []

    for path in arquivos_sql:
        matches = analisar_arquivo(path)
        if not matches:
            continue

        total_com_advertencias += 1

        try:
            texto = path.read_text(encoding="utf-8", errors="replace")
            alias = extrair_alias(texto)
        except OSError:
            alias = None

        rel = path.relative_to(raiz)
        alias_str = f" (Pagina: {alias})" if alias else ""

        print(f"[ADVERTENCIA] {rel}{alias_str}")

        items_dedup = []
        linhas_exibidas = set()
        for item in matches:
            if item["linha"] in linhas_exibidas:
                continue
            linhas_exibidas.add(item["linha"])
            trecho = item["trecho"]
            if len(trecho) > 120:
                trecho = trecho[:117] + "..."
            print(f"  Linha {item['linha']:>5}: {trecho}")
            items_dedup.append({"linha": item["linha"], "trecho": trecho, "match": item["match"]})

        print(f"  >>> Este arquivo precisa ser alterado para suportar CNPJ alfanumerico.\n")

        resultados_html.append({"rel": str(rel), "alias": alias, "items": items_dedup})

    print(sep)
    if total_com_advertencias == 0:
        print(f"  RESULTADO: Nenhuma advertencia encontrada em {total_analisados} arquivo(s).")
        print(sep)
        code = 0
    else:
        print(f"  RESULTADO: {total_com_advertencias} arquivo(s) com advertencia(s) | {total_analisados} analisado(s)")
        print(sep)
        print()
        code = 1

    if args.output:
        saida = Path(args.output)
        saida.parent.mkdir(parents=True, exist_ok=True)
        saida.write_text(
            gerar_html(resultados_html, raiz, total_analisados),
            encoding="utf-8"
        )
        print(f"  Relatorio HTML salvo em: {saida}")

    sys.exit(code)


if __name__ == "__main__":
    main()
