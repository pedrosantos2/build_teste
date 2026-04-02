#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
grep_engine.py — Analise estatica RT-only.
Detecta incompatibilidades de tipagem (String/int) em chamadas .fj -> Java,
cruzando com assinaturas reais dos repositorios auxiliares.
"""

from config import (
    PALAVRAS_CNPJ, IGNORAR_PADROES, PASTAS_INCLUIR, PASTAS_EXCLUIR,
)

import os
import re
import glob
import subprocess
from pathlib import Path

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


def buscar_arquivos_java(source_dir=None, branch_main=None, branch_cnpj=None):
    """
    Retorna lista de arquivos .java a analisar.

    Modo git (branch_main + branch_cnpj fornecidos):
      - Usa 'git diff branch_main...branch_cnpj --name-only' para obter
        apenas os arquivos modificados no branch CNPJ em relacao ao principal.

    Modo glob (padrao):
      - Varre o disco recursivamente.
    """
    raiz = source_dir or _encontrar_raiz_git() or "."

    if branch_main and branch_cnpj:
        result = subprocess.run(
            ["git", "diff", f"{branch_main}...{branch_cnpj}", "--name-only"],
            cwd=raiz, capture_output=True, text=True,
        )
        arquivos_relativos = [
            f for f in result.stdout.splitlines()
            if f.endswith(".java")
        ]

        resultado = []
        for rel in arquivos_relativos:
            partes = Path(rel).parts
            if any(p in PASTAS_EXCLUIR for p in partes):
                continue
            if not any(p in PASTAS_INCLUIR for p in partes):
                continue
            if deve_ignorar(rel):
                continue
            resultado.append(str(Path(raiz) / rel))
        return resultado

    # --- modo glob ---
    padrao = os.path.join(raiz, "**", "*.java")
    arquivos = glob.glob(padrao, recursive=True)

    resultado = []
    for a in arquivos:
        partes = Path(a).parts
        if any(p in PASTAS_EXCLUIR for p in partes):
            continue
        if not any(p in PASTAS_INCLUIR for p in partes):
            continue
        if not deve_ignorar(a):
            resultado.append(a)
    return resultado


# ============================================================
# PALAVRAS-CHAVE CNPJ (para detectar_procedure_sem_rt)
# ============================================================

_PALAVRAS_CURTAS = [p for p in PALAVRAS_CNPJ if len(p) <= 4]
_PALAVRAS_LONGAS = [p for p in PALAVRAS_CNPJ if len(p) > 4]


def _build_palavras_pattern():
    """Constroi regex que exige word boundary para palavras curtas."""
    partes = []
    if _PALAVRAS_LONGAS:
        partes.append('|'.join(re.escape(p) for p in _PALAVRAS_LONGAS))
    if _PALAVRAS_CURTAS:
        curtas = '|'.join(re.escape(p) for p in _PALAVRAS_CURTAS)
        partes.append(r'(?:(?:^|_)(?:' + curtas + r')(?:_|$|\d))')
    return r'(?:' + '|'.join(partes) + r')'


_RE_PALAVRAS_CNPJ = re.compile(
    _build_palavras_pattern(),
    re.IGNORECASE,
)


def _e_coluna_cnpj(nome):
    """
    Retorna True se o nome da coluna contem uma palavra-chave do dominio CNPJ.
    """
    return bool(_RE_PALAVRAS_CNPJ.search(nome.lower()))


def _achar(lista, num_linha, bug, tipo, msg):
    lista.append({"linha": num_linha, "bug": bug, "tipo": tipo, "mensagem": msg})


# ============================================================
# CONSTANTES RT — regex para extracao de assinaturas e invocacoes
# ============================================================

REGEX_IMPORTS_FJ = re.compile(r'^import\s+([\w\.]+)(?:\.\*)?\s*;', re.MULTILINE)

REGEX_INVOCACOES_FJ = re.compile(
    r'(?:(?:\w+[\w\.]*)\s+)?(\w+)\s*=\s*(?:([a-zA-Z_#0-9][\w\.#]*)\.)?([a-zA-Z_]\w*)\s*\((.*?)\)\s*;|([a-zA-Z_#0-9][\w\.#]*)\.([a-zA-Z_]\w*)\s*\((.*?)\)\s*;',
    re.DOTALL
)

# Declaracoes de variaveis no .fj: "NomeClasse varNome = ..." ou "NomeClasse varNome;"
REGEX_DECL_VAR_FJ = re.compile(r'^\s*([A-Z]\w+)\s+(\w+)\s*(?:=|;)', re.MULTILINE)

# Assinaturas de metodos Java
REGEX_METODO_JAVA = re.compile(
    r'(?:public|protected|private)\s+'
    r'(?:(?:static|final|abstract|synchronized|native|default)\s+)*'
    r'(\w+(?:<[^>]+>)?)\s+'
    r'(\w+)\s*\('
    r'([^)]*)\)',
    re.MULTILINE
)

_TIPOS_NUMERICOS = frozenset({'int', 'Integer', 'long', 'Long', 'short', 'Short', 'byte', 'Byte'})

# Sufixos que indicam que a variavel e uma String de CNPJ alfanumerico dividido
# _r = raiz (parte numerica inicial)  _o = ordem (parte numerica complementar)
_RE_CNPJ_SPLIT_SUFIXO = re.compile(r'_[ro]$', re.IGNORECASE)


def _e_arg_cnpj_split(arg: str) -> bool:
    """
    Retorna True se o argumento e uma variavel com sufixo CNPJ-split (_r ou _o).
    Esses sufixos indicam que a variavel armazena a parte alfanumerica (String) do CNPJ.
    Ex: cnpj_r, cgc_fornec_r, cnpj_cli_o, cgc_o
    Quando passados onde o Java espera int, representam erro de tipagem definitivo.
    """
    return bool(_RE_CNPJ_SPLIT_SUFIXO.search(arg.strip()))


_METODOS_SEMPRE_IGNORAR_TIPAGEM = {
    "setString", "setInt", "setLong", "setShort", "setByte",
    "setBigDecimal", "setDate", "setTimestamp", "setNull", "setObject",
    "setNullable", "setSearchRanges"
}

_CLASSES_SEMPRE_IGNORAR_TIPAGEM = {
    "PreparedStatement", "CallableStatement", "ResultSet", "Connection", "Statement",
    "BigDecimal", "String", "Integer", "Long", "CNPJ", "UtilBinding",
}


def _deve_ignorar_invocacao_tipagem(import_pkg: str, tipo_objeto: str,
                                    objeto: str, metodo: str) -> bool:
    """
    Filtra invocacoes que nao representam bug de tipagem RT de regra de negocio.
    Evita falsos positivos em APIs utilitarias/JDBC e chamadas de construcao CNPJ.
    """
    if metodo in _METODOS_SEMPRE_IGNORAR_TIPAGEM:
        return True

    if tipo_objeto in _CLASSES_SEMPRE_IGNORAR_TIPAGEM or objeto in _CLASSES_SEMPRE_IGNORAR_TIPAGEM:
        return True

    # CNPJ.get(...) e construcao valida e nao deve entrar na analise RT.
    if (objeto == "CNPJ" or tipo_objeto == "CNPJ") and metodo == "get":
        return True

    # Import de libs/JDK nao deve gerar sem_cobertura de regra de negocio.
    if import_pkg and (
        import_pkg.startswith("java.") or
        import_pkg.startswith("javax.") or
        import_pkg.startswith("jakarta.") or
        import_pkg.startswith("org.") or
        import_pkg.startswith("com.sun.")
    ):
        return True

    return False


# ============================================================
# EXTRATORES (para .fj e .java)
# ============================================================

def extrair_imports_fj(texto):
    """Extrai todos os imports do arquivo."""
    return REGEX_IMPORTS_FJ.findall(texto)


def extrair_variaveis_fj(texto: str) -> dict:
    """
    Extrai declaracoes de variaveis tipadas de um arquivo .fj.
    Retorna: {'nomeVar': 'NomeClasse', ...}
    """
    resultado = {}
    for m in REGEX_DECL_VAR_FJ.finditer(texto):
        resultado[m.group(2)] = m.group(1)
    return resultado


def extrair_assinaturas_java(caminho_java: str) -> dict:
    """
    Extrai assinaturas de metodos de um arquivo .java via regex.
    Retorna: {'nomeMetodo': [{'retorno': 'int', 'params': [{'tipo': 'int', 'nome': 'x'}]}, ...]}
    """
    try:
        with open(caminho_java, 'r', encoding='utf-8', errors='replace') as f:
            texto = f.read()
    except (OSError, IOError):
        return {}

    texto = re.sub(r'/\*.*?\*/', '', texto, flags=re.DOTALL)
    texto = re.sub(r'//[^\n]*', '', texto)

    resultado = {}
    for m in REGEX_METODO_JAVA.finditer(texto):
        retorno    = m.group(1)
        nome       = m.group(2)
        params_raw = m.group(3).strip()

        params = []
        if params_raw:
            for parte in params_raw.split(','):
                tokens = [t for t in parte.split() if not t.startswith('@')]
                is_varargs = False
                if len(tokens) >= 2:
                    tipo_raw = tokens[-2]
                    if tipo_raw.endswith('...'):
                        tipo_raw = tipo_raw[:-3]
                        is_varargs = True
                    # strip generics: List<Integer> -> List
                    tipo_raw = re.sub(r'<.*>', '', tipo_raw)
                    nome_raw = tokens[-1].lstrip('.')  # varargs nome pode vir como "...nome"
                    params.append({'tipo': tipo_raw, 'nome': nome_raw, 'varargs': is_varargs})
                elif len(tokens) == 1:
                    params.append({'tipo': tokens[0], 'nome': '', 'varargs': False})

        resultado.setdefault(nome, []).append({'retorno': retorno, 'params': params})

    return resultado


def _classificar_arg(arg: str) -> str:
    """
    Classifica o tipo de um argumento de chamada de metodo.
    Retorna: 'string_literal' | 'int_literal' | 'null' | 'cast_int' | 'parse_int' | 'variavel'
    """
    arg = arg.strip()
    if not arg:
        return 'vazio'
    if (arg.startswith('"') and arg.endswith('"')) or (arg.startswith("'") and arg.endswith("'")):
        return 'string_literal'
    if arg == 'null':
        return 'null'
    if re.match(r'^\((int|Integer|long|Long)\)', arg):
        return 'cast_int'
    if 'Integer.parseInt' in arg or 'Integer.valueOf' in arg or 'Long.parseLong' in arg:
        return 'parse_int'
    try:
        int(arg)
        return 'int_literal'
    except ValueError:
        pass
    return 'variavel'


def extrair_invocacoes_fj(texto, linha_offset=1):
    """
    Extrai chamadas de metodos iterando com balanceamento de parenteses.
    Isso substitui o uso direto de re.DOTALL que quebrava em cascata de parênteses
    (como em overloads aninhados, ex: val = parseInt(String.valueOf(x), base)).
    """
    resultados = []
    
    # Captura: [atribuicao =]? [objeto.]metodo(
    pattern = re.compile(r'(?:(?:([a-zA-Z_]\w*)\s*=)\s*)?(?:([^=;\(\)\s]+)\.)?([a-zA-Z_]\w*)\s*\(')
    
    pos = 0
    while True:
        match = pattern.search(texto, pos)
        if not match:
            break
            
        m_start = match.end() - 1
        parens = 0
        in_string = False
        escape = False
        args_end = -1
        
        for i in range(m_start, len(texto)):
            c = texto[i]
            if escape:
                escape = False
                continue
            if c == '\\':
                escape = True
                continue
            if c == '"':
                in_string = not in_string
                continue
                
            if not in_string:
                if c == '(':
                    parens += 1
                elif c == ')':
                    parens -= 1
                    if parens == 0:
                        args_end = i
                        break
                        
        if args_end != -1:
            atrib, obj, method = match.group(1), match.group(2), match.group(3)
            args = texto[m_start+1:args_end]
            linha = texto.count('\n', 0, m_start) + linha_offset
            resultados.append({
                'linha': linha,
                'atribuido_a': atrib,
                'objeto': obj or '',
                'metodo': method,
                'argumentos': args.replace('\n', ' '),
                'codigo_analisado': (match.group(0).replace('\n', ' ') + args.replace('\n', ' ') + ')')
            })
            pos = args_end + 1
        else:
            pos = match.end()
            
    return resultados


# ============================================================
# RESOLUCAO DE DEPENDENCIAS (.fj / Java -> Repositorios)
# ============================================================

def localizar_arquivo_repositorio(import_pacote, caminhos_repositorios):
    """
    Identifica de qual repositorio o pacote pertence e retorna o caminho fisico
    do arquivo .java correspondente no disco.

    Ordem de busca:
      1. plugins_api, function, bo (pelos prefixos de pacote conhecidos)
      2. projeto (o proprio diretorio sendo analisado) — fallback para qualquer
         import nao reconhecido pelos prefixos acima
    """
    if not import_pacote:
        return None

    repo_alvo = None

    prefixos_plugins_api = [
        "systextil.bo.inte.sysplan",
        "systextil.bo.sintegra",
        "systextil.erros",
        "systextil.intg.dto",
        "systextil.plugin",
        "systextil.services"
    ]

    for prefix in prefixos_plugins_api:
        if import_pacote.startswith(prefix):
            repo_alvo = caminhos_repositorios.get('plugins_api')
            break

    if not repo_alvo:
        if import_pacote.startswith("br.com.systextil.function") or import_pacote.startswith("systextil.function"):
            repo_alvo = caminhos_repositorios.get('function')
        elif import_pacote.startswith("br.com.systextil.bo") or import_pacote.startswith("systextil.bo"):
            repo_alvo = caminhos_repositorios.get('bo')

    # Fallback: busca no proprio projeto (arquivos Java do modulo sendo analisado)
    if not repo_alvo:
        repo_alvo = caminhos_repositorios.get('projeto')

    if not repo_alvo:
        return None

    caminho_relativo = import_pacote.replace(".", "/") + ".java"
    # Tenta multiplos layouts de codigo fonte antes de retornar o caminho padrao
    for base_src in ('src/main/java', 'src', 'sources'):
        candidato = Path(repo_alvo) / base_src / caminho_relativo
        if candidato.exists():
            return str(candidato)
    return str(Path(repo_alvo) / 'src' / 'main' / 'java' / caminho_relativo)


# ============================================================
# DETECCAO RT — procedures sem variante _rt
# ============================================================

def detectar_procedure_sem_rt(linhas_limpas):
    """
    Detecta chamadas SQL 'call <procedure>( ... )' dentro de strings Java.
    So escaneia blocos que contenham a palavra 'call' para evitar busca desnecessaria.
    Usa _e_coluna_cnpj() para validar parametros CNPJ (com word boundary).
    """
    erros = []
    pat_call = re.compile(r'\bcall\s+(\w+)', re.IGNORECASE)
    pat_frag = re.compile(r'"((?:[^"\\]|\\.)*)"')
    pat_call_rapido = re.compile(r'\bcall\b', re.IGNORECASE)

    already_reported = set()

    i = 0
    while i < len(linhas_limpas):
        if not pat_call_rapido.search(linhas_limpas[i]):
            i += 1
            continue

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

                param_words = re.findall(r'[a-z_][a-z0-9_]*', params_text, re.IGNORECASE)
                has_cnpj_param = any(_e_coluna_cnpj(w) for w in param_words)

                if has_cnpj_param:
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
# ANALISE DE ARQUIVO (RT-only)
# ============================================================

def analisar_arquivo(caminho_arquivo):
    """
    Le o arquivo, extrai imports/invocacoes/variaveis para analise RT,
    e detecta procedures SQL sem variante _rt.
    """
    try:
        with open(caminho_arquivo, "r", encoding="windows-1252") as f:
            texto_original = f.read()
    except Exception as e:
        print(f"  \u26a0 Erro ao ler {caminho_arquivo}: {e}")
        return None

    if len(texto_original.strip()) < 100:
        return None

    nome_arquivo = Path(caminho_arquivo).name
    texto_sem_comentarios = remover_comentarios(texto_original)
    texto_limpo = achatar_text_blocks(texto_sem_comentarios)
    linhas_limpas = texto_limpo.split('\n')

    erros = detectar_procedure_sem_rt(linhas_limpas)

    resultado = {
        "arquivo": nome_arquivo,
        "erros":   erros,
        "avisos":  [],
    }

    if nome_arquivo.endswith('.fj') or nome_arquivo.endswith('.java'):
        resultado["imports"]    = extrair_imports_fj(texto_limpo)
        resultado["invocacoes"] = extrair_invocacoes_fj(texto_limpo)
        resultado["variaveis"]  = extrair_variaveis_fj(texto_limpo)

    return resultado


# ============================================================
# RESOLUCAO DE BRANCHES (usado por analise.py)
# ============================================================

import subprocess as _subprocess


def _branch_existe(repo_path: str, nome: str) -> bool:
    r = _subprocess.run(
        ["git", "rev-parse", "--verify", nome],
        cwd=repo_path, capture_output=True
    )
    return r.returncode == 0


def _resolver_branch_principal(repo_path: str) -> str:
    """Detecta o branch principal: WEB, main, master, develop, trunk e suas variantes origin/."""
    candidatos_locais = ["WEB", "main", "master", "develop", "trunk"]
    candidatos_remotos = ["origin/" + c for c in candidatos_locais]

    for candidato in candidatos_locais + candidatos_remotos:
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
    """
    result_head = _subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        cwd=repo_path, capture_output=True, text=True
    )
    branch_atual = result_head.stdout.strip() if result_head.returncode == 0 else ""
    if branch_atual and "cnpj" in branch_atual.lower():
        return branch_atual

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

    if branch_atual == "HEAD" or branch_atual:
        return "HEAD"

    raise RuntimeError(
        f"Branch CNPJ nao encontrado em {repo_path}.\n"
        f"Tentados: {candidatos}\n"
        f"Verifique com: git branch -a"
    )


