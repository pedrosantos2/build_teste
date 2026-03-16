# =============================================================================
# claude_analyzer.py — Chama a API do Claude com skill + exemplos cacheados
# =============================================================================

import json
from pathlib import Path
import anthropic


def _carregar_skill(skill_path: str) -> str:
    return Path(skill_path).read_text(encoding="utf-8")


def _carregar_exemplos(exemplos_dir: str) -> str:
    """
    Lê pares .antes / .depois da pasta exemplos/.
    Estrutura:
      exemplos/
        efic_e450.java.antes
        efic_e450.java.depois
        inte_f140.java.antes
        inte_f140.java.depois
    """
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


def analisar(
    modulo:       str,
    hits:         list[dict],
    skill_path:   str,
    exemplos_dir: str,
) -> dict:
    """
    Envia apenas os hits (não o repositório inteiro) pro Claude.
    System prompt = skill .md + exemplos de referência (ambos cacheados).
    """
    client   = anthropic.Anthropic()
    skill    = _carregar_skill(skill_path)
    exemplos = _carregar_exemplos(exemplos_dir)

    # Serializa hits removendo campos desnecessários para economizar tokens
    # hits ja chegam como list[dict] do analise.py
    hits_payload = hits

    prompt_usuario = f"""Analise os candidatos abaixo encontrados na migração CNPJ do módulo **{modulo}**.

Para cada item:
1. Confirme se é bug real ou falso positivo usando o contexto fornecido
2. Se `pre_existente: true` → severidade máxima é ADVERTENCIA (bug já existia no WEB)
3. Para `tabela_dualidade` → verifique se as colunas CNPJ usadas nessa tabela estão corretas
4. Baseie as correções sugeridas nos exemplos de referência

Responda SOMENTE com JSON válido, sem markdown, neste formato:
{{
  "modulo": "{modulo}",
  "bugs": [
    {{
      "arquivo":    "...",
      "linha":      0,
      "tipo":       "...",
      "severidade": "CRITICO|MEDIO|BAIXO|SUGESTAO|ADVERTENCIA|FALSO_POSITIVO",
      "descricao":  "...",
      "correcao":   "..."
    }}
  ],
  "resumo": {{
    "criticos":        0,
    "medios":          0,
    "baixos":          0,
    "sugestoes":       0,
    "advertencias":    0,
    "falsos_positivos": 0
  }}
}}

CANDIDATOS ({len(hits_payload)} itens):
{json.dumps(hits_payload, ensure_ascii=False, indent=2)}"""

    response = client.messages.create(
        model      = "claude-sonnet-4-6",
        max_tokens = 8096,
        system     = [
            {
                # Skill .md — regras de análise — cacheada entre execuções
                "type": "text",
                "text": skill,
                "cache_control": {"type": "ephemeral"},
            },
            {
                # Exemplos de bugs reais de módulos anteriores — cacheados
                "type": "text",
                "text": f"## Exemplos de referência (bugs confirmados em módulos anteriores)\n\n{exemplos}",
                "cache_control": {"type": "ephemeral"},
            },
        ],
        messages=[{"role": "user", "content": prompt_usuario}],
    )

    raw = response.content[0].text.strip()

    # Remove eventuais blocos ```json ``` que o modelo possa ter adicionado
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1]
    if raw.endswith("```"):
        raw = raw.rsplit("```", 1)[0]

    resultado           = json.loads(raw.strip())
    resultado["_usage"] = {
        "input_tokens":         response.usage.input_tokens,
        "output_tokens":        response.usage.output_tokens,
        "cache_creation_tokens": getattr(response.usage, "cache_creation_input_tokens", 0),
        "cache_read_tokens":    getattr(response.usage, "cache_read_input_tokens", 0),
    }

    return resultado