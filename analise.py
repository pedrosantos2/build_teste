#!/usr/bin/env python3
# =============================================================================
# analise.py — Entrypoint RT-only
# Uso: python analise.py <modulo> [opcoes]
#
# Modo Jenkins (dois workspaces separados):
#   python analise.py efic \
#       --dir-web  /Systextil/workspace/WEB/prod/WEB-prod/efic \
#       --dir-cnpj /Systextil/workspace/WEB/prod/CNPJ/efic
#
# Modo local (dois branches no mesmo repo):
#   python analise.py . --modo-git
#
# Fluxo:
#   1. Compara dir-web vs dir-cnpj  -> lista arquivos modificados
#   2. grep_engine (RT-only)        -> extrai imports/invocacoes + detecta BUG_PROC_RT
#   3. Claude Tipagem               -> verifica incompatibilidades String/int (RT)
#   4. Relatorio HTML + JSON
#   5. exit 1 se criticos, exit 0 se limpo
# =============================================================================

import argparse
import filecmp
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import List, Dict, Any, Optional

import grep_engine
from claude_analyzer import analisar_tipagem
from report          import gerar_html
from config import PASTAS_INCLUIR, PASTAS_EXCLUIR, EXTENSOES_ANALISAR


DEFAULT_SKILL    = Path(__file__).parent / "analise-cnpj.md"

# Paths fixos dos workspaces no Jenkins
BASE_WEB  = Path("/Systextil/workspace/WEB/dev")
BASE_CNPJ = Path("/Systextil/workspace/WEB/prod/CNPJ")

# Paths fixos dos repositorios auxiliares (para checagem de Tipagem / RT)
BASE_PLUGINS  = BASE_CNPJ / "systextil-plugins-api"
BASE_BO       = BASE_CNPJ / "systextil-bo"
BASE_FUNCTION = BASE_CNPJ / "systextil-function"

ICONES = {
    "CRITICO":        "🔴",
    "MEDIO":          "🟠",
    "BAIXO":          "🟡",
    "SUGESTAO":       "🔵",
    "ADVERTENCIA":    "🟣",
    "FALSO_POSITIVO": "🟢",
}


def parse_args():
    p = argparse.ArgumentParser(description="Analise RT — Systextil")
    p.add_argument("modulo", nargs="?", default=".",
                   help="Nome do modulo (ex: efic) ou '.' para diretorio atual")
    p.add_argument("--dir-web",  default=None,
                   help="Path do workspace WEB (ex: /Systextil/.../WEB-prod/efic)")
    p.add_argument("--dir-cnpj", default=None,
                   help="Path do workspace CNPJ (ex: /Systextil/.../CNPJ/efic)")
    p.add_argument("--dry-run",        action="store_true",
                   help="Roda so analise estatica, sem chamar API")
    p.add_argument("--json-only",      action="store_true")
    p.add_argument("--output",    "-o", default=None,
                   help="Diretorio de saida para JSON e HTML (default: dir-cnpj)")
    p.add_argument("--modo-git",       action="store_true",
                   help="Usa git diff em vez de comparar diretorios (modo local)")
    p.add_argument("--branch-web",  default=None,
                   help="Branch WEB/principal (auto-detecta: WEB, main, master)")
    p.add_argument("--branch-cnpj", default=None,
                   help="Branch CNPJ (auto-detecta: origin/CNPJ, CNPJ)")
    p.add_argument("--dir-plugins", default=None,
                   help="Path do workspace do systextil-plugins-api")
    p.add_argument("--dir-bo", default=None,
                   help="Path do workspace do systextil-bo")
    p.add_argument("--dir-function", default=None,
                   help="Path do workspace do systextil-function")
    return p.parse_args()


# ---------------------------------------------------------------------------
# Comparacao de diretorios — sem Git
# ---------------------------------------------------------------------------

def _deve_incluir(relativo: Path) -> bool:
    partes = set(relativo.parts)
    if relativo.suffix not in EXTENSOES_ANALISAR:
        return False
    if any(p in PASTAS_EXCLUIR for p in partes):
        return False
    if not any(p in PASTAS_INCLUIR for p in partes):
        return False
    return True


