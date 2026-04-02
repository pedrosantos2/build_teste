# =============================================================================
# claude_analyzer.py — Analise de tipagem RT via Claude API
# Versao RT-only: apenas verificacao de incompatibilidades String/int (RT).
# =============================================================================

import json
import time
from typing import List, Dict, Any

import anthropic


def _extrair_json_da_resposta(raw_texto: str) -> str:
  """
  Extrai o primeiro objeto JSON valido do texto retornado pelo modelo.
  Aceita respostas com ou sem bloco markdown.
  """
  raw = raw_texto.strip()
  if raw.startswith("```json"):
    raw = raw[7:]
  if raw.startswith("```"):
    raw = raw[3:]
  if raw.endswith("```"):
    raw = raw[:-3]
  raw = raw.strip()

  if raw.startswith("{") and raw.endswith("}"):
    return raw

  inicio = raw.find("{")
  if inicio < 0:
    return raw

  nivel = 0
  em_string = False
  escape = False
  for i in range(inicio, len(raw)):
    c = raw[i]
    if escape:
      escape = False
      continue
    if c == "\\":
      escape = True
      continue
    if c == '"':
      em_string = not em_string
      continue
    if em_string:
      continue
    if c == "{":
      nivel += 1
    elif c == "}":
      nivel -= 1
      if nivel == 0:
        return raw[inicio:i + 1]

  return raw


def _normalizar_inconsistencias(payload: dict, lote: list) -> dict:
  """
  Normaliza a saida do Claude para o schema publico do pipeline.

  Formato preferencial (novo):
    {"inconsistencias": [{"idx": 0, "severidade": "CRITICO", "metodo_substituto": "buscarRT"}]}

  Formato legado (aceito por compatibilidade):
    {"inconsistencias": [{"arquivo": "...", ...}]}
  """
  incs = payload.get("inconsistencias", [])
  if not isinstance(incs, list):
    return {"inconsistencias": []}

  # Compatibilidade: se ja veio no formato completo, devolve como esta.
  if incs and isinstance(incs[0], dict) and "arquivo" in incs[0]:
    return {"inconsistencias": incs}

  normalizadas = []
  for item in incs:
    if not isinstance(item, dict):
      continue

    idx = item.get("idx")
    if not isinstance(idx, int) or idx < 0 or idx >= len(lote):
      continue

    severidade = str(item.get("severidade", "ADVERTENCIA")).upper()
    if severidade not in {"CRITICO", "ADVERTENCIA", "FALSO_POSITIVO"}:
      continue

    base = lote[idx]
    metodo_substituto = item.get("metodo_substituto", base.get("metodo_substituto"))
    args_suspeitos = [
      s.get("arg", "") for s in base.get("argumentos_suspeitos", [])
      if isinstance(s, dict)
    ]

    normalizadas.append({
      "arquivo": base.get("arquivo", ""),
      "linha": base.get("linha", 0),
      "codigo_analisado": base.get("codigo_analisado", ""),
      "chamada": {
        "objeto": base.get("objeto", ""),
        "metodo_alvo": base.get("metodo_alvo", ""),
        "argumentos_passados": ", ".join(a for a in args_suspeitos if a),
      },
      "correcao_sugerida": {
        "aplicar_conversao": True,
        "metodo_substituto": metodo_substituto,
      },
      "severidade": severidade,
    })

  return {"inconsistencias": normalizadas}


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

Retorne EXCLUSIVAMENTE JSON valido, sem texto adicional, no formato:
{{
  "inconsistencias": [
    {{
      "idx": <indice_do_caso_no_lote>,
      "severidade": "CRITICO|ADVERTENCIA|FALSO_POSITIVO",
      "metodo_substituto": "<Metodo Alternativo ou null>",
      "justificativa": "<curta>"
    }}
  ]
}}

IMPORTANTE:
- Use apenas o campo idx para identificar o caso.
- Nao repita codigo_analisado nem outros campos de entrada no output.
- Nao use comentarios, markdown, trailing commas ou texto fora do JSON.
- Se nao houver inconsistencias, retorne:
  {{
    "inconsistencias": []
  }}

CASOS — lote {numero_lote}/{total_lotes}:
"""

    casos_enxutos = []
    for idx, c in enumerate(lote):
        casos_enxutos.append({
            "idx": idx,
            "pre_classificacao": c.get("pre_classificacao"),
            "arquivo": c.get("arquivo"),
            "linha": c.get("linha"),
            "codigo_analisado": c.get("codigo_analisado"),
            "objeto": c.get("objeto"),
            "metodo_alvo": c.get("metodo_alvo"),
            "assinatura_java": c.get("assinatura_java"),
            "variante_rt": c.get("variante_rt"),
            "argumentos_suspeitos": c.get("argumentos_suspeitos", []),
            "metodo_substituto_sugerido": c.get("metodo_substituto"),
        })

    prompt += json.dumps(casos_enxutos, indent=2, ensure_ascii=False)

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2048,
        temperature=0,
        messages=[{"role": "user", "content": prompt}]
    )

    raw = _extrair_json_da_resposta(response.content[0].text)
    parsed = json.loads(raw.strip())
    normalizado = _normalizar_inconsistencias(parsed, lote)

    return normalizado, response.usage


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
