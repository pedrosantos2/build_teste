# =============================================================================
# claude_analyzer.py — Chama a API do Claude em lotes
# Maximo de LOTE_MAXIMO hits por chamada para nao estourar o output
# =============================================================================

import json
import re
import time
from pathlib import Path
from typing import List, Dict, Any

import anthropic

LOTE_MAXIMO = 20  # Reduzido de 50 para 20 para evitar truncamento de JSON (max_tokens)


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
- NAO INVENTE bugs que nao estao nos candidatos. Retorne EXATAMENTE um resultado para cada candidato enviado.
  Se o candidato mostra codigo que JA FOI MIGRADO corretamente (usa _r/_o em vez de _9/_4), classifique como FALSO_POSITIVO.
  Nunca deduza que existia uma coluna legada so porque ve a versao nova — analise apenas o que esta no contexto.
- Se o contexto for insuficiente para confirmar, classifique como FALSO_POSITIVO
- BUG_1 (dualidade INSERT/builder): so e CRITICO se a tabela estiver na lista TABELAS_DUALIDADE
  Se o contexto nao mencionar explicitamente uma tabela de dualidade, classificar como FALSO_POSITIVO
- BUG_LEGADO em arquivos .fj: SQL em blocos EXEC SQL usando colunas legadas (cgc_9, cgc_4) sem
  versao nova (cgc_r, cgc_o) e CRITICO — correcao e substituir a coluna legada pela nova
- CAMPO_NUMERICO_CNPJ: FIELD campo_numerico* usado para CNPJ em .fj e ADVERTENCIA —
  correcao e alterar para campo descricao (String) pois CNPJ agora e VARCHAR2.
  Nem todo campo_numerico e CNPJ — so os que extendem widgets CNPJ, recebem CNPJ.ZEROS
  ou tem SQL com colunas CNPJ. campo_numerico* sem relacao CNPJ e FALSO_POSITIVO
- IMPORTANTE: Se o candidate type for BUG_DTO_BRIDGE_LEGADO, BUG_VARIAVEL_LEGADA ou BUG_VARIAVEL_LEGADA_DEPRECATED, a severidade DEVE ser OBRIGATORIAMENTE **ADVERTENCIA** (nunca CRITICO), pois e um padrao aceito ou em depreciacao.

Para cada item:
1. Confirme se e bug real ou falso positivo usando APENAS o contexto fornecido
2. Classificacao de severidade por pre_existente:
   - Se for BUG_DTO_BRIDGE_LEGADO, BUG_VARIAVEL_LEGADA ou BUG_VARIAVEL_LEGADA_DEPRECATED → ADVERTENCIA.
   - pre_existente=false + qualquer outro bug CNPJ → CRITICO
   - pre_existente=true + bug de codigo CNPJ legado (cgc_9, cgc_4, parseInt em _r, getInt em _r/_o, etc) → ADVERTENCIA (arquivo nao migrado)
   - pre_existente=true + bug estrutural SEM relacao com CNPJ (mismatch de placeholders SQL, logica AND/OR errada, NPE generico, etc) → ADVERTENCIA
3. Sugira a correcao
   - Para bugs de dualidade (BUG_1): diga apenas que precisa duplicar a coluna, sem sugerir Integer.parseInt ou conversao numerica
   - A duplicacao e feita adicionando a coluna legada no INSERT com o mesmo valor da nova coluna — o sistema ja faz a conversao internamente
   - Exemplo correto: "Adicionar 'tran_cli_forne9' e 'tran_cli_forne4' no INSERT junto com 'tran_cli_forne_r' e 'tran_cli_forne_o'"
   - Nao sugerir Integer.parseInt, conversao de tipo ou casting em correcoes de dualidade
   - Para BUG_LEGADO em .fj: correcao e substituir coluna legada pela nova no EXEC SQL (ex: cgc_9 -> cgc_r)
   - Para CAMPO_NUMERICO_CNPJ: correcao e trocar campo_numerico* por descricao* (String) no FIELD e em todas as referencias do formulario
   - SEJA CONCISO nas descricoes e correcoes (max 1 a 2 frases).

