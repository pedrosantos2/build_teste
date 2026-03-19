# =============================================================================
# claude_analyzer.py — Chama a API do Claude em lotes
# Maximo de LOTE_MAXIMO hits por chamada para nao estourar o output
# =============================================================================

import json
from pathlib import Path
from typing import List, Dict, Any

import anthropic

LOTE_MAXIMO = 50  # itens por chamada — ajustar se necessario


def _carregar_skill(skill_path: str) -> str:
    return Path(skill_path).read_text(encoding="utf-8")


def _carregar_exemplos(exemplos_dir: str) -> str:
    dir_path = Path(exemplos_dir)
    if not dir_path.exists():
        return ""

    partes = []
    for antes in sorted(dir_path.glob("*.antes")):
        nome_base = antes.stem
        depois    = antes.with_suffix(".depois")

        bloco = [f"### {nome_base}"]
        bloco.append("**COM BUG:**")
        bloco.append("```java")
        bloco.append(antes.read_text(encoding="utf-8", errors="replace").strip())
        bloco.append("```")

        if depois.exists():
            bloco.append("**CORRIGIDO:**")
            bloco.append("```java")
            bloco.append(depois.read_text(encoding="utf-8", errors="replace").strip())
            bloco.append("```")

        partes.append("\n".join(bloco))

    return "\n\n".join(partes)


def _chamar_api(client, modulo: str, hits_lote: list,
                skill: str, exemplos: str,
                numero_lote: int, total_lotes: int) -> dict:
    """Envia um lote de hits e retorna o JSON parseado."""

    prompt = f"""Analise os candidatos abaixo (lote {numero_lote}/{total_lotes}) da migracao CNPJ do modulo **{modulo}**.

IMPORTANTE:
- Responda SOMENTE com base nas informacoes fornecidas abaixo
- NAO tente executar comandos, acessar arquivos ou buscar informacoes externas
- NAO use ferramentas — analise apenas o contexto ja fornecido em cada item
- Se o contexto for insuficiente para confirmar, classifique como FALSO_POSITIVO
- BUG_1 (dualidade INSERT/builder): so e CRITICO se a tabela estiver na lista TABELAS_DUALIDADE
  Se o contexto nao mencionar explicitamente uma tabela de dualidade, classificar como FALSO_POSITIVO

Para cada item:
1. Confirme se e bug real ou falso positivo usando APENAS o contexto fornecido
2. Classificacao de severidade por pre_existente:
   - pre_existente=false + qualquer bug CNPJ → CRITICO
   - pre_existente=true + bug de codigo CNPJ legado (cgc_9, cgc_4, getInt em _r/_o, etc) → CRITICO (arquivo nao migrado)
   - pre_existente=true + bug estrutural SEM relacao com CNPJ (mismatch de placeholders SQL, logica AND/OR errada, NPE generico, etc) → ADVERTENCIA
3. Sugira a correcao
   - Para bugs de dualidade (BUG_1): diga apenas que precisa duplicar a coluna, sem sugerir Integer.parseInt ou conversao numerica
   - A duplicacao e feita adicionando a coluna legada no INSERT com o mesmo valor da nova coluna — o sistema ja faz a conversao internamente
   - Exemplo correto: "Adicionar 'tran_cli_forne9' e 'tran_cli_forne4' no INSERT junto com 'tran_cli_forne_r' e 'tran_cli_forne_o'"
   - Nao sugerir Integer.parseInt, conversao de tipo ou casting em correcoes de dualidade

Responda SOMENTE com JSON valido, sem markdown, sem texto adicional:
{{
  "bugs": [
    {{
      "arquivo":    "...",
      "linha":      0,
      "tipo":       "...",
      "severidade": "CRITICO|MEDIO|BAIXO|SUGESTAO|ADVERTENCIA|FALSO_POSITIVO",
      "descricao":  "...",
      "correcao":   "..."
    }}
  ]
}}

CANDIDATOS ({len(hits_lote)} itens):
{json.dumps(hits_lote, ensure_ascii=False, indent=2)}"""

    response = client.messages.create(
        model      = "claude-sonnet-4-6",
        max_tokens = 8096,
        system     = [
            {
                "type": "text",
                "text": skill,
                "cache_control": {"type": "ephemeral"},
            },
            {
                "type": "text",
                "text": f"## Exemplos de referencia\n\n{exemplos}",
                "cache_control": {"type": "ephemeral"},
            },
        ],
        messages=[{"role": "user", "content": prompt}],
    )

    raw = response.content[0].text.strip() if response.content else ""

    if not raw:
        print(f"      ERRO: API retornou resposta vazia. Stop reason: {response.stop_reason}")
        print(f"      Usage: input={response.usage.input_tokens} output={response.usage.output_tokens}")
        raise json.JSONDecodeError("Resposta vazia da API", "", 0)

    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1]
    if raw.endswith("```"):
        raw = raw.rsplit("```", 1)[0]

    raw = raw.strip()
    try:
        resultado = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"      ERRO parse JSON: {e}")
        print(f"      Raw (primeiros 500 chars): {raw[:500]!r}")
        raise

    return resultado, response.usage


