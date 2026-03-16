#!/usr/bin/env python3
"""
debug.py — Diagnostico completo do ambiente Git e analise
Rode dentro do repositorio: python3 debug.py
"""
import sys
import subprocess
import re
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from grep_engine import (
    _resolver_branch_cnpj,
    _resolver_branch_principal,
    analisar_arquivo,
    deve_ignorar,
)

repo_path = str(Path.cwd())
print(f"repo_path: {repo_path}")
print()

# =============================================================================
# 1. Branches
# =============================================================================
print("=== 1. BRANCHES ===")
try:
    branch_cnpj = _resolver_branch_cnpj(repo_path)
    branch_main = _resolver_branch_principal(repo_path)
    print(f"  Principal : {branch_main!r}")
    print(f"  CNPJ      : {branch_cnpj!r}")
except RuntimeError as e:
    print(f"  ERRO: {e}")
    sys.exit(1)

# =============================================================================
# 2. Arquivos modificados
# =============================================================================
print()
print(f"=== 2. ARQUIVOS MODIFICADOS ({branch_main}..{branch_cnpj}) ===")
result = subprocess.run(
    ["git", "diff", f"{branch_main}..{branch_cnpj}", "--name-only"],
    cwd=repo_path, capture_output=True, text=True
)
todos = result.stdout.splitlines()
extensoes = [".java", ".fj", ".fx", ".jsp"]
arquivos  = [f for f in todos if any(f.endswith(e) for e in extensoes)]

print(f"  Total modificados  : {len(todos)}")
print(f"  Com extensao alvo  : {len(arquivos)}")
for a in arquivos:
    print(f"    + {a}")

if not arquivos:
    print()
    print("  PROBLEMA: nenhum arquivo com extensao alvo no diff.")
    print(f"  Todos os arquivos modificados:")
    for f in todos:
        print(f"    {f}")
    sys.exit(1)

# =============================================================================
# 3. Testa leitura de cada arquivo via git show
# =============================================================================
print()
print("=== 3. LEITURA DOS ARQUIVOS (git show) ===")
import tempfile, os

for arquivo in arquivos:
    result = subprocess.run(
        ["git", "show", f"{branch_cnpj}:{arquivo}"],
        cwd=repo_path, capture_output=True, errors="replace"
    )
    if result.returncode != 0:
        print(f"  ERRO ao ler {arquivo}: {result.stderr[:100]}")
        continue

    tamanho = len(result.stdout)
    print(f"  OK  {tamanho:6} bytes  {arquivo}")

# =============================================================================
# 4. Roda analisar_arquivo em cada .java
# =============================================================================
print()
print("=== 4. ANALISE ESTATICA (analisar_arquivo) ===")

for arquivo in arquivos:
    if not arquivo.endswith(".java"):
        continue
    if deve_ignorar(arquivo):
        print(f"  IGNORADO  {arquivo}")
        continue

    # Extrai para temp
    result = subprocess.run(
        ["git", "show", f"{branch_cnpj}:{arquivo}"],
        cwd=repo_path, capture_output=True
    )
    if result.returncode != 0:
        print(f"  ERRO leitura: {arquivo}")
        continue

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".java", mode="wb")
    tmp.write(result.stdout)
    tmp.close()

    try:
        r = analisar_arquivo(tmp.name)
    finally:
        os.unlink(tmp.name)

    if not r:
        print(f"  VAZIO/SKIP  {arquivo}")
        continue

    erros  = r.get("erros",  [])
    avisos = r.get("avisos", [])
    cat    = r.get("categoria", "?")

    if erros or avisos:
        print(f"  [{cat}] {arquivo} — {len(erros)} erro(s) | {len(avisos)} aviso(s)")
        for e in erros:
            print(f"    🔴 Linha {e.get('linha','?')} [{e.get('bug','')}]: {e.get('mensagem','')}")
        for a in avisos:
            print(f"    🟠 Linha {a.get('linha','?')} [{a.get('bug','')}]: {a.get('mensagem','')}")
    else:
        print(f"  [{cat}] {arquivo} — sem problemas")