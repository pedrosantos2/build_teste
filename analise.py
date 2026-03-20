#!/usr/bin/env python3
# =============================================================================
# analise.py — Entrypoint principal
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
#   2. grep_engine                  -> analise estatica (sem API, gratis)
#   3. Se houver erros:
#      Claude API                   -> confirma falsos positivos + correcoes
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
from claude_analyzer import analisar
from report          import gerar_html
from config import PASTAS_INCLUIR, PASTAS_EXCLUIR, EXTENSOES_ANALISAR


DEFAULT_SKILL    = Path(__file__).parent / "analise-cnpj.md"
DEFAULT_EXEMPLOS = Path(__file__).parent / "exemplos"

# Paths fixos dos workspaces no Jenkins
BASE_WEB  = Path("/Systextil/workspace/WEB/dev")
BASE_CNPJ = Path("/Systextil/workspace/WEB/prod/CNPJ")

# Extensoes e pastas vem do config.py

ICONES = {
    "CRITICO":        "🔴",
    "MEDIO":          "🟠",
    "BAIXO":          "🟡",
    "SUGESTAO":       "🔵",
    "ADVERTENCIA":    "🟣",
    "FALSO_POSITIVO": "🟢",
}
ORDEM_SEVERIDADE = ["CRITICO", "MEDIO", "BAIXO", "SUGESTAO", "ADVERTENCIA"]


def parse_args():
    p = argparse.ArgumentParser(description="Analise CNPJ alfanumerico — Systextil")
    p.add_argument("modulo", nargs="?", default=".",
                   help="Nome do modulo (ex: efic) ou '.' para diretorio atual")
    p.add_argument("--dir-web",  default=None,
                   help="Path do workspace WEB (ex: /Systextil/.../WEB-prod/efic)")
    p.add_argument("--dir-cnpj", default=None,
                   help="Path do workspace CNPJ (ex: /Systextil/.../CNPJ/efic)")
    p.add_argument("--skill",    "-s", default=str(DEFAULT_SKILL))
    p.add_argument("--exemplos", "-e", default=str(DEFAULT_EXEMPLOS))
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
    return p.parse_args()


# ---------------------------------------------------------------------------
# Comparacao de diretorios — sem Git
# ---------------------------------------------------------------------------

def _deve_incluir(relativo: Path) -> bool:
    """
    Retorna True se o arquivo deve ser analisado:
    - Extensao esta em EXTENSOES_ANALISAR
    - Passa por pelo menos uma pasta de PASTAS_INCLUIR
    - Nao passa por nenhuma pasta de PASTAS_EXCLUIR
    """
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
      - "nao_tocados": identicos ao WEB (nunca migrados, podem ter legado)
    Aplica filtros de pastas e extensoes do config.py.
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
            # Novo no CNPJ
            modificados.append(str(relativo))
        elif not filecmp.cmp(str(arquivo_web), str(arquivo_cnpj), shallow=False):
            # Modificado
            modificados.append(str(relativo))
        else:
            # Identico ao WEB — nunca tocado na migracao
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
    # Modificados: diff entre branch principal (WEB) e branch CNPJ
    result = subprocess.run(
        ["git", "diff", f"{branch_main}..{branch_cnpj}", "--name-only"],
        cwd=repo_path, capture_output=True, text=True,
    )
    modificados = [f for f in result.stdout.splitlines() if _deve_incluir(Path(f))]

    # Todos os arquivos do branch CNPJ
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
# Analise estatica
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


def _coletar_telas_hdoc(arquivos: List[str], dir_cnpj: Optional[Path],
                        repo_path: Optional[str], branch_cnpj: Optional[str]) -> set:
    """
    Escaneia arquivos .jsp procurando target_table=HDOC_001.
    Retorna set de base names (sem extensao) cujas telas usam HDOC_001.
    Para essas telas, erros em .fj e .jsp serao rebaixados a AVISO.
    """
    import re as _re
    bases_hdoc = set()
    pat = _re.compile(r'target_table\s*=\s*["\']?HDOC_001', _re.IGNORECASE)

    for relativo in arquivos:
        if not relativo.endswith(".jsp"):
            continue

        conteudo = None
        if dir_cnpj:
            path_real = dir_cnpj / relativo
            if path_real.exists():
                try:
                    conteudo = path_real.read_text(encoding="windows-1252", errors="replace")
                except Exception:
                    pass
        elif repo_path and branch_cnpj:
            result = subprocess.run(
                ["git", "show", f"{branch_cnpj}:{relativo}"],
                cwd=repo_path, capture_output=True
            )
            if result.returncode == 0:
                conteudo = result.stdout.decode("windows-1252", errors="replace")

        if conteudo and pat.search(conteudo):
            base = Path(relativo).stem  # ex: basi_f965
            bases_hdoc.add(base)

    return bases_hdoc


