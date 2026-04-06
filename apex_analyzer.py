#!/usr/bin/env python3
# =============================================================================
# apex_analyzer.py — Detector de campos CNPJ numericos em arquivos APEX .sql
# Uso: python apex_analyzer.py <diretorio>
# =============================================================================

import argparse
import re
import sys
from pathlib import Path

REGEX_CNPJ_NUMERICO = re.compile(
    r'(CNPJ|CGC|COD_PART|CORRETORA|DESPACHANTE|COURIER|FACC|TRAN|TERC|CONS|CLI|FOR)[_]?[942]',
    re.IGNORECASE
)

REGEX_ALIAS = re.compile(r",p_alias=>'([^']+)'")


def extrair_alias(texto: str) -> str | None:
    m = REGEX_ALIAS.search(texto)
    return m.group(1) if m else None


def analisar_arquivo(path: Path) -> list[dict]:
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


def main():
    parser = argparse.ArgumentParser(
        description="Detecta campos CNPJ numericos em arquivos APEX .sql"
    )
    parser.add_argument(
        "diretorio",
        nargs="?",
        default=".",
        help="Diretorio a escanear (default: diretorio atual)",
    )
    args = parser.parse_args()

    raiz = Path(args.diretorio).resolve()
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

        print(f"🟣 [ADVERTENCIA] {rel}{alias_str}")

        # Deduplica por linha para nao repetir a mesma linha com varios matches
        linhas_exibidas = set()
        for item in matches:
            if item["linha"] in linhas_exibidas:
                continue
            linhas_exibidas.add(item["linha"])
            trecho = item["trecho"]
            if len(trecho) > 120:
                trecho = trecho[:117] + "..."
            print(f"  Linha {item['linha']:>5}: {trecho}")

        print(f"  >>> Este arquivo precisa ser alterado para suportar CNPJ alfanumerico.\n")

    print(sep)
    if total_com_advertencias == 0:
        print(f"  RESULTADO: Nenhuma advertencia encontrada em {total_analisados} arquivo(s).")
        print(sep)
        sys.exit(0)
    else:
        print(f"  RESULTADO: {total_com_advertencias} arquivo(s) com advertencia(s) | {total_analisados} analisado(s)")
        print(sep)
        print()
        sys.exit(1)


if __name__ == "__main__":
    main()
