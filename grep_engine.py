#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from config import (
    PALAVRAS_CNPJ, TABELAS_DUALIDADE, TABELAS_NATIVAS_VARCHAR2, COLUNAS_NATIVAS_VARCHAR2,
    IGNORAR_PADROES, PASTAS_INCLUIR, PASTAS_EXCLUIR,
)

"""
Analise estatica de codigo Java para migracao CNPJ alfanumerico.
Versao 2.x — com deteccao de padroes CNPJ usando palavras-chave.
Uso: python3 app.py --source src/main/java/
"""

import os
import sys
import re
import json
import argparse
import glob
from pathlib import Path

# ============================================================
# CONFIGURACAO
# ============================================================

# Tabelas que possuem dualidade de colunas (_R/_O coexistindo com _9/_4).
# Apenas para estas, INSERTs devem gravar em ambos os conjuntos.
# ============================================================
# UTILITARIOS
# ============================================================

def remover_comentarios(texto):
    """
    Remove comentarios Java de um texto-fonte.
    Blocos /* */ sao removidos (preservando quebras de linha), depois linhas //.
    """
    texto = re.sub(r'/\*.*?\*/', lambda m: '\n' * m.group().count('\n'), texto, flags=re.DOTALL)
    texto = re.sub(r'//[^\n]*', '', texto)
    return texto

def achatar_text_blocks(texto):
    """
    Converte Java Text Blocks (triple-quote) em strings normais de aspas duplas.
    Remove as quebras de linha internas e escapa aspas internas para que
    a regex de leitura linha a linha original continue funcionando sem quebras.
    """
    def substituto(match):
        miolo = match.group(1)
        miolo = miolo.replace('\n', ' ')
        miolo = miolo.replace('"', '\\"')
        return '"' + miolo + '"'

    return re.sub(r'"{3}(.*?)"{3}', substituto, texto, flags=re.DOTALL)

def deve_ignorar(caminho):
    nome = Path(caminho).name
    for padrao in IGNORAR_PADROES:
        if Path(nome).match(padrao):
            return True
    return False

def _encontrar_raiz_git(partida="."):
    """Sobe a arvore de diretorios ate encontrar a raiz do repositorio git."""
    caminho = Path(partida).resolve()
    while caminho != caminho.parent:
        if (caminho / ".git").exists():
            return str(caminho)
        caminho = caminho.parent
    return None

# Pastas que DEVEM ser analisadas
# Pastas que NUNCA devem ser analisadas
def buscar_arquivos_java(source_dir=None):
    if source_dir:
        raiz = source_dir
    else:
        raiz = _encontrar_raiz_git() or "."

    padrao = os.path.join(raiz, "**", "*.java")
    arquivos = glob.glob(padrao, recursive=True)

    resultado = []
    for a in arquivos:
        partes = Path(a).parts

        # Ignora se passar por pasta excluída
        if any(p in PASTAS_EXCLUIR for p in partes):
            continue

        # Só inclui se passar por pelo menos uma pasta desejada
        if not any(p in PASTAS_INCLUIR for p in partes):
            continue

        if not deve_ignorar(a):
            resultado.append(a)

    return resultado

# ============================================================
# CLASSIFICACAO
# ============================================================

def classificar(texto_limpo):
    """
    Classifica o arquivo conforme estado da migracao CNPJ.

    Regras de escopo:
    - Imports que contenham "dao" mas NAO da classe CNPJ nova indicam ERRO
    - Duplicata.make(...) indica codigo ja usando CNPJ novo
    """
    # ERRO: import do Cnpj legado OU campo int cgc9/4/2 declarado
    if (re.search(r'\bimport\s+systextil\.dao\.Cnpj\s*;', texto_limpo) or
            re.search(r'\bint\s+cgc[942]\b', texto_limpo)):
        return "ERRO"

    # VERIFICADO: usa a classe CNPJ nova (systextil.CNPJ)
    if (re.search(r'\bimport\s+systextil\.CNPJ\s*;', texto_limpo) or
            re.search(r'\bsystextil\.CNPJ\b', texto_limpo) or
            re.search(r'\bCNPJ\s+\w+\s*[=;,(]', texto_limpo) or
            re.search(r'\bCNPJ\.[A-Z_]', texto_limpo)):
        return "VERIFICADO"

    # VERIFICADO: SQL strings referenciam colunas CNPJ com sufixos novos (_r/_o)
    frags = re.findall(r'"((?:[^"\\]|\\.)*)"', texto_limpo)
    if frags and _RE_COL_CNPJ_RO_SQL.search(' '.join(frags)):
        return "VERIFICADO"

    # ATENCAO: le getString em coluna _R/_O sem import CNPJ
    if re.search(r'getString\s*\(\s*"[^"]*_[RO]"\s*\)', texto_limpo, re.IGNORECASE):
        return "ATENCAO"

    return "SEM_CNPJ"

# ============================================================
# PALAVRAS-CHAVE CNPJ (filtro para deteccao _9/_4/_r/_o)
# ============================================================

_RE_PALAVRAS_CNPJ = re.compile(
    r'(?:' + '|'.join(re.escape(p) for p in PALAVRAS_CNPJ) + r')',
    re.IGNORECASE,
)

_RE_COL_CNPJ_RO_SQL = re.compile(
    r'\b\w*(?:' + '|'.join(re.escape(p) for p in PALAVRAS_CNPJ) + r')\w*_[ro]\b',
    re.IGNORECASE,
)

def _e_coluna_cnpj(nome):
    """Retorna True se o nome da coluna contem uma palavra-chave do dominio CNPJ."""
    return bool(_RE_PALAVRAS_CNPJ.search(nome.lower()))

