#!/usr/bin/env python3
# =============================================================================
# analise.py — Entrypoint principal
# Uso: python analise.py [modulo] [--workspace path] [--dry-run] [--json-only]
#
# Fluxo:
#   1. git diff              -> lista arquivos modificados entre branches
#   2. grep_engine.py              -> analise estatica completa (sem API, gratis)
#   3. Se houver erros:
#      Claude API            -> confirma falsos positivos + sugere correcoes
#   4. Relatorio HTML + JSON
#   5. exit 1 se criticos confirmados, exit 0 se limpo
# =============================================================================

import argparse
import json
import sys
import subprocess
import os
from pathlib import Path

import grep_engine as grep_engine
from grep_engine     import (
    _resolver_branch_cnpj,
    _resolver_branch_principal,
)
from claude_analyzer import analisar
from report          import gerar_html


DEFAULT_SKILL     = Path(__file__).parent / "analise-cnpj.md"
DEFAULT_EXEMPLOS  = Path(__file__).parent / "exemplos"
DEFAULT_WORKSPACE = Path("/Systextil/workspace")

ICONES = {
    "CRITICO":     "🔴",
    "MEDIO":       "🟠",
    "BAIXO":       "🟡",
    "SUGESTAO":    "🔵",
    "ADVERTENCIA": "🟣",
    "FALSO_POSITIVO": "🟢",
}
ORDEM_SEVERIDADE = ["CRITICO", "MEDIO", "BAIXO", "SUGESTAO", "ADVERTENCIA"]


def parse_args():
    p = argparse.ArgumentParser(description="Analise CNPJ alfanumerico — Systextil")
    p.add_argument("modulo", nargs="?", default=".",
                   help="Nome do modulo ou '.' para diretorio atual")
    p.add_argument("--skill",     "-s", default=str(DEFAULT_SKILL))
    p.add_argument("--exemplos",  "-e", default=str(DEFAULT_EXEMPLOS))
    p.add_argument("--workspace", "-w", default=str(DEFAULT_WORKSPACE))
    p.add_argument("--dry-run",         action="store_true",
                   help="Roda so analise estatica, sem chamar API")
    p.add_argument("--json-only",       action="store_true")
    return p.parse_args()


# ---------------------------------------------------------------------------
# Git helpers
# ---------------------------------------------------------------------------

def diff_arquivos(repo_path: str, branch_main: str, branch_cnpj: str,
                  extensoes: List[str]) -> List[str]:
    result = subprocess.run(
        ["git", "diff", f"{branch_main}..{branch_cnpj}", "--name-only"],
        cwd=repo_path, capture_output=True, text=True,
    )
    todos = result.stdout.splitlines()
    return [f for f in todos if any(f.endswith(e) for e in extensoes)]


def checkout_temp(repo_path: str, branch: str, arquivo: str) -> Optional[Path]:
    """Extrai arquivo do branch para temp — grep_engine precisa de path real no disco."""
    import tempfile
    result = subprocess.run(
        ["git", "show", f"{branch}:{arquivo}"],
        cwd=repo_path, capture_output=True
    )
    if result.returncode != 0:
        return None
    suffix = Path(arquivo).suffix or ".java"
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix, mode="wb")
    tmp.write(result.stdout)
    tmp.close()
    return Path(tmp.name)


# ---------------------------------------------------------------------------
# Analise estatica com grep_engine (sem API)
# ---------------------------------------------------------------------------

def rodar_grep_engine(repo_path: str, branch_cnpj: str,
                arquivos: List[str]) -> List[Dict[str, Any]]:
    resultados = []
    for arquivo in arquivos:
        if not arquivo.endswith(".java"):
            continue
        if grep_engine.deve_ignorar(arquivo):
            continue

        tmp = checkout_temp(repo_path, branch_cnpj, arquivo)
        if not tmp:
            continue
        try:
            r = grep_engine.analisar_arquivo(str(tmp))
            if r:
                r["arquivo_original"] = arquivo
                r["arquivo"]          = Path(arquivo).name
                resultados.append(r)
        finally:
            os.unlink(tmp)

    return resultados


