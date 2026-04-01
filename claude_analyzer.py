# =============================================================================
# claude_analyzer.py — Analise de tipagem RT via Claude API
# Versao RT-only: apenas verificacao de incompatibilidades String/int (RT).
# =============================================================================

import json
import time
from typing import List, Dict, Any

import anthropic


def _chamar_api_tipagem(client, lote_possiveis: list, numero_lote: int, total_lotes: int) -> dict:
    """
    Envia ao Claude apenas casos ambiguos (variaveis cujo tipo nao pode ser determinado
    estaticamente), ja enriquecidos com a assinatura Java real do metodo.
    """
    prompt = f"""Role: Analisador de Tipagem Java/.fj.

Cada caso abaixo representa uma chamada de metodo em um arquivo .fj onde um argumento
de tipo incerto (nome de variavel) e passado a um parametro que a assinatura Java real
declara como int/Integer/long.

Sua tarefa: determinar se o argumento e provavelmente uma String (ou null incompativel
com int primitivo), configurando um erro de tipagem que exige uso da variante RT.

Campos por caso:
  - codigo_analisado : linha exata do .fj
  - assinatura_java  : assinatura real do metodo no repositorio Java
  - variante_rt      : assinatura da variante RT (se existir)
  - argumento_suspeito : argumento especifico em analise (nome de variavel)

REGRAS ESTRITAS:
1. REPORTAR se o argumento termina em _r ou _o (ex: cnpj_r, cgc_fornec_r, cnpj_cli_o) E
   a assinatura Java espera int/Integer → CRITICO se variante_rt existir, ADVERTENCIA caso contrario.
   Esses sufixos indicam CNPJ alfanumerico dividido (raiz/_r e ordem/_o) armazenado como String.
2. REPORTAR se o nome da variavel contem cnpj, cgc, ou termina em _cnpj/_cgc/_str/_s
   E a assinatura espera int → ADVERTENCIA
3. REPORTAR se o argumento for null E o parametro for int primitivo (nao Integer) → ADVERTENCIA
4. NAO REPORTAR se houver cast explicito no codigo_analisado: (int), Integer.parseInt, etc.
5. NAO REPORTAR se nao for possivel determinar o tipo com razoavel confianca.
6. Se variante_rt for null (sem alternativa RT), ainda assim reporte mas sem metodo_substituto.

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
        "aplicar_sufixo_rt": true,
        "metodo_substituto": "<MetodoRT ou null>"
      }},
      "severidade": "ADVERTENCIA"
    }}
  ]
}}

CASOS AMBIGUOS — lote {numero_lote}/{total_lotes}:
{json.dumps(lote_possiveis, indent=2, ensure_ascii=False)}
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
      Casos definitivos (string literal onde int esperado) sao reportados diretamente.

    Passo 2 — Claude apenas para casos ambiguos (variaveis):
      Envia somente os casos onde o tipo do argumento e incerto, mas com a assinatura
      Java real embutida no contexto — prompts muito menores e mais precisos.
    """
    import grep_engine

    repos_aux   = repos_aux or {}
    usage_total = {"input_tokens": 0, "output_tokens": 0}
    todas_inconsistencias = []

    # --- Passo 1: analise estatica gratuita ---
    definitivos, possiveis = grep_engine.verificar_tipagem_estatica(hits, repos_aux)

    for item in definitivos:
        todas_inconsistencias.append({
            "arquivo":          item["arquivo"],
            "linha":            item["linha"],
            "codigo_analisado": item["codigo_analisado"],
            "chamada": {
                "objeto":              item["objeto"],
                "metodo_alvo":         item["metodo_alvo"],
                "argumentos_passados": item["argumento_suspeito"],
            },
            "correcao_sugerida": {
                "aplicar_sufixo_rt": item["metodo_substituto"] is not None,
                "metodo_substituto": item["metodo_substituto"],
            },
            "assinatura_detectada": item["assinatura_java"],
            "variante_rt":          item["variante_rt"],
            "severidade":           item["severidade"],
            "origem":               "estatico",
        })

    if definitivos:
        print(f"      [Tipagem] {len(definitivos)} incompatibilidade(s) definitiva(s) detectada(s) estaticamente (0 tokens).")

    if not possiveis:
        if not definitivos:
            print(f"      [Tipagem] Nenhuma invocacao cruzou com assinaturas dos repositorios — nada a verificar.")
        return {"inconsistencias": todas_inconsistencias, "_usage": usage_total}

    # --- Passo 2: Claude apenas para casos ambiguos ---
    print(f"      [Tipagem] {len(possiveis)} caso(s) ambiguo(s) (variaveis) enviados ao Claude com assinaturas reais...")

    client = anthropic.Anthropic()

    LOTE_TIPAGEM = 20
    lotes       = [possiveis[i:i + LOTE_TIPAGEM] for i in range(0, len(possiveis), LOTE_TIPAGEM)]
    total_lotes = len(lotes)

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