# ============================================================
# HELPERS DE DETECCAO
# ============================================================

_RE_DUPLICATA_MAKE = re.compile(r'\bDuplicata\b.*?\.make\s*\(', re.DOTALL)

def _linha_e_duplicata_make(linha):
    """
    Linha que usa Duplicata.make(...) ja resolve dualidade internamente.
    """
    return bool(re.search(r'\bDuplicata\b.*\.make\s*\(', linha))

def _achar(lista, num_linha, bug, tipo, msg):
    lista.append({"linha": num_linha, "bug": bug, "tipo": tipo, "mensagem": msg})

# ============================================================
# DETECTORES
# ============================================================

def _e_trio_cnpj(base, cols_set):
    """
    Confirma que 'base' e realmente uma coluna CNPJ verificando a existencia
    da coluna de digito verificador (sufixo 2 ou _2).
    Ex: base='nr_titul_cli_dup_cgc_cli' -> deve existir '...cli2' ou '...cli_2'.
    So retorna True se o trio (9/4/2) parece completo.
    """
    return (base + '2') in cols_set or (base + '_2') in cols_set

def _extrair_conteudo_parenteses(text, start_pos):
    """
    A partir de start_pos, encontra o proximo bloco de conteudo
    entre parenteses balanceados.
    Retorna (conteudo, posicao_final) ou (None, -1) se nao encontrado.
    """
    open_pos = text.find('(', start_pos)
    if open_pos == -1:
        return None, -1
    depth = 0
    for i in range(open_pos, len(text)):
        if text[i] == '(':
            depth += 1
        elif text[i] == ')':
            depth -= 1
            if depth == 0:
                return text[open_pos + 1:i], i
    return None, -1

def detectar_bug1(texto_limpo):
    """
    BUG 1 -- INSERT com mismatch de colunas vs valores:
      a) contagem de colunas != contagem de valores
      b) coluna _r sem par _9, ou _o sem par _4 (dualidade incompleta)
    Compara colunas por nome, verificando dualidade _r/_9 e _o/_4.
    """
    erros = []
    linhas = texto_limpo.split('\n')
    pat_insert_inicio = re.compile(r'(?i)INSERT\s+INTO\b')
    i = 0
    while i < len(linhas):
        if pat_insert_inicio.search(linhas[i]):
            partes = []
            linha_inicio = i + 1
            j = i
            while j < len(linhas) and j < i + 120:
                frags = re.findall(r'"((?:[^"\\]|\\.)*)"', linhas[j])
                partes.extend(frags)
                sql_atual = ' '.join(partes).upper()
                if 'VALUES' in sql_atual:
                    pos_v = sql_atual.index('VALUES')
                    trecho = sql_atual[pos_v:]
                    if trecho.count('(') > 0 and trecho.count('(') == trecho.count(')'):
                        break
                j += 1

            if partes:
                sql = ' '.join(partes)
                if not sql.strip().upper().startswith("INSERT INTO"):
                    i += 1
                    continue

                m_table = re.search(r'(?i)INSERT\s+INTO\s+([A-Z0-9_]+)', sql)
                if m_table:
                    tabela = m_table.group(1).upper()
                    if tabela not in TABELAS_DUALIDADE:
                        i += 1
                        continue
                    # Tabela ja e VARCHAR2 nativo — nao precisa de dualidade
                    if tabela in TABELAS_NATIVAS_VARCHAR2:
                        i += 1
                        continue

                    cols_content, cols_end = _extrair_conteudo_parenteses(sql, m_table.end())
                    if cols_content is None:
                        i += 1
                        continue

                    m_values = re.search(r'(?i)\bVALUES\b', sql[cols_end + 1:])
                    if not m_values:
                        i += 1
                        continue

                    vals_content, _ = _extrair_conteudo_parenteses(sql, cols_end + 1 + m_values.end())
                    if vals_content is None:
                        i += 1
                        continue

                    cols     = [c.strip().lower() for c in cols_content.split(',') if c.strip()]
                    cols_set = set(cols)

                    # a) mismatch de contagem
                    vals = _split_args_toplevel(vals_content)
                    n_vals = len(vals)
                    if n_vals > 0 and len(cols) != n_vals:
                        n_q = vals_content.count('?')
                        _achar(erros, linha_inicio, "BUG_1", "ERRO",
                               f"INSERT INTO {tabela}: {len(cols)} coluna(s) mas {n_vals} valor(es) no VALUES ({n_q} placeholder(s) ?)")

                    # b) pares de dualidade _r/_9 e _o/_4
                    for col in cols:
                        if not _e_coluna_cnpj(col):
                            continue
                        if col.endswith('_r'):
                            base = col[:-2]
                            if not _e_trio_cnpj(base, cols_set):
                                continue
                            if (base + '9') not in cols_set and (base + '_9') not in cols_set:
                                _achar(erros, linha_inicio, "BUG_1", "ERRO",
                                       f"INSERT INTO {tabela}: falta duplicar '{col}' -> adicionar '{base}9' (NUMBER legado) -- INSERT deve gravar em ambas as colunas")
                        elif col.endswith('_o'):
                            base = col[:-2]
                            if not _e_trio_cnpj(base, cols_set):
                                continue
                            if (base + '4') not in cols_set and (base + '_4') not in cols_set:
                                _achar(erros, linha_inicio, "BUG_1", "ERRO",
                                       f"INSERT INTO {tabela}: falta duplicar '{col}' -> adicionar '{base}4' (NUMBER legado) -- INSERT deve gravar em ambas as colunas")
                        elif col.endswith('_9'):
                            base = col[:-2]
                            if not _e_trio_cnpj(base, cols_set):
                                continue
                            if (base + '_r') not in cols_set:
                                _achar(erros, linha_inicio, "BUG_1", "AVISO",
                                       f"INSERT INTO {tabela}: falta duplicar '{col}' -> adicionar '{base}_r' (VARCHAR2 novo) -- INSERT deve gravar em ambas as colunas")
                        elif col.endswith('_4'):
                            base = col[:-2]
                            if not _e_trio_cnpj(base, cols_set):
                                continue
                            if (base + '_o') not in cols_set:
                                _achar(erros, linha_inicio, "BUG_1", "AVISO",
                                       f"INSERT INTO {tabela}: falta duplicar '{col}' -> adicionar '{base}_o' (VARCHAR2 novo) -- INSERT deve gravar em ambas as colunas")
                        elif col.endswith('9') and len(col) >= 2 and col[-2] != '_':
                            base = col[:-1]
                            if not _e_trio_cnpj(base, cols_set):
                                continue
                            if (base + '_r') not in cols_set:
                                _achar(erros, linha_inicio, "BUG_1", "AVISO",
                                       f"INSERT INTO {tabela}: falta duplicar '{col}' -> adicionar '{base}_r' (VARCHAR2 novo) -- INSERT deve gravar em ambas as colunas")
                        elif col.endswith('4') and len(col) >= 2 and col[-2] != '_':
                            base = col[:-1]
                            if not _e_trio_cnpj(base, cols_set):
                                continue
                            if (base + '_o') not in cols_set:
                                _achar(erros, linha_inicio, "BUG_1", "AVISO",
                                       f"INSERT INTO {tabela}: falta duplicar '{col}' -> adicionar '{base}_o' (VARCHAR2 novo) -- INSERT deve gravar em ambas as colunas")
        i += 1
    return erros