def _rebaixar_erros_hdoc(resultados: List[Dict], bases_hdoc: set) -> None:
    """
    Para telas com target_table=HDOC_001, rebaixa todos os ERRO para AVISO
    nos arquivos .fj e .jsp correspondentes.
    """
    if not bases_hdoc:
        return

    for r in resultados:
        relativo = r.get("arquivo_original", r.get("arquivo", ""))
        sufixo = Path(relativo).suffix
        if sufixo not in (".fj", ".jsp"):
            continue

        base = Path(relativo).stem
        if base not in bases_hdoc:
            continue

        # Move erros para avisos
        erros_rebaixados = []
        for e in r.get("erros", []):
            e["tipo"] = "AVISO"
            e["mensagem"] = "[HDOC_001] " + e.get("mensagem", "")
            erros_rebaixados.append(e)

        r["avisos"] = r.get("avisos", []) + erros_rebaixados
        r["erros"] = []


def _rebaixar_bugs_claude_hdoc(resultado_claude: Dict, bases_hdoc: set) -> None:
    """
    Rebaixa severidade de bugs do Claude para ADVERTENCIA quando o arquivo
    pertence a uma tela com target_table=HDOC_001.
    Tambem recalcula o resumo de contagens.
    """
    if not bases_hdoc:
        return

    for bug in resultado_claude.get("bugs", []):
        arquivo = bug.get("arquivo", "")
        p = Path(arquivo)
        base = p.stem
        sufixo = p.suffix
        # Claude pode retornar path completo ou so o nome — pega o stem do name
        if not sufixo:
            continue
        if sufixo not in (".fj", ".jsp"):
            continue
        if base in bases_hdoc and bug.get("severidade") not in ("FALSO_POSITIVO", "ADVERTENCIA"):
            bug["severidade"] = "ADVERTENCIA"
            bug["descricao"] = "[HDOC_001] " + bug.get("descricao", "")

    # Recalcula resumo
    todos_bugs = resultado_claude.get("bugs", [])
    resultado_claude["resumo"] = {
        "criticos":         sum(1 for b in todos_bugs if b.get("severidade") == "CRITICO"),
        "medios":           sum(1 for b in todos_bugs if b.get("severidade") == "MEDIO"),
        "baixos":           sum(1 for b in todos_bugs if b.get("severidade") == "BAIXO"),
        "sugestoes":        sum(1 for b in todos_bugs if b.get("severidade") == "SUGESTAO"),
        "advertencias":     sum(1 for b in todos_bugs if b.get("severidade") == "ADVERTENCIA"),
        "falsos_positivos": sum(1 for b in todos_bugs if b.get("severidade") == "FALSO_POSITIVO"),
    }


def rodar_analise(arquivos: List[str], dir_cnpj: Optional[Path],
                  repo_path: Optional[str], branch_cnpj: Optional[str]) -> List[Dict]:
    """
    Para cada arquivo modificado:
      - Modo diretorio: le direto do dir_cnpj
      - Modo git: extrai via git show para temp
    """
    resultados = []

    for relativo in arquivos:
        sufixo = Path(relativo).suffix
        if sufixo not in EXTENSOES_ANALISAR:
            continue

        if dir_cnpj:
            # Modo Jenkins — arquivo ja esta no disco
            path_real = str(dir_cnpj / relativo)
            if not Path(path_real).exists():
                continue
            r = analisar_arquivo_do_disco(path_real, relativo)

        else:
            # Modo git — extrai para temp
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
# Console output
# ---------------------------------------------------------------------------

def imprimir_resultados(resultados: List[Dict]) -> int:
    total_erros = 0
    for r in resultados:
        erros  = r.get("erros",  [])
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