def listar_arquivos(dir_web: Path, dir_cnpj: Path) -> Dict[str, List[str]]:
    """
    Varre o diretorio CNPJ recursivamente e classifica cada arquivo:
      - "modificados": diferentes do WEB ou novos no CNPJ
      - "nao_tocados": identicos ao WEB
    """
    modificados = []
    nao_tocados = []

    for arquivo_cnpj in dir_cnpj.rglob("*"):
        if not arquivo_cnpj.is_file():
            continue

        relativo = arquivo_cnpj.relative_to(dir_cnpj)

        if not _deve_incluir(relativo):
            continue

        arquivo_web = dir_web / relativo

        if not arquivo_web.exists():
            modificados.append(str(relativo))
        elif not filecmp.cmp(str(arquivo_web), str(arquivo_cnpj), shallow=False):
            modificados.append(str(relativo))
        else:
            nao_tocados.append(str(relativo))

    return {
        "modificados": sorted(modificados),
        "nao_tocados": sorted(nao_tocados),
    }


# ---------------------------------------------------------------------------
# Comparacao via Git — modo local
# ---------------------------------------------------------------------------

def listar_arquivos_git(repo_path: str, branch_main: str,
                        branch_cnpj: str) -> Dict[str, List[str]]:
    result = subprocess.run(
        ["git", "diff", f"{branch_main}...{branch_cnpj}", "--name-only"],
        cwd=repo_path, capture_output=True, text=True,
    )
    modificados = [f for f in result.stdout.splitlines() if _deve_incluir(Path(f))]

    result_all = subprocess.run(
        ["git", "ls-tree", "-r", "--name-only", branch_cnpj],
        cwd=repo_path, capture_output=True, text=True,
    )
    todos = [f for f in result_all.stdout.splitlines() if _deve_incluir(Path(f))]
    mod_set = set(modificados)
    nao_tocados = [f for f in todos if f not in mod_set]

    return {
        "modificados": sorted(modificados),
        "nao_tocados": sorted(nao_tocados),
    }


# ---------------------------------------------------------------------------
# Analise estatica RT
# ---------------------------------------------------------------------------

def analisar_arquivo_do_disco(path_real: str, path_relativo: str) -> Optional[Dict]:
    """Roda grep_engine.analisar_arquivo em um arquivo real no disco."""
    if grep_engine.deve_ignorar(path_relativo):
        return None

    r = grep_engine.analisar_arquivo(path_real)

    if r:
        r["arquivo_original"] = path_relativo
        r["arquivo"]          = Path(path_relativo).name
    return r


