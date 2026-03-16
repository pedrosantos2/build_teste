# Análise CNPJ Alfanumérico — Módulo $ARGUMENTS

Executar análise completa da migração CNPJ alfanumérico no módulo **$ARGUMENTS**, comparando o branch `CNPJ` com o branch principal (`WEB`).

## Contexto da Migração

O ERP Systextil está migrando o CNPJ brasileiro de formato **numérico** (`int`) para **alfanumérico** (`String`).

| Aspecto | Legado | Novo |
|---------|--------|------|
| Classe Java | `systextil.dao.Cnpj` (`int cgc9, int cgc4, int cgc2`) | `systextil.CNPJ` (`String r, String o, byte d`) |
| Colunas BD (raiz) | `cgc_9`, `fornecedor9`, `cli_ped_cgc_cli9` (NUMBER) | `cgc_r`, `fornecedor_r`, `cli_ped_cgc_cli_r` (VARCHAR2) |
| Colunas BD (ordem) | `cgc_4`, `fornecedor4`, `cli_ped_cgc_cli4` (NUMBER) | `cgc_o`, `fornecedor_o`, `cli_ped_cgc_cli_o` (VARCHAR2) |
| Colunas BD (dígito) | `cgc_2` (NUMBER) — sem mudança | `cgc_2` / `.d` (int/byte) — sem mudança |
| Constantes | `0` / `9999` (int) | `CNPJ.ZEROS` ("000000000","0000",0) / `CNPJ.NOVES` ("999999999","9999",99) |

### API da Classe `systextil.CNPJ`
```java
public final String r;        // Raiz (ex: "000000000" ou alfanumérico)
public final String o;        // Ordem (ex: "0000" ou alfanumérico)
public final byte d;          // Dígito verificador
public static final CNPJ ZEROS;  // new CNPJ("000000000", "0000", 0)
public static final CNPJ NOVES;  // new CNPJ("999999999", "9999", 99)
public static CNPJ get(String r, String o, int d);
public boolean equals(Object o);
public boolean isZeros();
```

---

## Procedimento de Análise

### PASSO 1 — Preparação do Repositório

1. Verificar se o módulo `$ARGUMENTS` já está no workspace (`/Systextil/workspace/$ARGUMENTS`)
2. Se não existe, clonar: `git clone https://jeffreyal91systextil@bitbucket.org/systextildevelopers/$ARGUMENTS.git`
3. Verificar branches: `git branch -a | grep -i cnpj`
4. Identificar o branch principal (geralmente `WEB`) e o branch CNPJ
5. Obter o diff: `git diff WEB..origin/CNPJ --stat`

### PASSO 2 — Análise Automatizada de Padrões de Erro

Para **cada arquivo** modificado entre os branches, executar as seguintes verificações automatizadas em lote. Estes são os padrões de erro confirmados em módulos anteriores (efic, inte):

#### 2.1 — Comparação `==` / `!=` com String (Bug Crítico em Java)
```bash
# Buscar em TODOS os arquivos do branch CNPJ
for file in $(git diff WEB..origin/CNPJ --name-only -- '*.java' '*.fj'); do
    git show "origin/CNPJ:$file" | grep -n '==' | grep -iE '(cgc_r|cgc_o|forne_r|forne_o|fornec_r|fornec_o|cliente_r|cliente_o)' | grep -v '!='
done
```
**Problema**: Em Java, `==` compara referência de objeto, não conteúdo. Strings CNPJ devem usar `.equals()`.
**EXCEÇÃO**: Arquivos `.fj` usam compilador proprietário que PODE converter `==` em `.equals()`. Verificar com a equipe do framework. Mesmo assim, reportar como advertência.