def imprimir_bugs_claude(bugs: List[Dict]) -> None:
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
        print(f"\n{ICONES.get(sev,'?')} {sev} ({len(grupo)})")
        for bug in grupo:
            print(f"  {'-'*56}")
            print(f"  >> {bug.get('arquivo','')} : linha {bug.get('linha','')}")
            print(f"  Tipo:     {bug.get('tipo','')}")
            print(f"  Detalhe:  {bug.get('descricao','')}")
            if bug.get("correcao"):
                print(f"  Correcao: {bug.get('correcao','')}")
    print("\n" + "-" * 60)


def converter_para_hits(resultados: List[Dict]) -> List[Dict]:
    from config import COLUNAS_NATIVAS_VARCHAR2

    hits = []
    for r in resultados:
        arquivo       = r.get("arquivo_original", r.get("arquivo", ""))
        pre_existente = r.get("pre_existente", False)
        for item in r.get("erros", []) + r.get("avisos", []):
            mensagem = item.get("mensagem", "")

            # Ignora hits que mencionam colunas nativas VARCHAR2 (ex: CREC_050)
            if any(col in mensagem.lower() for col in COLUNAS_NATIVAS_VARCHAR2):
                continue

            hits.append({
                "arquivo":       arquivo,
                "linha":         item.get("linha", 0),
                "tipo":          item.get("bug", ""),
                "sev_estimada":  "CRITICO" if item.get("tipo") == "ERRO" else "MEDIO",
                "codigo":        item.get("codigo", ""),
                "contexto":      mensagem,
                "match":         mensagem[:80],
                "pre_existente": pre_existente,
            })
    return hits


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    args   = parse_args()
    modulo = args.modulo

    # Resolve paths
    if args.modo_git:
        # Modo git — um unico repositorio, compara branches
        # Branch principal (WEB/main/master) vs branch CNPJ
        # Aceita --dir-cnpj como path do repositorio
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
        # Modo Jenkins — dois diretorios separados
        repo_path   = None
        branch_cnpj = None
        branch_main = None

        # Resolve dir_cnpj
        if args.dir_cnpj:
            dir_cnpj = Path(args.dir_cnpj)
        elif modulo == ".":
            dir_cnpj = Path.cwd()
        else:
            dir_cnpj = BASE_CNPJ / modulo

        # Modulo sempre e so o nome da pasta final
        modulo = dir_cnpj.name

        # Resolve dir_web — se nao passado, deriva do path do CNPJ
        # Ex: /Systextil/workspace/WEB/prod/CNPJ/efic
        #  -> /Systextil/workspace/WEB/prod/WEB-prod/efic
        if args.dir_web:
            dir_web = Path(args.dir_web)
        else:
            # Deriva o WEB a partir do CNPJ
            # /Systextil/workspace/WEB/prod/CNPJ/efic -> /Systextil/workspace/WEB/dev/efic
            dir_web = BASE_WEB / modulo
            if not dir_web.exists():
                print(f"AVISO: diretorio WEB nao encontrado: {dir_web}")
                print(f"       Usando so analise do CNPJ sem comparacao de diff.")
                dir_web = None

        if not dir_cnpj.exists():
            print(f"ERRO: diretorio CNPJ nao encontrado: {dir_cnpj}")
            sys.exit(1)
        if dir_web and not dir_web.exists():
            print(f"ERRO: diretorio WEB nao encontrado: {dir_web}")
            sys.exit(1)

    print(f"\n{'='*60}")
    print(f"  Analise CNPJ — modulo: {modulo}")
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
        # WEB nao encontrado — analisa tudo como modificado
        todos = [str(f.relative_to(dir_cnpj))
                 for f in dir_cnpj.rglob("*")
                 if f.is_file() and _deve_incluir(f.relative_to(dir_cnpj))]
        mapa = {"modificados": sorted(todos), "nao_tocados": []}
    else:
        mapa = listar_arquivos(dir_web, dir_cnpj)

    modificados  = mapa["modificados"]
    nao_tocados  = mapa["nao_tocados"]

    print(f"      {len(modificados)} modificado(s) | {len(nao_tocados)} nao tocado(s)")
    for a in modificados:
        print(f"        [MOD] {a}")
    for a in nao_tocados[:10]:  # mostra so os primeiros 10 para nao poluir
        print(f"        [LEG] {a}")
    if len(nao_tocados) > 10:
        print(f"        ... e mais {len(nao_tocados) - 10} nao tocados")

    if not modificados and not nao_tocados:
        print("\n[OK] Nenhum arquivo encontrado. Nada a analisar.")
        sys.exit(0)

    # ------------------------------------------------------------------
    # PASSO 2 — Analise estatica (sem API)
    # ------------------------------------------------------------------
    print(f"\n[2/3] Analise estatica...")

    # Modificados — severidade normal
    resultados = rodar_analise(modificados, dir_cnpj, repo_path, branch_cnpj)

    # Nao tocados — pre_existente=True mas severidade CRITICO
    # Todo arquivo do modulo com legado e critico, tocado ou nao
    resultados_leg = rodar_analise(nao_tocados, dir_cnpj, repo_path, branch_cnpj)
    for r in resultados_leg:
        r["pre_existente"] = True
    resultados += resultados_leg

    # Rebaixa erros para AVISO em telas com target_table=HDOC_001
    todos_arquivos = modificados + nao_tocados
    bases_hdoc = _coletar_telas_hdoc(todos_arquivos, dir_cnpj, repo_path, branch_cnpj)
    if bases_hdoc:
        print(f"      Telas HDOC_001 (rebaixadas a AVISO): {', '.join(sorted(bases_hdoc))}")
    _rebaixar_erros_hdoc(resultados, bases_hdoc)

    total_erros  = sum(len(r.get("erros",  [])) for r in resultados)
    total_avisos = sum(len(r.get("avisos", [])) for r in resultados)
    print(f"      {total_erros} erros criticos | {total_avisos} avisos")
    imprimir_resultados(resultados)

    # ------------------------------------------------------------------
    # PASSO 3 — Claude (so se houver erros)
    # ------------------------------------------------------------------
    resultado_claude = {"modulo": modulo, "bugs": [], "resumo": {}}

    if not total_erros and not total_avisos:
        print(f"\n[3/3] Sem erros — API nao sera chamada.")
    elif args.dry_run:
        print(f"\n[3/3] --dry-run: pulando chamada a API.")
    else:
        hits = converter_para_hits(resultados)
        print(f"\n[3/3] Enviando {len(hits)} item(ns) ao Claude...")
        resultado_claude = analisar(
            modulo       = modulo,
            hits         = hits,
            skill_path   = args.skill,
            exemplos_dir = args.exemplos,
        )
        # Rebaixa bugs HDOC_001 no resultado do Claude tambem
        if bases_hdoc:
            _rebaixar_bugs_claude_hdoc(resultado_claude, bases_hdoc)

        uso = resultado_claude.get("_usage", {})
        print(f"      Tokens: {uso.get('input_tokens',0):,} input "
              f"| {uso.get('output_tokens',0):,} output "
              f"| {uso.get('cache_read_tokens',0):,} cache")
        imprimir_bugs_claude(resultado_claude.get("bugs", []))

    # ------------------------------------------------------------------
    # Salva resultados
    # ------------------------------------------------------------------
    if args.output:
        saida = Path(args.output)
        saida.mkdir(parents=True, exist_ok=True)
    else:
        saida = dir_cnpj if dir_cnpj else Path(repo_path)
    json_path = saida / f"analise-cnpj-{modulo}.json"
    json_path.write_text(
        json.dumps({"modulo": modulo, "analise": resultados,
                    "claude": resultado_claude}, ensure_ascii=False, indent=2)
    )
    print(f"\n      JSON: {json_path}")

    if not args.json_only:
        html_path = saida / f"analise-cnpj-{modulo}.html"
        gerar_html(resultado_claude, str(html_path))

    # ------------------------------------------------------------------
    # Resumo e exit code
    # ------------------------------------------------------------------
    r = resultado_claude.get("resumo", {})
    criticos_confirmados = r.get("criticos", 0)

    print(f"\n{'='*60}")
    print(f"  RESULTADO — {modulo}")
    print(f"  Estatica : {total_erros} erros | {total_avisos} avisos")
    if not args.dry_run:
        print(f"  Claude   : {criticos_confirmados} criticos confirmados "
              f"| {r.get('falsos_positivos',0)} falsos positivos removidos")
    print(f"{'='*60}\n")

    deve_bloquear = total_erros > 0 if args.dry_run else criticos_confirmados > 0

    if deve_bloquear:
        print("[FALHOU] Bugs criticos encontrados — verifique antes do merge.")
        sys.exit(1)
    else:
        print("[OK] Nenhum bug critico confirmado.")
        sys.exit(0)


if __name__ == "__main__":
    main()