def detectar_bug1_builder(linhas_limpas):
    """
    BUG 1 (builder) -- mesma logica do BUG 1 mas para padrao .insertUnique().set(...).
    Verifica pares de dualidade _r/_9 e _o/_4 em colunas CNPJ.
    So reporta colunas que contenham palavras-chave CNPJ.
    """
    erros = []
    pat_inicio  = re.compile(r'\.insertUnique\s*\(\s*\)')
    pat_set     = re.compile(r'\.set\s*\(\s*"([^"]+)"', re.IGNORECASE)
    pat_execute = re.compile(r'\.execute\s*\(')

    i = 0
    while i < len(linhas_limpas):
        if pat_inicio.search(linhas_limpas[i]):
            linha_inicio = i + 1
            cols = []
            j = i
            while j < len(linhas_limpas) and j < i + 80:
                m_set = pat_set.search(linhas_limpas[j])
                if m_set:
                    cols.append(m_set.group(1).lower())
                if pat_execute.search(linhas_limpas[j]) and j > i:
                    break
                j += 1

            pat_mid = re.compile(r'^([a-z_]+)(9|4)([a-z_]+)$')
            cols_dual = [
                c for c in cols
                if _e_coluna_cnpj(c) and (
                    c.endswith(('_r', '_o', '_9', '_4'))
                    or (c.endswith('9') and len(c) >= 2 and c[-2] != '_')
                    or (c.endswith('4') and len(c) >= 2 and c[-2] != '_')
                    or pat_mid.match(c)
                )
            ]
            if not cols_dual:
                i += 1
                continue

            cols_set = set(cols)
            for col in cols_dual:
                if col.endswith('_r'):
                    base = col[:-2]
                    if not _e_trio_cnpj(base, cols_set):
                        continue
                    if (base + '9') not in cols_set and (base + '_9') not in cols_set:
                        _achar(erros, linha_inicio, "BUG_1", "ERRO",
                               f"Builder INSERT: falta duplicar '{col}' -> adicionar '{base}9' (NUMBER legado)")
                elif col.endswith('_o'):
                    base = col[:-2]
                    if not _e_trio_cnpj(base, cols_set):
                        continue
                    if (base + '4') not in cols_set and (base + '_4') not in cols_set:
                        _achar(erros, linha_inicio, "BUG_1", "ERRO",
                               f"Builder INSERT: falta duplicar '{col}' -> adicionar '{base}4' (NUMBER legado)")
                elif col.endswith('_9'):
                    base = col[:-2]
                    if not _e_trio_cnpj(base, cols_set):
                        continue
                    if (base + '_r') not in cols_set:
                        _achar(erros, linha_inicio, "BUG_1", "AVISO",
                               f"Builder INSERT: falta duplicar '{col}' -> adicionar '{base}_r' (VARCHAR2 novo)")
                elif col.endswith('_4'):
                    base = col[:-2]
                    if not _e_trio_cnpj(base, cols_set):
                        continue
                    if (base + '_o') not in cols_set:
                        _achar(erros, linha_inicio, "BUG_1", "AVISO",
                               f"Builder INSERT: falta duplicar '{col}' -> adicionar '{base}_o' (VARCHAR2 novo)")
                elif col.endswith('9') and len(col) >= 2 and col[-2] != '_':
                    base = col[:-1]
                    if not _e_trio_cnpj(base, cols_set):
                        continue
                    if (base + '_r') not in cols_set:
                        _achar(erros, linha_inicio, "BUG_1", "AVISO",
                               f"Builder INSERT: falta duplicar '{col}' -> adicionar '{base}_r' (VARCHAR2 novo)")
                elif col.endswith('4') and len(col) >= 2 and col[-2] != '_':
                    base = col[:-1]
                    if not _e_trio_cnpj(base, cols_set):
                        continue
                    if (base + '_o') not in cols_set:
                        _achar(erros, linha_inicio, "BUG_1", "AVISO",
                               f"Builder INSERT: falta duplicar '{col}' -> adicionar '{base}_o' (VARCHAR2 novo)")
                else:
                    mm = pat_mid.match(col)
                    if mm:
                        prefix, digit, suffix = mm.group(1), mm.group(2), mm.group(3)
                        if (prefix + '2' + suffix) in cols_set:
                            letra = '_r' if digit == '9' else '_o'
                            
                            novos = [
                                prefix + letra + suffix,
                                prefix + '_' + suffix + letra,
                                prefix + suffix + letra,
                                (prefix + '_' + suffix + letra).replace('__', '_')
                            ]
                            
                            if not any(n in cols_set for n in novos):
                                sugerido = (prefix + '_' + suffix + letra).replace('__', '_')
                                _achar(erros, linha_inicio, "BUG_1", "AVISO",
                                       f"Builder INSERT: '{col}' e coluna CNPJ legado (digito no meio) -> adicionar '{sugerido}' (VARCHAR2 novo)")
        i += 1
    return erros