#### 2.2 — `getInt()` em colunas alfanuméricas
```bash
for file in $(git diff WEB..origin/CNPJ --name-only -- '*.java'); do
    git show "origin/CNPJ:$file" | grep -n 'getInt' | grep -iE '(_r"|_o"|cgc_r|cgc_o|forne_r|forne_o)'
done
```
**Problema**: `getInt()` em VARCHAR2 causa `NumberFormatException` com CNPJ alfanumérico.

#### 2.3 — `setInt()` com variáveis String
```bash
for file in $(git diff WEB..origin/CNPJ --name-only -- '*.java'); do
    git show "origin/CNPJ:$file" | grep -n 'setInt' | grep -iE '(cgc_r|cgc_o|forne_r|forne_o|fornec_r|fornec_o|cliente_r|cliente_o)'
done
```
**Problema**: Passar String para `setInt()` causa erro de compilação ou runtime.

#### 2.4 — `Integer.parseInt()` em campos alfanuméricos
```bash
for file in $(git diff WEB..origin/CNPJ --name-only -- '*.java'); do
    git show "origin/CNPJ:$file" | grep -n 'parseInt' | grep -iE '(cgc_r|cgc_o|forne_r|forne_o|fornec_r|fornec_o)'
done
```
**Problema**: `parseInt()` falhará com CNPJ contendo letras.

#### 2.5 — Colunas antigas esquecidas em queries SQL
```bash
for file in $(git diff WEB..origin/CNPJ --name-only -- '*.java' '*.fj'); do
    git show "origin/CNPJ:$file" | grep -nE '(cmdSQL|select|from|where|and|insert|update)' | \
    grep -iE 'cgc_9\b|cgc_4\b|fornecedor9|fornecedor4|fornec_9\b|fornec_4\b|cli_ped_cgc_cli9|cli_ped_cgc_cli4'
done
```
**Problema**: Query SQL referenciando colunas que foram renomeadas causará `ORA-00904: invalid identifier`.

#### 2.6 — SELECT com colunas antigas mas getString com novas (ou vice-versa)
Verificar que as colunas no SELECT correspondam às usadas no `getString()`/`getInt()` do ResultSet.

#### 2.7 — Condições OR com tipos misturados
```bash
# Buscar condições "? = 0 and ? = '000'" ou similar
for file in $(git diff WEB..origin/CNPJ --name-only -- '*.java'); do
    git show "origin/CNPJ:$file" | grep -n "? = 0.*? = '\\|? = '.*? = 0"
done
```
**Problema**: Parâmetros String comparados com literais numéricos, ou vice-versa.

#### 2.8 — Literais hardcoded vs `CNPJ.ZEROS`
```bash
for file in $(git diff WEB..origin/CNPJ --name-only -- '*.java'); do
    git show "origin/CNPJ:$file" | grep -n '"000000000"\|"0000"' | grep -v 'cmdSQL\|SQL\|select\|where\|//\|println'
done
```
**Nota**: Funcionalmente equivalente, mas `CNPJ.ZEROS.r` é mais manutenível. Reportar como sugestão.

#### 2.9 — Encoding corrompido
```bash
for file in $(git diff WEB..origin/CNPJ --name-only); do
    cnpj=$(git show "origin/CNPJ:$file" 2>/dev/null | grep -c '�?' || echo 0)
    web=$(git show "WEB:$file" 2>/dev/null | grep -c '�?' || echo 0)
    [ "$cnpj" -gt "$web" ] && echo "ENCODING: $file"
done
```

#### 2.10 — Verificação de widgets em .fj (formulários)
```bash
for file in $(git diff WEB..origin/CNPJ --name-only -- '*.fj'); do
    git show "origin/CNPJ:$file" | grep 'systextil.widgets.(Fornecedor|cliente)\.'
done
```

#### 2.11 — Verificação de tipos em .fx (frontend)
```bash
for file in $(git diff WEB..origin/CNPJ --name-only -- '*.fx'); do
    git diff WEB..origin/CNPJ -- "$file" | grep '^[+-]' | grep -E 'accell_type|db_type'
done
```