def rodar_analise(arquivos: List[str], dir_cnpj: Optional[Path],
                  repo_path: Optional[str], branch_cnpj: Optional[str]) -> List[Dict]:
    """
    Para cada arquivo, tenta ler na ordem:
      1. dir_cnpj (diretorio no disco — modo Jenkins ou workspace git)
      2. repo_path (arquivo no disco relativo ao repo — modo git com checkout)
      3. git show (fallback — extrai do branch para temp)
    """
    resultados = []

    for relativo in arquivos:
        sufixo = Path(relativo).suffix
        if sufixo not in EXTENSOES_ANALISAR:
            continue

        r = None
        path_real = None

        if dir_cnpj:
            candidato = dir_cnpj / relativo
            if candidato.exists():
                path_real = str(candidato)
        if not path_real and repo_path:
            candidato = Path(repo_path) / relativo
            if candidato.exists():
                path_real = str(candidato)

        if path_real:
            r = analisar_arquivo_do_disco(path_real, relativo)
        elif repo_path and branch_cnpj:
            result = subprocess.run(
                ["git", "show", f"{branch_cnpj}:{relativo}"],
                cwd=repo_path, capture_output=True
            )
            if result.returncode != 0:
                continue
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=sufixo, mode="wb")
            tmp.write(result.stdout)
            tmp.close()
            try:
                r = analisar_arquivo_do_disco(tmp.name, relativo)
            finally:
                os.unlink(tmp.name)

        if r:
            resultados.append(r)

    return resultados


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    args   = parse_args()
    modulo = args.modulo

    # Resolve paths
    if args.modo_git:
        from grep_engine import _resolver_branch_cnpj, _resolver_branch_principal
        if args.dir_cnpj:
            repo_path = str(Path(args.dir_cnpj).resolve())
        elif modulo == ".":
            repo_path = str(Path.cwd())
        else:
            repo_path = modulo
        modulo      = Path(repo_path).name
        dir_web     = None
        dir_cnpj    = None
        branch_cnpj = args.branch_cnpj or _resolver_branch_cnpj(repo_path)
        branch_main = args.branch_web  or _resolver_branch_principal(repo_path)
    else:
        repo_path   = None
        branch_cnpj = None
        branch_main = None

        if args.dir_cnpj:
            dir_cnpj = Path(args.dir_cnpj)
        elif modulo == ".":
            dir_cnpj = Path.cwd()
        else:
            dir_cnpj = BASE_CNPJ / modulo

        modulo = dir_cnpj.name

        if args.dir_web:
            dir_web = Path(args.dir_web)
        else:
            dir_web = BASE_WEB / modulo
            if not dir_web.exists():
                print(f"AVISO: diretorio WEB nao encontrado: {dir_web}")
                dir_web = None

        if not dir_cnpj.exists():
            print(f"ERRO: diretorio CNPJ nao encontrado: {dir_cnpj}")
            sys.exit(1)

    print(f"\n{'='*60}")
    print(f"  Analise RT — modulo: {modulo}")
    if args.modo_git:
        print(f"  Repo : {repo_path}")
        print(f"  WEB  : branch {branch_main}")
        print(f"  CNPJ : branch {branch_cnpj}")
    elif dir_web:
        print(f"  WEB  : {dir_web}")
        print(f"  CNPJ : {dir_cnpj}")
    print(f"{'='*60}")

    # ------------------------------------------------------------------
    # PASSO 1 — Arquivos modificados
    # ------------------------------------------------------------------
    print(f"\n[1/3] Coletando arquivos modificados...")

    if args.modo_git:
        mapa = listar_arquivos_git(repo_path, branch_main, branch_cnpj)
    elif dir_web is None:
        todos = [str(f.relative_to(dir_cnpj))
                 for f in dir_cnpj.rglob("*")
                 if f.is_file() and _deve_incluir(f.relative_to(dir_cnpj))]
        mapa = {"modificados": sorted(todos), "nao_tocados": []}
    else:
        mapa = listar_arquivos(dir_web, dir_cnpj)

    modificados = mapa["modificados"]
    nao_tocados = mapa["nao_tocados"]

    print(f"      {len(modificados)} modificado(s) | {len(nao_tocados)} nao tocado(s)")
    for a in modificados:
        print(f"        [MOD] {a}")

    if not modificados and not nao_tocados:
        print("\n[OK] Nenhum arquivo encontrado. Nada a analisar.")
        sys.exit(0)

    # ------------------------------------------------------------------
    # PASSO 2 — Analise RT estatica (sem API)
    # ------------------------------------------------------------------
    print(f"\n[2/3] Analise RT estatica...")

    todos_arquivos = modificados + nao_tocados
    resultados = rodar_analise(todos_arquivos, dir_cnpj, repo_path, branch_cnpj)

    total_proc_rt = sum(len(r.get("erros", [])) for r in resultados)
    print(f"      {total_proc_rt} ocorrencia(s) BUG_PROC_RT | {len(resultados)} arquivo(s) analisado(s)")

    # ------------------------------------------------------------------
    # PASSO 3 — Claude Tipagem RT
    # ------------------------------------------------------------------
    resultado_tipagem = {"inconsistencias": [], "_usage": {}}
    if args.dry_run:
        print(f"\n[3/3] --dry-run: pulando Claude para Tipagem.")
    else:
        repos_aux = {
            "plugins_api": args.dir_plugins or str(BASE_PLUGINS),
            "bo":          args.dir_bo      or str(BASE_BO),
            "function":    args.dir_function or str(BASE_FUNCTION),
            "projeto":     str(dir_cnpj) if dir_cnpj else (repo_path or ""),
        }

        print(f"\n[3/3] Verificando incompatibilidades de Tipagem RT...")
        resultado_tipagem = analisar_tipagem(resultados, repos_aux=repos_aux)

        inconsistencias = resultado_tipagem.get("inconsistencias", [])
        uso_tipagem     = resultado_tipagem.get("_usage", {})
        print(f"      Tokens: {uso_tipagem.get('input_tokens',0):,} input "
              f"| {uso_tipagem.get('output_tokens',0):,} output")

        if inconsistencias:
            print(f"      Encontradas {len(inconsistencias)} possivel(is) incompatibilidade(s).")
            for inc in inconsistencias:
                sev  = inc.get("severidade", "ADVERTENCIA")
                icone = ICONES.get(sev, "🟣")
                arq  = inc.get("arquivo", "?")
                lin  = inc.get("linha", "?")
                cod  = inc.get("codigo_analisado", "?").strip()
                sug  = inc.get("correcao_sugerida", {}).get("metodo_substituto", "?")
                print(f"        {icone} [{sev}] {arq}:{lin}")
                print(f"           Codigo:   {cod}")
                print(f"           Sugestao: Trocar para {sug}")
        else:
            print(f"      Nenhuma incompatibilidade encontrada.")

    # Consolida bugs RT para saida
    bugs_rt = []
    for inc in resultado_tipagem.get("inconsistencias", []):
        metodo_sub = inc.get("correcao_sugerida", {}).get("metodo_substituto")
        if metodo_sub:
            desc_tipagem = (
                f"Possivel uso de String onde se espera int. "
                f"Sugerida substituicao por {metodo_sub}"
            )
        else:
            desc_tipagem = (
                "Possivel uso de String onde se espera int. "
                "Sem metodo substituto automatico"
            )

        bugs_rt.append({
            "arquivo":    inc.get("arquivo"),
            "linha":      inc.get("linha"),
            "tipo":       "BUG_TIPAGEM_RT",
            "severidade": inc.get("severidade", "ADVERTENCIA"),
            "descricao":  desc_tipagem,
            "correcao":   inc.get("codigo_analisado", ""),
        })

    # Adiciona erros BUG_PROC_RT
    for r in resultados:
        for e in r.get("erros", []):
            bugs_rt.append({
                "arquivo":    r.get("arquivo_original", r.get("arquivo", "")),
                "linha":      e.get("linha"),
                "tipo":       e.get("bug", "BUG_PROC_RT"),
                "severidade": "CRITICO" if e.get("tipo") == "ERRO" else "ADVERTENCIA",
                "descricao":  e.get("mensagem", ""),
                "correcao":   "",
            })

    resumo_rt = {
        "criticos":         sum(1 for b in bugs_rt if b.get("severidade") == "CRITICO"),
        "medios":           sum(1 for b in bugs_rt if b.get("severidade") == "MEDIO"),
        "baixos":           sum(1 for b in bugs_rt if b.get("severidade") == "BAIXO"),
        "sugestoes":        sum(1 for b in bugs_rt if b.get("severidade") == "SUGESTAO"),
        "advertencias":     sum(1 for b in bugs_rt if b.get("severidade") == "ADVERTENCIA"),
        "falsos_positivos": sum(1 for b in bugs_rt if b.get("severidade") == "FALSO_POSITIVO"),
    }

    resultado_final = {
        "modulo":  modulo,
        "bugs":    bugs_rt,
        "resumo":  resumo_rt,
        "_usage":  resultado_tipagem.get("_usage", {}),
    }

    # ------------------------------------------------------------------
    # Salva resultados
    # ------------------------------------------------------------------
    if args.output:
        saida = Path(args.output)
        saida.mkdir(parents=True, exist_ok=True)
    elif dir_cnpj:
        saida = dir_cnpj
    else:
        saida = Path(repo_path)

    json_path = saida / f"analise-rt-{modulo}.json"
    json_path.write_text(
        json.dumps(resultado_final, ensure_ascii=False, indent=2)
    )
    print(f"\n      JSON: {json_path}")

    if not args.json_only:
        html_path = saida / f"analise-rt-{modulo}.html"
        gerar_html(resultado_final, str(html_path))

    # ------------------------------------------------------------------
    # Resumo e exit code
    # ------------------------------------------------------------------
    criticos = resumo_rt.get("criticos", 0)
    advertencias = resumo_rt.get("advertencias", 0)

    print(f"\n{'='*60}")
    print(f"  RESULTADO RT — {modulo}")
    print(f"  Criticos: {criticos} | Advertencias: {advertencias}")
    print(f"{'='*60}\n")

    if criticos > 0:
        print("[FALHOU] Bugs criticos RT encontrados — verifique antes do merge.")
        sys.exit(1)
    else:
        print("[OK] Nenhum bug critico RT confirmado.")
        sys.exit(0)


if __name__ == "__main__":
    main()