def detectar_bug2(linhas_limpas):
    """BUG 2 -- getInt() em coluna VARCHAR2 (_R/_O)."""
    erros = []
    pat = re.compile(r'\.getInt\s*\(\s*"([^"]*_[RO])"\s*\)', re.IGNORECASE)
    for i, linha in enumerate(linhas_limpas, 1):
        if _linha_e_duplicata_make(linha):
            continue
        m = pat.search(linha)
        if m and _e_coluna_cnpj(m.group(1)):
            _achar(erros, i, "BUG_2", "ERRO",
                   "getInt() em campo VARCHAR2: use getString() para colunas _R/_O")
    return erros

def detectar_bug3(linhas_limpas):
    """
    BUG 3 -- CNPJ.ZEROS.equals() sem .r/.o/.d
    Reporta como AVISO — Claude confirma se argumento e String (ERRO) ou CNPJ (CORRETO).
    """
    erros = []
    pat_errado  = re.compile(r'CNPJ\.ZEROS\.equals\s*\(')
    pat_correto = re.compile(r'CNPJ\.ZEROS\.[rod]\.equals\s*\(')

    for i, linha in enumerate(linhas_limpas, 1):
        if _linha_e_duplicata_make(linha):
            continue
        if pat_errado.search(linha) and not pat_correto.search(linha):
            _achar(erros, i, "BUG_3", "AVISO",
                   "CNPJ.ZEROS.equals() sem .r/.o/.d -- verificar tipo do argumento: "
                   "se for String e ERRO, se for objeto CNPJ e correto")
    return erros


def detectar_bug5(linhas_limpas):
    """BUG 5 -- Integer.parseInt() em campo _R/_O."""
    erros = []
    pat = re.compile(r'Integer\.parseInt\s*\([^)]*\.get[RrOo]\(\)')
    for i, linha in enumerate(linhas_limpas, 1):
        if _linha_e_duplicata_make(linha):
            continue
        if pat.search(linha):
            _achar(erros, i, "BUG_5", "ERRO",
                   "Integer.parseInt() em raiz/ordem: _R/_O podem conter letras -- use CNPJ.parse() ou getString()")
    return erros

def detectar_bug6(linhas_limpas):
    """BUG 6 -- setInt/setLong/setString com tipo errado."""
    achados = []
    pat_num_em_str = re.compile(r'\.(setInt|setLong)\s*\(\s*[^,)]+,\s*([^)]+)\)', re.IGNORECASE)
    pat_str_em_num = re.compile(r'\.setString\s*\(\s*[^,)]+,\s*([^)]+)\)', re.IGNORECASE)
    re_ro = re.compile(r'_[RO]\b', re.IGNORECASE)
    re_94 = re.compile(r'_[94]\b', re.IGNORECASE)
    for i, linha in enumerate(linhas_limpas, 1):
        if _linha_e_duplicata_make(linha):
            continue
        m = pat_num_em_str.search(linha)
        if m:
            valor = m.group(2)
            if re_ro.search(valor) and _e_coluna_cnpj(valor):
                _achar(achados, i, "BUG_6", "ERRO",
                       "setInt/setLong em coluna VARCHAR2 (_R/_O): use setString()")
        else:
            m = pat_str_em_num.search(linha)
            if m:
                valor = m.group(1)
                if re_94.search(valor) and _e_coluna_cnpj(valor):
                    _achar(achados, i, "BUG_6", "AVISO",
                           "setString() em coluna NUMBER (_9/_4): verificar se DDL foi alterado para VARCHAR2 (risco ORA-01722)")
    return achados

def detectar_bug8(linhas_limpas):
    """BUG 8 -- .cgcrt sem acesso a .r/.o/.d."""
    avisos = []
    pat = re.compile(r'\.cgcrt\b(?!\.[rod]\b)')
    for i, linha in enumerate(linhas_limpas, 1):
        if _linha_e_duplicata_make(linha):
            continue
        if pat.search(linha):
            _achar(avisos, i, "BUG_8", "AVISO",
                   "Referencia a .cgcrt sem acessar campo novo (.r/.o/.d): possivel uso do objeto CNPJ como inteiro")
    return avisos

def _split_args_toplevel(text):
    """
    Divide argumentos por virgula no nivel top-level, respeitando parenteses e strings SQL.
    Ignora virgulas e parenteses que estiverem contidos dentro de aspas simples ('...').
    """
    args, current = [], []
    depth = 0
    in_string = False

    for ch in text:
        if ch == "'":
            in_string = not in_string
            current.append(ch)
        elif in_string:
            current.append(ch)
        else:
            if ch in '([{':
                depth += 1
                current.append(ch)
            elif ch in ')]}':
                depth -= 1
                current.append(ch)
            elif ch == ',' and depth == 0:
                args.append(''.join(current).strip())
                current = []
            else:
                current.append(ch)

    tail = ''.join(current).strip()
    if tail:
        args.append(tail)
    return args