### PASSO 3 — Análise Detalhada por Arquivo

Para cada bug ou inconsistência encontrada no Passo 2:
1. Ler o contexto completo no branch CNPJ: `git show origin/CNPJ:arquivo | sed -n 'LINHAp'`
2. Comparar com o original WEB: `git show WEB:arquivo | sed -n 'LINHAp'`
3. Determinar se é:
   - **Bug novo** (introduzido pela migração CNPJ) → Reportar com severidade
   - **Bug pré-existente** (já existia no WEB) → Reportar como advertência
   - **Falso positivo** (correto, contexto explica) → Ignorar

### PASSO 4 — Verificação de Completude

1. Listar TODOS os arquivos modificados entre branches
2. Classificar cada arquivo como:
   - **Batch Java** (.java em batch/) — lógica backend
   - **Forms** (.fj) — formulários
   - **Frontend** (.fx, .jsp) — apresentação
   - **Config** (pom.xml, java.xml) — configuração
3. Para cada arquivo Java/fj, verificar que TODOS os campos CNPJ foram migrados consistentemente:
   - Declaração de variável (int → String)
   - Leitura do BD (getInt → getString)
   - Escrita no BD (setInt → setString)
   - Queries SQL (colunas renomeadas)
   - Comparações (== → .equals())
   - Valores default (0 → CNPJ.ZEROS.r)
   - Output/relatório (formatação)

### PASSO 5 — Geração do Relatório HTML

Gerar um arquivo HTML autocontido em `/Systextil/workspace/$ARGUMENTS/analise-cnpj-$ARGUMENTS.html` com:

1. **Dashboard** com estatísticas (arquivos analisados, bugs por severidade)
2. **Padrão de Renomeação** (tabela com colunas antigas → novas)
3. **Classe CNPJ** (API resumida)
4. **Bugs Críticos** — Cards detalhados com:
   - Arquivo e linha
   - Código problemático (diff colorido)
   - Impacto em produção
   - Correção sugerida
5. **Bugs Médios e Baixos** — Mesmo formato
6. **Advertências** — Bugs pré-existentes, inconsistências de estilo
7. **Arquivos Corretos** — Lista com verificação de cada item
8. **Tabela de Ações** — Resumo priorizado