def analisar(
    modulo:       str,
    hits:         List[Dict[str, Any]],
    skill_path:   str,
    exemplos_dir: str,
) -> dict:
    """
    Envia hits em lotes para o Claude e consolida os resultados.
    Evita estouro de tokens de output.
    """
    client   = anthropic.Anthropic()
    skill    = _carregar_skill(skill_path)
    exemplos = _carregar_exemplos(exemplos_dir)

    # Divide em lotes
    lotes = [hits[i:i + LOTE_MAXIMO] for i in range(0, len(hits), LOTE_MAXIMO)]
    total_lotes = len(lotes)

    print(f"      {len(hits)} itens divididos em {total_lotes} lote(s) de ate {LOTE_MAXIMO}")

    todos_bugs = []
    usage_total = {"input_tokens": 0, "output_tokens": 0,
                   "cache_creation_tokens": 0, "cache_read_tokens": 0}

    for i, lote in enumerate(lotes, 1):
        print(f"      Lote {i}/{total_lotes} ({len(lote)} itens)...")
        try:
            resultado_lote, usage = _chamar_api(
                client, modulo, lote, skill, exemplos, i, total_lotes
            )
            todos_bugs.extend(resultado_lote.get("bugs", []))
            usage_total["input_tokens"]          += usage.input_tokens
            usage_total["output_tokens"]         += usage.output_tokens
            usage_total["cache_creation_tokens"] += getattr(usage, "cache_creation_input_tokens", 0)
            usage_total["cache_read_tokens"]     += getattr(usage, "cache_read_input_tokens", 0)
        except json.JSONDecodeError as e:
            print(f"      AVISO: lote {i} retornou JSON invalido ({e}) — pulando")
            continue
        except Exception as e:
            print(f"      AVISO: lote {i} falhou ({e}) — pulando")
            continue

    # Consolida resumo
    resumo = {
        "criticos":         sum(1 for b in todos_bugs if b.get("severidade") == "CRITICO"),
        "medios":           sum(1 for b in todos_bugs if b.get("severidade") == "MEDIO"),
        "baixos":           sum(1 for b in todos_bugs if b.get("severidade") == "BAIXO"),
        "sugestoes":        sum(1 for b in todos_bugs if b.get("severidade") == "SUGESTAO"),
        "advertencias":     sum(1 for b in todos_bugs if b.get("severidade") == "ADVERTENCIA"),
        "falsos_positivos": sum(1 for b in todos_bugs if b.get("severidade") == "FALSO_POSITIVO"),
    }

    return {
        "modulo":  modulo,
        "bugs":    todos_bugs,
        "resumo":  resumo,
        "_usage":  usage_total,
    }