def detectar_bug1_appconnection(linhas_limpas):
    """
    BUG 1 (AppConnection) -- verifica se a quantidade de variaveis de valor 
    no construtor bate com placeholders (?).
    """
    erros = []
    sql_var_map = {}
    pat_var = re.compile(r'(?:(?:final\s+)?String\s+)?\b(\w+)\s*=')

    for idx, linha in enumerate(linhas_limpas):
        m = pat_var.search(linha)
        if not m:
            continue

        vname = m.group(1)
        if vname in ('if', 'while', 'for', 'return', 'else', 'catch'):
            continue

        partes = []
        for k in range(idx, min(idx + 120, len(linhas_limpas))):
            frags = re.findall(r'"((?:[^"\\]|\\.)*)"', linhas_limpas[k])
            partes.extend(frags)
            linha_sem_string = re.sub(r'"(?:[^"\\]|\\.)*"', '', linhas_limpas[k])
            if ';' in linha_sem_string:
                break

        sql_u = ' '.join(partes).upper()
        if not re.search(r'\b(SELECT|INSERT|UPDATE|DELETE|FROM|WHERE)\b', sql_u):
            continue

        n_q = ' '.join(partes).count('?')
        if vname not in sql_var_map:
            sql_var_map[vname] = []
        sql_var_map[vname].append((idx, n_q))

    pat_ac = re.compile(r'\bnew\s+AppConnection\s*\(')

    i = 0
    while i < len(linhas_limpas):
        m_ac = pat_ac.search(linhas_limpas[i])
        if not m_ac:
            i += 1
            continue

        linha_inicio = i + 1

        raw_parts = [linhas_limpas[i][m_ac.start():]]
        depth = raw_parts[0].count('(') - raw_parts[0].count(')')
        j = i + 1
        while depth > 0 and j < len(linhas_limpas) and j < i + 60:
            raw_parts.append(linhas_limpas[j])
            depth += linhas_limpas[j].count('(') - linhas_limpas[j].count(')')
            j += 1

        raw = ' '.join(raw_parts)

        open_idx = raw.index('(')
        inner_raw = raw[open_idx + 1:]
        d, end_idx = 1, len(inner_raw)
        for ci, ch in enumerate(inner_raw):
            if ch == '(':
                d += 1
            elif ch == ')':
                d -= 1
                if d == 0:
                    end_idx = ci
                    break
        inner = inner_raw[:end_idx]

        args = _split_args_toplevel(inner)

        if len(args) < 3:
            i += 1
            continue

        sql_arg      = args[1].strip()
        n_val_params = len(args) - 2

        n_q = None
        if '"' in sql_arg:
            frags = re.findall(r'"((?:[^"\\]|\\.)*)"', sql_arg)
            n_q = ' '.join(frags).count('?')
        else:
            vname = re.split(r'\W', sql_arg)[0]
            if vname in sql_var_map:
                entries = sql_var_map[vname]
                best = None
                for (line_idx, count) in entries:
                    if line_idx < i:
                        if best is None or line_idx > best[0]:
                            best = (line_idx, count)
                if best:
                    n_q = best[1]

        if n_q is not None and n_q > 0 and n_val_params != n_q:
            _achar(erros, linha_inicio, "BUG_1", "ERRO",
                   f"AppConnection: SQL tem {n_q} placeholder(s) (?) mas recebe {n_val_params} variavel(is) de valor")
        i += 1
    return erros

def detectar_getint_campo_novo(linhas_limpas):
    """
    BUG 2 (estendido) -- detecta getInt() em coluna VARCHAR2
    tanto como string literal quanto como variavel terminada em _R/_O.
    """
    erros = []
    pat_literal = re.compile(r'\.getInt\s*\(\s*"([^"]*_[ro])"\s*\)', re.IGNORECASE)
    pat_var     = re.compile(r'\.getInt\s*\(\s*(\w*_[RrOo])\s*\)')

    for i, linha in enumerate(linhas_limpas, 1):
        if _linha_e_duplicata_make(linha):
            continue
        m = pat_literal.search(linha)
        if m and _e_coluna_cnpj(m.group(1)):
            _achar(erros, i, "BUG_2", "ERRO",
                   "getInt() em coluna VARCHAR2 (_r/_o): use getString()")
        else:
            m = pat_var.search(linha)
            if m and _e_coluna_cnpj(m.group(1)):
                _achar(erros, i, "BUG_2", "AVISO",
                       "getInt() com identificador terminado em _R/_O: verificar se coluna e VARCHAR2 e usar getString()")
    return erros

def detectar_equals_nullable(linhas_limpas):
    """
    BUG 3 (NullPointer) -- detecta .equals() em campos CNPJ nullable
    """
    erros = []
    pat = re.compile(r'([\w][\w.]*)\.(r|o)\.equals\s*\(', re.IGNORECASE)

    for i, linha in enumerate(linhas_limpas, 1):
        if _linha_e_duplicata_make(linha):
            continue
        for m in pat.finditer(linha):
            base  = m.group(1)
            campo = m.group(2).lower()

            if re.search(r'CNPJ\.ZEROS$', base, re.IGNORECASE):
                continue

            arg = linha[m.end():].strip()

            if re.match(r'CNPJ\.ZEROS', arg, re.IGNORECASE):
                _achar(erros, i, "BUG_3", "ERRO",
                       f"NullPointerException: '{base}.{campo}.equals(CNPJ.ZEROS.{campo})' -- "
                       f"inverter para 'CNPJ.ZEROS.{campo}.equals({base}.{campo})'")
            elif arg.startswith('"'):
                _achar(erros, i, "BUG_3", "AVISO",
                       f"Risco de NullPointerException: '{base}.{campo}' pode ser null -- "
                       f"inverter para literal.equals({base}.{campo})")
    return erros

