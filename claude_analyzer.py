# =============================================================================
# claude_analyzer.py — Analise de tipagem RT via Claude API
# Versao RT-only: apenas verificacao de incompatibilidades String/int (RT).
# =============================================================================

import json
import time
from typing import List, Dict, Any

import anthropic


def _chamar_api_tipagem(client, lote: list, numero_lote: int, total_lotes: int) -> dict:
    """
    Envia ao Claude todos os casos de tipagem suspeita (definitivos + ambiguos),
    ja com pre_classificacao da analise estatica, para validacao final.
    """
    prompt = f"""Role: Analisador de Tipagem Java/.fj.

Cada caso abaixo representa uma chamada de metodo em arquivo .fj onde um argumento
e passado a um parametro que a assinatura Java declara como int/Integer/long.

O campo `pre_classificacao` indica o resultado da analise estatica previa:
  - "ERRO": analise estatica identificou com alta confianca que e String passada onde
            int esperado (ex: literal de string, variavel com sufixo _r/_o que indica
            CNPJ alfanumerico dividido armazenado como String)
  - "POSSIVEL": caso ambiguo — tipo da variavel nao pode ser determinado estaticamente

Sua tarefa: revisar cada caso e determinar a severidade final.

Campos por caso:
  - pre_classificacao    : classificacao estatica previa (ERRO ou POSSIVEL)
  - codigo_analisado     : linha exata do .fj com a chamada completa
  - assinatura_java      : assinatura real do metodo no repositorio Java (pode ser null)
  - variante_rt          : assinatura da variante RT ou overload CNPJ disponivel (pode ser null)
  - argumentos_suspeitos : lista de todos os argumentos suspeitos da chamada, cada um com:
                           idx (posicao na chamada), arg (nome da variavel), tipo,
                           e_cnpj_split (true se sufixo _r/_o — indica String de CNPJ dividido)

REGRAS:
1. Se pre_classificacao="ERRO" e a analise faz sentido → severidade "CRITICO"
2. Se pre_classificacao="ERRO" mas parece falso positivo → severidade "FALSO_POSITIVO"
3. Se pre_classificacao="POSSIVEL" e ha evidencia de String onde int esperado → "ADVERTENCIA"
4. Se pre_classificacao="POSSIVEL" e nao ha evidencia suficiente → NAO inclua no resultado
5. NAO REPORTAR se houver cast explicito no codigo_analisado: (int), Integer.parseInt, etc.
6. Se variante_rt for null (sem alternativa RT ou objeto CNPJ), reporte mas sem metodo_substituto.

Retorne EXCLUSIVAMENTE JSON valido, sem texto adicional:
{{
  "inconsistencias": [
    {{
      "arquivo": "<caminho>",
      "linha": <numero>,
      "codigo_analisado": "<codigo>",
      "chamada": {{
        "objeto": "<obj>",
        "metodo_alvo": "<metodo>",
        "argumentos_passados": "<arg>"
      }},
      "correcao_sugerida": {{
        "aplicar_conversao": true,
        "metodo_substituto": "<Metodo Alternativo ou null>"
      }},
      "severidade": "CRITICO|ADVERTENCIA|FALSO_POSITIVO"
    }}
  ]
}}

CASOS — lote {numero_lote}/{total_lotes}:
{json.dumps(lote, indent=2, ensure_ascii=False)}
"""

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2048,
        temperature=0,
        messages=[{"role": "user", "content": prompt}]
    )

    raw = response.content[0].text.strip()
    if raw.startswith("```json"):
        raw = raw[7:]
    if raw.startswith("```"):
        raw = raw[3:]
    if raw.endswith("```"):
        raw = raw[:-3]

    return json.loads(raw.strip()), response.usage


def analisar_tipagem(hits: List[Dict[str, Any]], repos_aux: dict = None) -> dict:
    """
    Detecta incompatibilidades de tipagem (String passada onde int esperado) em dois passos:

    Passo 1 — Estatico (zero tokens):
      Cruza as invocacoes do .fj com as assinaturas Java reais dos repositorios.
      Classifica cada caso como ERRO (definitivo) ou POSSIVEL (ambiguo) e adiciona
      o campo pre_classificacao para orientar o Claude.

    Passo 2 — Claude para todos os casos:
      Envia todos os casos (definitivos + ambiguos + sem cobertura) ao Claude para
      validacao e determinacao final da severidade (CRITICO, ADVERTENCIA ou FALSO_POSITIVO).
    """
    import grep_engine

    repos_aux   = repos_aux or {}
    usage_total = {"input_tokens": 0, "output_tokens": 0}

    # --- Passo 1: analise estatica ---
    definitivos, possiveis, sem_cobertura = grep_engine.verificar_tipagem_estatica(hits, repos_aux)

    for item in definitivos:
        item['pre_classificacao'] = 'ERRO'
    for item in possiveis:
        item['pre_classificacao'] = 'POSSIVEL'
    for item in sem_cobertura:
        item['pre_classificacao'] = 'POSSIVEL'

    todos_para_claude = definitivos + possiveis + sem_cobertura

    if not todos_para_claude:
        print(f"      [Tipagem] Nenhuma invocacao cruzou com assinaturas dos repositorios — nada a verificar.")
        return {"inconsistencias": [], "_usage": usage_total}

    n_def = len(definitivos)
    n_pos = len(possiveis)
    n_sem = len(sem_cobertura)
    print(f"      [Tipagem] {len(todos_para_claude)} caso(s) enviados ao Claude "
          f"({n_def} definitivo(s), {n_pos} ambiguo(s), {n_sem} sem cobertura)...")

    # --- Passo 2: Claude valida todos os casos ---
    client = anthropic.Anthropic()

    LOTE_TIPAGEM = 20
    lotes       = [todos_para_claude[i:i + LOTE_TIPAGEM] for i in range(0, len(todos_para_claude), LOTE_TIPAGEM)]
    total_lotes = len(lotes)

    todas_inconsistencias = []
    for i, lote in enumerate(lotes, 1):
        print(f"      [Tipagem] Lote {i}/{total_lotes} ({len(lote)} casos)...")
        tentativas = 0
        while tentativas < 3:
            try:
                res, usage = _chamar_api_tipagem(client, lote, i, total_lotes)
                todas_inconsistencias.extend(res.get("inconsistencias", []))
                usage_total["input_tokens"]  += usage.input_tokens
                usage_total["output_tokens"] += usage.output_tokens
                break
            except json.JSONDecodeError as e:
                print(f"      [Tipagem] AVISO: lote {i} retornou JSON invalido ({e}) — pulando")
                break
            except Exception as e:
                msg = str(e).lower()
                if "429" in msg or "rate" in msg or "529" in msg or "overloaded" in msg:
                    espera = 15 * (2 ** tentativas)
                    print(f"      [Tipagem] API indisponivel. Aguardando {espera}s para retentar (tentativa {tentativas+1}/3)...")
                    time.sleep(espera)
                    tentativas += 1
                else:
                    print(f"      [Tipagem] AVISO: lote {i} falhou ({e})")
                    break

    return {"inconsistencias": todas_inconsistencias, "_usage": usage_total}