REGRA CRITICA: Retorne APENAS bugs para os candidatos listados abaixo.
NAO adicione bugs para arquivos ou colunas que nao estao nos candidatos.
Se um candidato tem {len(hits_lote)} itens, o JSON deve ter no maximo {len(hits_lote)} bugs.

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

    # Remove markdown wrapper se o modelo adicionou
    if '```' in raw:
        raw = re.sub(r'```(?:json)?\s*', '', raw)

    # Extrai o JSON do texto — pega do primeiro { ao ultimo }
    inicio = raw.find('{')
    fim = raw.rfind('}')
    if inicio != -1 and fim != -1 and fim > inicio:
        raw = raw[inicio:fim + 1]

    raw = raw.strip()
    try:
        resultado = json.loads(raw)
        
        # FINAL OVERRIDE: Garantir que Claude nunca retorne como CRITICO
        if "bugs" in resultado:
            for b in resultado["bugs"]:
                if b.get("candidate") in ["BUG_DTO_BRIDGE_LEGADO", "BUG_VARIAVEL_LEGADA", "BUG_VARIAVEL_LEGADA_DEPRECATED"]:
                    b["severidade"] = "ADVERTENCIA"
                    
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
        tentativas = 0
        while tentativas < 5:
            try:
                resultado_lote, usage = _chamar_api(
                    client, modulo, lote, skill, exemplos, i, total_lotes
                )
                todos_bugs.extend(resultado_lote.get("bugs", []))
                usage_total["input_tokens"]          += usage.input_tokens
                usage_total["output_tokens"]         += usage.output_tokens
                usage_total["cache_creation_tokens"] += getattr(usage, "cache_creation_input_tokens", 0)
                usage_total["cache_read_tokens"]     += getattr(usage, "cache_read_input_tokens", 0)
                break  # Sucesso, sai do loop de tentativas
            except json.JSONDecodeError as e:
                print(f"      AVISO: lote {i} retornou JSON invalido ({e}) — pulando")
                break  # JSON error indica erro de sintaxe do modelo, pulamos
            except Exception as e:
                msg = str(e).lower()
                if "429" in msg or "rate_limit" in msg or "rate limit" in msg:
                    espera = 20 * (2 ** tentativas)
                    print(f"      [RATE LIMIT] Limite excedido. Aguardando {espera}s para retentar (tentativa {tentativas+1}/5)...")
                    time.sleep(espera)
                    tentativas += 1
                else:
                    print(f"      AVISO: lote {i} falhou ({e}) — pulando")
                    break
        
        if tentativas == 5:
            print(f"      ERRO: Lote {i} abortado apos 5 tentativas de Rate Limit.")

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
def _chamar_api_tipagem(client, lote_invocacoes: list, numero_lote: int, total_lotes: int) -> dict:
    prompt = f"""Role: Analisador de Tipagem Java/.fj.
Task: Validar chamadas de metodos e apontar incompatibilidades de tipos em argumentos.

Abaixo estao as invocacoes extraidas do codigo fonte (lote {numero_lote}/{total_lotes}).
Para cada invocacao, avalie se ha um erro de tipagem claro, especialmente focado no uso de variaveis do tipo String onde se espera int.

Instrucoes Estritas:
1. FOCO: Quando um metodo no pacote de negocios (ex: pcpb, systextil) esperar `int` e receber `String` (literal entre aspas ou variavel convertida/conhecida), sugira a substituicao pelo metodo com sufixo `RT`. 
   Ex: `buscaValorPcpb("123")` -> `buscaValorPcpbRT("123")`
2. FALSOS POSITIVOS: Ignore imediatamente e não relate se houver conversão/cast explícito no argumento (ex: `(int)` ou `Integer.parseInt()`).
3. Se o argumento aparenta ser variavel do tipo String ou null, classifique como possivel erro sugerindo RT, mas marque severidade "ADVERTENCIA".
4. Retorne EXCLUSIVAMENTE um objeto JSON valido, respeitando a estrutura abaixo, sem textos adicionais.

{{
  "inconsistencias": [
    {{
      "arquivo": "<caminho_do_arquivo>",
      "linha": <linha_da_invocacao>,
      "codigo_analisado": "<codigo>",
      "chamada": {{
        "objeto": "<obj>",
        "metodo_alvo": "<metodo>",
        "argumentos_passados": "<argumentos_brutos>"
      }},
      "correcao_sugerida": {{
        "aplicar_sufixo_rt": true,
        "metodo_substituto": "<MetodoComSufixoRT>"
      }},
      "severidade": "ADVERTENCIA"
    }}
  ]
}}

LOTE DE INVOCACOES:
{json.dumps(lote_invocacoes, indent=2, ensure_ascii=False)}
"""

    response = client.messages.create(
        model="claude-3-5-sonnet-20241022",
        max_tokens=4096,
        temperature=0,
        messages=[
            {"role": "user", "content": prompt}
        ]
    )
    
    raw = response.content[0].text.strip()
    # Remove markdown code blocks se o modelo ainda adicionar
    if raw.startswith("```json"):
        raw = raw[7:]
    if raw.startswith("```"):
        raw = raw[3:]
    if raw.endswith("```"):
        raw = raw[:-3]

    return json.loads(raw.strip()), response.usage

def analisar_tipagem(hits: List[Dict[str, Any]], repos_aux: dict = None) -> dict:
    """
    Funcao focada em encontrar incompatibilidade de Tipagem usando o Claude.
    """
    client = anthropic.Anthropic()
    
    # hits aqui tem o formato: [{"arquivo": "...", "invocacoes": [{...}, {...}]}]
    todas_invocacoes = []
    for h in hits:
        if "invocacoes" in h and h["invocacoes"]:
            for inv in h["invocacoes"]:
                inv["arquivo"] = h.get("arquivo", "desconhecido")
                todas_invocacoes.append(inv)
                
    if not todas_invocacoes:
        return {"inconsistencias": [], "_usage": {}}
        
    lotes = [todas_invocacoes[i:i + 30] for i in range(0, len(todas_invocacoes), 30)]
    total_lotes = len(lotes)
    
    todas_inconsistencias = []
    usage_total = {"input_tokens": 0, "output_tokens": 0}
    
    for i, lote in enumerate(lotes, 1):
        print(f"      [Tipagem] Lote {i}/{total_lotes} ({len(lote)} invocacoes)...")
        tentativas = 0
        while tentativas < 3:
            try:
                res, usage = _chamar_api_tipagem(client, lote, i, total_lotes)
                todas_inconsistencias.extend(res.get("inconsistencias", []))
                usage_total["input_tokens"] += usage.input_tokens
                usage_total["output_tokens"] += usage.output_tokens
                break
            except Exception as e:
                msg = str(e).lower()
                if "429" in msg or "rate" in msg:
                    espera = 15 * (2 ** tentativas)
                    time.sleep(espera)
                    tentativas += 1
                else:
                    print(f"      [Tipagem] AVISO: lote {i} falhou ({e})")
                    break
                    
    return {"inconsistencias": todas_inconsistencias, "_usage": usage_total}