def detectar_bug10(linhas_limpas):
    """BUG 10 -- inner class com campo int cgc legado."""
    erros = []
    classes_vistas = 0
    brace_depth = 0
    pat_class  = re.compile(r'\bclass\s+\w+')
    pat_legado = re.compile(r'\bint\s+cgc[942]\b')
    for i, linha in enumerate(linhas_limpas, 1):
        if pat_class.search(linha):
            classes_vistas += 1
        brace_depth += linha.count('{') - linha.count('}')
        if classes_vistas > 1 and pat_legado.search(linha):
            _achar(erros, i, "BUG_10", "ERRO",
                   "Inner class com campo int cgc legado (cgc9/cgc4/cgc2): nao migrado para CNPJ alfanumerico")
    return erros

def detectar_procedure_sem_rt(linhas_limpas):
    """
    Detecta chamadas SQL 'call <procedure>( ... )' dentro de strings Java
    """
    erros = []
    pat_call = re.compile(r'\bcall\s+(\w+)', re.IGNORECASE)
    pat_frag = re.compile(r'"((?:[^"\\]|\\.)*)"')

    cnpj_kw = '|'.join(re.escape(p) for p in PALAVRAS_CNPJ)
    pat_cnpj_col = re.compile(r'\b\w*(?:' + cnpj_kw + r')\w*\b', re.IGNORECASE)

    already_reported = set()

    i = 0
    while i < len(linhas_limpas):
        frags = []
        for j in range(i, min(len(linhas_limpas), i + 40)):
            for f in pat_frag.findall(linhas_limpas[j]):
                frags.append(f)

        if frags:
            sql_block = ' '.join(frags).lower()

            for m_call in pat_call.finditer(sql_block):
                proc_name = m_call.group(1)

                if proc_name.lower().endswith('_rt'):
                    continue

                rest = sql_block[m_call.end():]
                paren_start = rest.find('(')
                if paren_start == -1:
                    continue
                paren_end = rest.find(')', paren_start)
                if paren_end == -1:
                    params_text = rest[paren_start:]
                else:
                    params_text = rest[paren_start:paren_end + 1]

                if pat_cnpj_col.search(params_text):
                    linha_num = i + 1
                    key = (linha_num, proc_name)
                    if key in already_reported:
                        continue
                    already_reported.add(key)
                    _achar(erros, linha_num, "BUG_PROC_RT", "ERRO",
                           f"Procedure 'call {proc_name}(...)' recebe parametro CNPJ "
                           f"mas nao termina em _rt -- usar versao _rt para CNPJ alfanumerico")
        i += 1
    return erros

# ============================================================
# BUG_LEGADO -- SQL usa apenas coluna legado sem versao nova
# ============================================================

def detectar_cnpj_legado_em_sql(texto_limpo):
    """
    Varre todos os blocos de strings Java (literals, concatenacoes)
    que parecem SQL e procura colunas CNPJ legado
    """
    erros = []
    linhas = texto_limpo.split('\n')

    pat_sql_inicio = re.compile(r'(?i)"[^"]*\b(SELECT|INSERT|UPDATE|DELETE|WHERE|FROM)\b')
    pat_frag = re.compile(r'"((?:[^"\\]|\\.)*)"')

    pat_leg_nosus = re.compile(r'\b([a-z_][a-z0-9_]{2,}[a-z0-9])(9|4)\b')
    pat_leg_sus   = re.compile(r'\b([a-z_][a-z0-9_]{2,})_(9|4)\b')
    pat_leg_mid   = re.compile(r'\b([a-z_][a-z0-9_]*)(9|4)([a-z_][a-z0-9_]+)\b')

    already_reported = set()

    i = 0
    while i < len(linhas):
        if not pat_sql_inicio.search(linhas[i]):
            i += 1
            continue

        linha_inicio = i + 1

        frags = []
        for j in range(i, min(len(linhas), i + 80)):
            for f in pat_frag.findall(linhas[j]):
                frags.append(f.lower())

        if not frags:
            i += 1
            continue

        sql_block = ' '.join(frags)

        # Pula blocos SQL que referenciam tabelas nativas VARCHAR2
        pat_tabela = re.compile(r'\b(from|into|update)\s+([a-z0-9_]+)', re.IGNORECASE)
        tabelas_no_bloco = {m.group(2).upper() for m in pat_tabela.finditer(sql_block)}
        if tabelas_no_bloco & TABELAS_NATIVAS_VARCHAR2:
            i += 1
            continue

        def _verificar(base, digit, col_display):
            if col_display in COLUNAS_NATIVAS_VARCHAR2:
                return
            if not any(kw in base for kw in PALAVRAS_CNPJ):
                return
            if (base + '2') not in sql_block and (base + '_2') not in sql_block:
                return
            novo = (base + '_r') if digit == '9' else (base + '_o')
            if novo in sql_block:
                return
            key = (linha_inicio, col_display)
            if key in already_reported:
                return
            already_reported.add(key)
            _achar(erros, linha_inicio, "BUG_LEGADO", "ERRO",
                   f"SQL usa apenas coluna legado '{col_display}' sem versao nova '{novo}' -- codigo ainda nao migrado ou falta duplicar")

        def _verificar_mid(prefix, digit, suffix):
            """Digito no meio: base9suffix -> base_r_suffix."""
            col_display = prefix + digit + suffix
            if col_display in COLUNAS_NATIVAS_VARCHAR2:
                return
            if not any(kw in prefix or kw in suffix for kw in PALAVRAS_CNPJ):
                return
            if (prefix + '2' + suffix) not in sql_block:
                return
            letra = '_r' if digit == '9' else '_o'
            
            novos = [
                prefix + letra + suffix,
                prefix + '_' + suffix + letra,
                prefix + suffix + letra,
                (prefix + '_' + suffix + letra).replace('__', '_')
            ]
            
            if any(n in sql_block for n in novos):
                return
            key = (linha_inicio, col_display)
            if key in already_reported:
                return
            already_reported.add(key)
            sugerido = (prefix + '_' + suffix + letra).replace('__', '_')
            _achar(erros, linha_inicio, "BUG_LEGADO", "ERRO",
                   f"SQL usa apenas coluna legado '{col_display}' sem versao nova '{sugerido}' -- codigo ainda nao migrado ou falta duplicar")

        for m in pat_leg_nosus.finditer(sql_block):
            _verificar(m.group(1), m.group(2), m.group(1) + m.group(2))

        for m in pat_leg_sus.finditer(sql_block):
            _verificar(m.group(1), m.group(2), m.group(1) + '_' + m.group(2))

        for m in pat_leg_mid.finditer(sql_block):
            _verificar_mid(m.group(1), m.group(2), m.group(3))

        i += 1
    return erros