**Estilo visual**: Tema escuro (#0d1117), cards com borda colorida por severidade, código com syntax highlighting, badges de severidade. Sem dependências externas (CSS inline).

---

## Classificação de Severidade

| Severidade | Critério | Exemplos |
|------------|----------|----------|
| **CRÍTICO** | Causa erro em runtime (SQLException, NPE, resultado incorreto) | SELECT coluna_antiga + getString coluna_nova; setInt com String; condição OR tipos misturados |
| **MÉDIO** | Pode causar comportamento incorreto em casos específicos | `==` com String em .fj (depende do compilador); lógica de filtro invertida |
| **BAIXO** | Problema estético ou de manutenibilidade | Encoding corrompido em mensagens; literais hardcoded |
| **SUGESTÃO** | Melhoria recomendada sem impacto funcional | Usar CNPJ.ZEROS em vez de "000000000"; padronizar estilo |
| **ADVERTÊNCIA** | Bug pré-existente (não introduzido pelo CNPJ) | Lógica AND onde deveria ser OR; comparações confusas |

---

## Bugs Conhecidos em Outros Módulos (Referência)

Estes padrões foram confirmados em análises anteriores. Priorize a busca por eles:

| Módulo | Bug | Arquivo | Padrão |
|--------|-----|---------|--------|
| **inte** | INSERT 16 cols / 12 placeholders | inte_f140.java | SQL mismatch |
| **inte** | getInt() em VARCHAR2 | inte_f140.java | Tipo incorreto |
| **inte** | CNPJ.ZEROS.equals(String) | InteF385.java | Comparação inválida |
| **inte** | Dead code (x \|\| !x) | inte_f155.java | Lógica incorreta |
| **efic** | SELECT coluna_antiga + getString nova | efic_e450.java | Coluna esquecida |
| **efic** | Condição OR tipos invertidos | efic_e450.java | Tipos misturados |
| **efic** | `==` com String em .fj | efic_f230.fj | Comparação referência |
| **efic** | Encoding corrompido | efic_e400.fj | Encoding |

---

## Notas Importantes

- **NÃO modificar nenhum arquivo do código fonte** — esta análise é somente leitura
- **Idioma**: Relatório em português, código em inglês (como original)
- **Arquivos .fj**: O compilador proprietário Systextil pode tratar `==` como `.equals()` para Strings. Reportar como "potencial bug" com nota sobre o framework
- **Performance**: Lançar agentes em paralelo para análise de batch, forms e frontend quando possível
- **Completude**: Analisar TODOS os arquivos, não apenas amostras. O objetivo é zero bugs em produção

---

## Regra de Dualidade em INSERT (Tabelas de Transição)

Durante a migração, tabelas listadas em `TABELAS_DUALIDADE` precisam manter **ambas** as colunas simultaneamente no INSERT — a legada (NUMBER) e a nova (VARCHAR2). Isso garante compatibilidade com módulos ainda não migrados.

### Critério de validação em INSERTs

Para qualquer INSERT em tabela de `TABELAS_DUALIDADE`:

| Situação | Diagnóstico |
|----------|-------------|
| Tem `cgc_r`/`cgc_o` **e** tem `cgc_9`/`cgc_4` | ✅ CORRETO — dualidade mantida |
| Tem `cgc_r`/`cgc_o` mas **falta** `cgc_9`/`cgc_4` | ❌ ERRO — coluna legada ausente, módulos antigos vão falhar |
| Tem `cgc_9`/`cgc_4` mas **falta** `cgc_r`/`cgc_o` | ❌ ERRO — coluna nova ausente, migração incompleta |
| Tem só as colunas corretas do contexto (ex: `cli_ped_cgc_cli_r`) mas falta o par (`cli_ped_cgc_cli_r` sem `cli_ped_cgc_cli9`) | ❌ ERRO — par incompleto |

### Escopo

- Verificar **apenas INSERTs** — SELECTs e UPDATEs não precisam de dualidade
- Aplicar **apenas para tabelas em `TABELAS_DUALIDADE`**
- A verificação é por **grupo de colunas CNPJ** — cada entidade (cgc, fornecedor, cli_ped_cgc_cli) deve ter seu par completo

### Exemplo correto
```sql
-- INSERT em PEDI_010 (tabela de dualidade) — CORRETO
INSERT INTO PEDI_010 (cgc_r, cgc_o, cgc_9, cgc_4, ...)
VALUES (?, ?, ?, ?, ...)
```

### Exemplo com erro
```sql
-- INSERT em PEDI_010 — ERRO: tem cgc_r/cgc_o mas falta cgc_9/cgc_4
INSERT INTO PEDI_010 (cgc_r, cgc_o, ...)
VALUES (?, ?, ...)

-- INSERT em PEDI_010 — ERRO: cli_ped_cgc_cli_r presente mas falta cli_ped_cgc_cli9
INSERT INTO PEDI_010 (cgc_r, cgc_o, cgc_9, cgc_4, cli_ped_cgc_cli_r, cli_ped_cgc_cli_o, ...)
VALUES (?, ?, ?, ?, ?, ?, ...)
```

---

## Verificação de JSPs Não Migrados

Arquivos `.jsp` que referenciam tabelas de `TABELAS_DUALIDADE` ou colunas CNPJ mas **não foram modificados** entre WEB e CNPJ devem ser reportados como **ADVERTÊNCIA** — podem precisar de migração.

- Reportar como: `jsp_nao_migrado`
- Severidade: `ADVERTENCIA`
- Ação sugerida: revisar manualmente se o JSP precisa ser atualizado