# ============================================================
# VERIFICACAO DE TIPAGEM ESTATICA (RT)
# ============================================================

def verificar_tipagem_estatica(hits: list, repos_aux: dict) -> tuple:
    """
    Verifica estaticamente (sem API) se invocacoes em .fj passam String/null onde
    o metodo Java espera int, cruzando com as assinaturas reais dos repositorios.

    Retorna (definitivos, possiveis):
      definitivos: string literal passado onde int esperado — certeza absoluta, sem Claude
      possiveis:   variavel ou null passado onde int esperado — ambiguo, envia ao Claude
                   com assinatura real embutida no contexto

    Cada item tem: arquivo, linha, codigo_analisado, objeto, metodo_alvo,
                   argumento_suspeito, tipo_argumento, assinatura_java,
                   variante_rt, metodo_substituto, severidade
    """
    definitivos   = []
    possiveis     = []
    sem_cobertura = []  # metodo/classe nao encontrado nos repos

    for h in hits:
        arquivo    = h.get('arquivo_original', h.get('arquivo', ''))
        imports    = h.get('imports', [])
        invocacoes = h.get('invocacoes', [])
        variaveis  = h.get('variaveis', {})

        if not imports or not invocacoes:
            continue

        # Monta cache: NomeSimplesDaClasse -> dict de assinaturas
        # Tambem rastreia quais nomes de classe vieram de imports reconhecidos
        # (mesmo que o arquivo nao exista no disco ainda)
        cache_sigs          = {}
        cache_caminhos      = {}  # NomeSimplesDaClasse -> caminho fisico do .java
        cache_import_pkg    = {}  # NomeSimplesDaClasse -> pacote importado completo
        classes_dos_imports = set()  # nomes simples de todas as classes importadas

        for imp in imports:
            nome_classe = imp.split('.')[-1]
            caminho = localizar_arquivo_repositorio(imp, repos_aux)
            if caminho:
                # Import reconhecido pelo prefixo — classe pertence a um dos repos
                classes_dos_imports.add(nome_classe)
                cache_caminhos[nome_classe] = caminho  # registra mesmo se nao existir no disco
                cache_import_pkg[nome_classe] = imp
                if Path(caminho).exists():
                    sigs = extrair_assinaturas_java(caminho)
                    if sigs:
                        cache_sigs[nome_classe] = sigs

        for inv in invocacoes:
            objeto   = inv.get('objeto', '')
            metodo   = inv.get('metodo', '')
            args_raw = inv.get('argumentos', '')

            if not objeto or not metodo:
                continue

            # Se ja estiver sendo envelopado como objeto CNPJ, nao e erro de tipagem RT
            if 'CNPJ.get(' in args_raw:
                continue
                
            # Se o metodo alvo ja e a variante RT documentada, nao precisamos fazer hook de tipagem
            if metodo.endswith('RT') or metodo.endswith('_rt'):
                continue

            args = [a.strip() for a in args_raw.split(',') if a.strip()]

            # Resolve tipo do objeto via mapa de variaveis ou tenta o proprio nome
            tipo_objeto = variaveis.get(objeto, objeto)
            sigs_classe = cache_sigs.get(tipo_objeto)

            # Fallback: busca por correspondencia parcial (ex: var "vendas" -> "VendasProvedor")
            if not sigs_classe:
                for nome_classe, sigs in cache_sigs.items():
                    if objeto.lower() in nome_classe.lower() or nome_classe.lower().startswith(objeto.lower()):
                        sigs_classe = sigs
                        tipo_objeto = nome_classe
                        break

            # Caminho fisico do .java dessa classe (pode nao existir no disco ainda)
            caminho_java = cache_caminhos.get(tipo_objeto)
            if not caminho_java:
                for nc, cp in cache_caminhos.items():
                    if tipo_objeto.lower() in nc.lower() or nc.lower().startswith(tipo_objeto.lower()):
                        caminho_java = cp
                        tipo_objeto  = nc
                        break

            import_pkg_tipo = cache_import_pkg.get(tipo_objeto)
            if not import_pkg_tipo:
                for nc, imp in cache_import_pkg.items():
                    if tipo_objeto.lower() in nc.lower() or nc.lower().startswith(tipo_objeto.lower()):
                        import_pkg_tipo = imp
                        break

            if _deve_ignorar_invocacao_tipagem(import_pkg_tipo, tipo_objeto, objeto, metodo):
                continue

            # Verifica se o tipo pertence a um import reconhecido mas sem arquivo no disco
            tipo_nos_imports = tipo_objeto in classes_dos_imports or bool(caminho_java)

            if not sigs_classe:
                # Se o tipo nao e de um import reconhecido, nao temos como avaliar
                if not tipo_nos_imports:
                    continue
                # Tipo e de um repo conhecido mas o arquivo nao foi encontrado no disco.
                # Reporta TODOS os argumentos com sufixo _r/_o.
                suspeitos_sc = []
                for arg in args:
                    tipo_arg = _classificar_arg(arg)
                    if tipo_arg == 'variavel' and _e_arg_cnpj_split(arg):
                        suspeitos_sc.append({'arg': arg, 'tipo': tipo_arg, 'e_cnpj_split': True})
                if suspeitos_sc:
                    sem_cobertura.append({
                        'arquivo':              arquivo,
                        'linha':                inv['linha'],
                        'codigo_analisado':     inv['codigo_analisado'],
                        'objeto':               objeto,
                        'metodo_alvo':          metodo,
                        'argumentos_suspeitos': suspeitos_sc,
                        'assinatura_java':      None,
                        'variante_rt':          None,
                        'metodo_substituto':    metodo + 'RT',
                        'caminho_java':         caminho_java,
                        'severidade':           'ADVERTENCIA',
                        'motivo':               'classe_nao_encontrada_nos_repos',
                    })
                continue

            overloads = sigs_classe.get(metodo, [])
            if not overloads:
                # Metodo nao existe na classe — reporta TODOS os args suspeitos
                suspeitos_sc = []
                for arg in args:
                    tipo_arg = _classificar_arg(arg)
                    if tipo_arg == 'variavel' and _e_arg_cnpj_split(arg):
                        suspeitos_sc.append({'arg': arg, 'tipo': tipo_arg, 'e_cnpj_split': True})
                if suspeitos_sc:
                    sem_cobertura.append({
                        'arquivo':              arquivo,
                        'linha':                inv['linha'],
                        'codigo_analisado':     inv['codigo_analisado'],
                        'objeto':               objeto,
                        'metodo_alvo':          metodo,
                        'argumentos_suspeitos': suspeitos_sc,
                        'assinatura_java':      None,
                        'variante_rt':          None,
                        'metodo_substituto':    metodo + 'RT',
                        'caminho_java':         caminho_java,
                        'severidade':           'ADVERTENCIA',
                        'motivo':               'metodo_nao_encontrado_no_repo',
                    })
                continue

            for overload in overloads:
                params = overload['params']
                has_varargs = params and params[-1].get('varargs', False)
                if params and not has_varargs and len(params) != len(args):
                    continue  # Aridade diferente, outro overload
                if params and has_varargs and len(args) < len(params) - 1:
                    continue  # Nem os parametros fixos foram fornecidos

                # Coleta TODOS os argumentos suspeitos deste overload
                suspeitos = []
                for idx, param in enumerate(params):
                    if param['tipo'] not in _TIPOS_NUMERICOS:
                        continue
                    if idx >= len(args):
                        continue
                    tipo_arg = _classificar_arg(args[idx])
                    if tipo_arg in ('cast_int', 'parse_int', 'int_literal', 'vazio'):
                        continue
                    e_cnpj_split = tipo_arg == 'variavel' and _e_arg_cnpj_split(args[idx])
                    suspeitos.append({
                        'idx':          idx,
                        'arg':          args[idx],
                        'tipo':         tipo_arg,
                        'e_cnpj_split': e_cnpj_split,
                    })

                if not suspeitos:
                    continue  # Nenhum argumento suspeito neste overload

                # Verifica overload CNPJ e variante RT (uma vez por invocacao)
                sobreposicoes_mesmo_nome = sigs_classe.get(metodo, [])
                sig_cnpj = None
                for o_same in sobreposicoes_mesmo_nome:
                    p_same = o_same['params']
                    if len(p_same) == 1 and p_same[0]['tipo'].upper() == 'CNPJ':
                        sig_cnpj = o_same
                        break

                metodo_rt = metodo + 'RT'
                rt_sigs = sigs_classe.get(metodo_rt) or sigs_classe.get(metodo + '_rt')

                params_str = ', '.join(f"{p['tipo']} {p['nome']}".strip() for p in params)
                assinatura = f"{overload['retorno']} {metodo}({params_str})"

                variante_rt_str = None
                metodo_substituto = None

                if sig_cnpj:
                    cnpj_ps = ', '.join(f"{p['tipo']} {p['nome']}".strip() for p in sig_cnpj['params'])
                    variante_rt_str = f"{sig_cnpj['retorno']} {metodo}({cnpj_ps})"
                    motivo = 'usar_objeto_cnpj'
                    metodo_substituto = metodo
                elif rt_sigs:
                    rt_ps = ', '.join(f"{p['tipo']} {p['nome']}".strip() for p in rt_sigs[0]['params'])
                    nome_rt = metodo_rt if sigs_classe.get(metodo_rt) else metodo + '_rt'
                    variante_rt_str = f"{rt_sigs[0]['retorno']} {nome_rt}({rt_ps})"
                    motivo = 'usar_variante_rt'
                    metodo_substituto = nome_rt
                else:
                    motivo = 'criar_variante_rt_ou_cnpj'

                e_definitivo = any(
                    s['tipo'] == 'string_literal' or s['e_cnpj_split']
                    for s in suspeitos
                )

                # Se ja existe evidencia definitiva na chamada, nao poluir o item
                # com variaveis ambiguas sem sufixo CNPJ (ex: cgc2).
                if e_definitivo:
                    suspeitos = [
                        s for s in suspeitos
                        if s['tipo'] == 'string_literal' or s['e_cnpj_split']
                    ]

                item = {
                    'arquivo':              arquivo,
                    'linha':                inv['linha'],
                    'codigo_analisado':     inv['codigo_analisado'],
                    'objeto':               objeto,
                    'metodo_alvo':          metodo,
                    'argumentos_suspeitos': suspeitos,
                    'assinatura_java':      assinatura,
                    'variante_rt':          variante_rt_str,
                    'metodo_substituto':    metodo_substituto,
                    'caminho_java':         caminho_java,
                    'severidade':           'CRITICO' if e_definitivo and (rt_sigs or sig_cnpj) else 'ADVERTENCIA',
                    'motivo':               motivo,
                }

                if e_definitivo:
                    definitivos.append(item)
                else:
                    possiveis.append(item)
                break  # Primeiro overload com suspeitos — um item por invocacao

    return definitivos, possiveis, sem_cobertura