# ============================================================
# ORQUESTRADOR DE BUGS
# ============================================================

def detectar_todos_bugs(linhas_limpas, texto_limpo):
    erros  = []
    avisos = []

    erros  += detectar_bug1(texto_limpo)
    erros  += detectar_bug1_builder(linhas_limpas)
    erros  += detectar_bug1_appconnection(linhas_limpas)
    erros  += detectar_bug2(linhas_limpas)
    erros  += detectar_getint_campo_novo(linhas_limpas)
    erros  += detectar_bug3(linhas_limpas)
    erros  += detectar_equals_nullable(linhas_limpas)
    erros  += detectar_bug5(linhas_limpas)
    erros  += detectar_bug6(linhas_limpas)
    erros  += detectar_bug10(linhas_limpas)
    avisos += detectar_bug8(linhas_limpas)
    erros  += detectar_cnpj_legado_em_sql(texto_limpo)

    erros.sort(key=lambda x: x.get("linha", 0))
    avisos.sort(key=lambda x: x.get("linha", 0))
    return erros, avisos

# ============================================================
# ANALISE PRINCIPAL
# ============================================================

def analisar_arquivo(caminho_arquivo):
    try:
        with open(caminho_arquivo, "r", encoding="windows-1252") as f:
            texto_original = f.read()
    except Exception as e:
        print(f"  \u26a0 Erro ao ler {caminho_arquivo}: {e}")
        return None

    if len(texto_original.strip()) < 100:
        return None

    nome_arquivo  = Path(caminho_arquivo).name
    texto_limpo   = remover_comentarios(texto_original)
    texto_limpo   = achatar_text_blocks(texto_limpo)
    linhas_limpas = texto_limpo.split('\n')

    categoria = classificar(texto_limpo)

    erros, avisos = detectar_todos_bugs(linhas_limpas, texto_limpo)

    if categoria == "SEM_CNPJ" and (erros or avisos):
        categoria = "ERRO" if erros else "ATENCAO"

    erros += detectar_procedure_sem_rt(linhas_limpas)

    if erros or avisos:
        if categoria == "SEM_CNPJ":
            categoria = "VERIFICADO"

    partes = [f"Categoria: {categoria}."]
    if erros:
        partes.append(f"{len(erros)} erro(s) critico(s).")
    if avisos:
        partes.append(f"{len(avisos)} aviso(s).")
    if not erros and not avisos and categoria != "SEM_CNPJ":
        partes.append("Nenhum problema detectado.")

    return {
        "arquivo":   nome_arquivo,
        "categoria": categoria,
        "erros":     erros,
        "avisos":    avisos,
        "resumo":    " ".join(partes),
    }

# ============================================================
# SAIDA
# ============================================================

def imprimir_resultado(resultado):
    if not resultado:
        return

    arquivo   = resultado.get("arquivo", "desconhecido")
    categoria = resultado.get("categoria", "?")
    erros     = resultado.get("erros", [])
    avisos    = resultado.get("avisos", [])
    resumo    = resultado.get("resumo", "")

    ICONE_CATEGORIA = {
        "VERIFICADO": "\u2705",
        "ATENCAO":    "\u26a0\ufe0f",
        "ERRO":       "\u274c",
        "SEM_CNPJ":   "\u2b1c",
    }
    icone = ICONE_CATEGORIA.get(categoria, "\u2753")

    if not erros and not avisos:
        print(f"  {icone} [{categoria}] {arquivo} \u2014 sem problemas encontrados")
        return

    print(f"\n  {icone} [{categoria}] {arquivo}")
    if resumo:
        print(f"     {resumo}")

    for erro in erros:
        linha = erro.get("linha", "?")
        bug   = erro.get("bug", "")
        msg   = erro.get("mensagem", "")
        print(f"     \u274c Linha {linha} [{bug}]: {msg}")

    for aviso in avisos:
        linha = aviso.get("linha", "?")
        bug   = aviso.get("bug", "")
        msg   = aviso.get("mensagem", "")
        print(f"     \u26a0\ufe0f  Linha {linha} [{bug}]: {msg}")

def salvar_relatorio(resultados, output_path="reports/analise.json"):
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(resultados, f, indent=2, ensure_ascii=False)
    print(f"\n\U0001f4c4 Relatorio JSON salvo em: {output_path}")