def imprimir_grep_engine(resultados: List[Dict[str, Any]]) -> int:
    """Imprime resultados do grep_engine e retorna total de erros criticos."""
    total_erros = 0
    for r in resultados:
        erros  = r.get("erros", [])
        avisos = r.get("avisos", [])
        total_erros += len(erros)

        if not erros and not avisos:
            continue

        arquivo   = r.get("arquivo_original", r.get("arquivo", ""))
        categoria = r.get("categoria", "?")
        icone     = {"ERRO": "🔴", "ATENCAO": "🟠", "VERIFICADO": "🟢"}.get(categoria, "⬜")

        print(f"\n  {icone} [{categoria}] {arquivo}")
        for e in erros:
            print(f"     🔴 Linha {e.get('linha','?')} [{e.get('bug','')}]: {e.get('mensagem','')}")
        for a in avisos:
            print(f"     🟠 Linha {a.get('linha','?')} [{a.get('bug','')}]: {a.get('mensagem','')}")

    return total_erros


def converter_para_hits(resultados: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Converte erros do grep_engine para o formato que o claude_analyzer espera."""
    hits = []
    for r in resultados:
        arquivo = r.get("arquivo_original", r.get("arquivo", ""))
        for item in r.get("erros", []) + r.get("avisos", []):
            hits.append({
                "arquivo":       arquivo,
                "linha":         item.get("linha", 0),
                "tipo":          item.get("bug", ""),
                "sev_estimada":  "CRITICO" if item.get("tipo") == "ERRO" else "MEDIO",
                "codigo":        "",
                "contexto":      item.get("mensagem", ""),
                "match":         item.get("mensagem", "")[:80],
                "pre_existente": False,
            })
    return hits


# ---------------------------------------------------------------------------
# Console output — bugs confirmados pelo Claude
# ---------------------------------------------------------------------------

def imprimir_bugs_claude(bugs: List[Dict[str, Any]]) -> None:
    bugs_reais = [b for b in bugs if b.get("severidade") != "FALSO_POSITIVO"]
    if not bugs_reais:
        return

    print("\n" + "-" * 60)
    print("  CLAUDE — falsos positivos removidos, correcoes sugeridas")
    print("-" * 60)

    for sev in ORDEM_SEVERIDADE:
        grupo = [b for b in bugs_reais if b.get("severidade") == sev]
        if not grupo:
            continue
        print(f"\n{ICONES.get(sev,'⚪')} {sev} ({len(grupo)})")
        for bug in grupo:
            print(f"  {'-'*56}")
            print(f"  📄 {bug.get('arquivo','')} : linha {bug.get('linha','')}")
            print(f"  Tipo:     {bug.get('tipo','')}")
            print(f"  Detalhe:  {bug.get('descricao','')}")
            if bug.get("correcao"):
                print(f"  Correcao: {bug.get('correcao','')}")
    print("\n" + "-" * 60)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    args   = parse_args()
    modulo = args.modulo

    if modulo == ".":
        repo_path = str(Path.cwd())
        modulo    = Path.cwd().name
    else:
        repo_path = str(Path(args.workspace) / modulo)

    print(f"\n{'='*60}")
    print(f"  Analise CNPJ — modulo: {modulo}")
    print(f"{'='*60}")

    try:
        branch_cnpj = _resolver_branch_cnpj(repo_path)
        branch_main = _resolver_branch_principal(repo_path)
    except RuntimeError as e:
        print(f"ERRO: {e}")
        sys.exit(1)

    print(f"  Branch principal : {branch_main}")
    print(f"  Branch CNPJ      : {branch_cnpj}")

    # ------------------------------------------------------------------
    # PASSO 1 — Arquivos modificados
    # ------------------------------------------------------------------
    print(f"\n[1/3] Coletando arquivos modificados...")
    arquivos = diff_arquivos(
        repo_path, branch_main, branch_cnpj,
        [".java", ".fj", ".fx", ".jsp"]
    )
    print(f"      {len(arquivos)} arquivo(s)")
    for a in arquivos:
        print(f"        + {a}")

    if not arquivos:
        print("\n✅ Nenhum arquivo modificado. Nada a analisar.")
        sys.exit(0)

    # ------------------------------------------------------------------
    # PASSO 2 — Analise estatica local com grep_engine (sem API, gratis)
    # ------------------------------------------------------------------
    print(f"\n[2/3] Analise estatica (grep_engine)...")
    resultados = rodar_grep_engine(repo_path, branch_cnpj, arquivos)
    total_erros  = sum(len(r.get("erros",  [])) for r in resultados)
    total_avisos = sum(len(r.get("avisos", [])) for r in resultados)
    print(f"      {total_erros} erros criticos | {total_avisos} avisos")

    imprimir_grep_engine(resultados)

    # ------------------------------------------------------------------
    # PASSO 3 — Claude so e chamado se houver erros
    # ------------------------------------------------------------------
    resultado_claude = {"modulo": modulo, "bugs": [], "resumo": {}}

    if not total_erros and not total_avisos:
        print(f"\n[3/3] Nenhum erro encontrado — API nao sera chamada.")

    elif args.dry_run:
        print(f"\n[3/3] --dry-run: pulando chamada a API.")

    else:
        hits = converter_para_hits(resultados)
        print(f"\n[3/3] Enviando {len(hits)} item(ns) ao Claude para confirmacao...")
        resultado_claude = analisar(
            modulo       = modulo,
            hits         = hits,
            skill_path   = args.skill,
            exemplos_dir = args.exemplos,
        )
        uso = resultado_claude.get("_usage", {})
        print(f"      Tokens: {uso.get('input_tokens',0):,} input "
              f"| {uso.get('output_tokens',0):,} output "
              f"| {uso.get('cache_read_tokens',0):,} cache")

        imprimir_bugs_claude(resultado_claude.get("bugs", []))

    # ------------------------------------------------------------------
    # Salva resultados
    # ------------------------------------------------------------------
    base = Path(repo_path)

    json_path = base / f"analise-cnpj-{modulo}.json"
    json_path.write_text(
        json.dumps({"modulo": modulo, "grep_engine": resultados,
                    "claude": resultado_claude}, ensure_ascii=False, indent=2)
    )
    print(f"\n      JSON: {json_path}")

    if not args.json_only and resultado_claude.get("bugs"):
        html_path = base / f"analise-cnpj-{modulo}.html"
        gerar_html(resultado_claude, str(html_path))

    # ------------------------------------------------------------------
    # Resumo e exit code
    # ------------------------------------------------------------------
    r = resultado_claude.get("resumo", {})
    criticos_confirmados = r.get("criticos", 0)

    print(f"\n{'='*60}")
    print(f"  RESULTADO — {modulo}")
    print(f"  grep_engine: {total_erros} erros | {total_avisos} avisos")
    if not args.dry_run:
        print(f"  Claude : {criticos_confirmados} criticos confirmados "
              f"| {r.get('falsos_positivos',0)} falsos positivos removidos")
    print(f"{'='*60}\n")

    # Se dry-run, bloqueia pelo grep_engine; se nao, bloqueia pelo Claude
    deve_bloquear = total_erros > 0 if args.dry_run else criticos_confirmados > 0

    if deve_bloquear:
        print("❌ Bugs criticos encontrados — verifique o relatorio antes do merge.")
        sys.exit(1)
    else:
        print("✅ Nenhum bug critico confirmado.")
        sys.exit(0)


if __name__ == "__main__":
    main()