def imprimir_resumo(resultados):
    total_erros   = 0
    total_avisos  = 0
    arquivos_com_problema = 0

    contagem_categoria = {
        "VERIFICADO": 0,
        "ATENCAO":       0,
        "ERRO":      0,
        "SEM_CNPJ":    0,
    }
    contagem_bugs = {}

    for r in resultados:
        erros  = r.get("erros", [])
        avisos = r.get("avisos", [])
        cat    = r.get("categoria", "?")

        total_erros  += len(erros)
        total_avisos += len(avisos)

        if erros or avisos:
            arquivos_com_problema += 1

        if cat in contagem_categoria:
            contagem_categoria[cat] += 1

        for e in erros + avisos:
            bug = e.get("bug", "GERAL")
            contagem_bugs[bug] = contagem_bugs.get(bug, 0) + 1

    print("\n" + "=" * 60)
    print("  RESUMO FINAL -- Analise CNPJ Alfanumerico")
    print("=" * 60)
    print(f"  Arquivos analisados:      {len(resultados)}")
    print(f"  Arquivos com problemas:   {arquivos_com_problema}")
    print(f"  Total de erros criticos:  {total_erros}")
    print(f"  Total de avisos:          {total_avisos}")
    print()
    print("  CLASSIFICACAO DOS ARQUIVOS:")
    print(f"  \u2705 VERIFICADO: {contagem_categoria['VERIFICADO']}")
    print(f"  \u26a0\ufe0f  ATENCAO:    {contagem_categoria['ATENCAO']}")
    print(f"  \u274c ERRO:       {contagem_categoria['ERRO']}")
    print(f"  \u2b1c SEM_CNPJ:   {contagem_categoria['SEM_CNPJ']}")

    if contagem_bugs:
        print()
        print("  BUGS ENCONTRADOS POR TIPO:")
        for bug, qtd in sorted(contagem_bugs.items(), key=lambda x: -x[1]):
            print(f"  {bug}: {qtd} ocorrencia(s)")

    print("=" * 60)
    return total_erros

# ============================================================
# MAIN
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description="Analise estatica de codigo Java para migracao CNPJ alfanumerico"
    )
    parser.add_argument("--source", default=None, help="Diretorio raiz do codigo-fonte Java (se omitido, busca a partir da raiz do repositorio git)")
    parser.add_argument("--output", default="reports/analise.json", help="Caminho do relatorio JSON de saida")
    args = parser.parse_args()

    print("=" * 60)
    print("  ANALISE CNPJ ALFANUMERICO -- Systextil ERP")
    print("  Systextil ERP | Deteccao de Bugs de Migracao CNPJ")
    print("=" * 60)

    arquivos = buscar_arquivos_java(args.source)
    raiz_usada = args.source or _encontrar_raiz_git() or "."
    if not arquivos:
        print(f"\u26a0 Nenhum arquivo Java encontrado em: {raiz_usada}")
        sys.exit(1)

    print(f"\n\U0001f4c2 {len(arquivos)} arquivo(s) Java encontrado(s) em: {raiz_usada}\n")

    resultados = []

    for i, arquivo in enumerate(arquivos, 1):
        nome = Path(arquivo).name
        print(f"[{i}/{len(arquivos)}] Analisando {nome}...")

        resultado = analisar_arquivo(arquivo)
        if resultado:
            resultados.append(resultado)
            imprimir_resultado(resultado)

    salvar_relatorio(resultados, args.output)

    total_erros = imprimir_resumo(resultados)

    if total_erros > 0:
        print(f"\n\u274c {total_erros} erro(s) critico(s) encontrado(s)!")
        print("   Verifique o relatorio JSON para detalhes.")
        sys.exit(1)
    else:
        print(f"\n\u2705 Nenhum erro critico encontrado.")
        sys.exit(0)


if __name__ == "__main__":
    main()

# =============================================================================
# Funcoes Git — resolucao de branches para uso pelo analise.py
# =============================================================================

import subprocess as _subprocess


def _branch_existe(repo_path: str, nome: str) -> bool:
    r = _subprocess.run(
        ["git", "rev-parse", "--verify", nome],
        cwd=repo_path, capture_output=True
    )
    return r.returncode == 0


def _resolver_branch_principal(repo_path: str) -> str:
    """Detecta o branch principal: WEB, main, master, develop, trunk."""
    for candidato in ["WEB", "main", "master", "develop", "trunk"]:
        if _branch_existe(repo_path, candidato):
            return candidato
    raise RuntimeError(
        "Branch principal nao encontrado. "
        "Esperado: WEB, main, master, develop ou trunk. "
        "Verifique com: git branch -a"
    )


def _resolver_branch_cnpj(repo_path: str) -> str:
    """
    Detecta automaticamente qual ref usar para o branch CNPJ.
    Tenta em ordem: origin/CNPJ, CNPJ, qualquer branch com 'cnpj' no nome.
    """
    candidatos = ["origin/CNPJ", "CNPJ"]

    result = _subprocess.run(
        ["git", "branch", "-a"],
        cwd=repo_path, capture_output=True, text=True
    )
    for linha in result.stdout.splitlines():
        nome = linha.strip().lstrip("* ")
        if "cnpj" in nome.lower() and nome not in candidatos:
            candidatos.append(nome)

    for candidato in candidatos:
        if _branch_existe(repo_path, candidato):
            return candidato

    raise RuntimeError(
        f"Branch CNPJ nao encontrado em {repo_path}.\n"
        f"Tentados: {candidatos}\n"
        f"Verifique com: git branch -a"
    )