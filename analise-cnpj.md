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

---

## Regras de Identificação de Colunas CNPJ Reais (Anti Falso Positivo)

### Regra do Trio Completo

Uma coluna com sufixo numérico (`_9`, `_4`, `9`, `4`) **só é coluna CNPJ real** se existir o **trio completo** no mesmo contexto (SELECT, INSERT ou declaração):

- Raiz: `cgc_9` ou `cgc_r`
- Ordem: `cgc_4` ou `cgc_o`  
- Dígito: `cgc_2` ou `cgc_d`

**Se não existir a coluna `_2` correspondente, é FALSO POSITIVO.**

Exemplos de falso positivo:
```java
// "constante4" — não existe constante2 ou constante9 → NÃO é CNPJ
// "complemento_cliente4" — não existe complemento_cliente2 → NÃO é CNPJ
// "linha4" — não existe linha2 → NÃO é CNPJ
```

Exemplo real:
```java
// cgc_9, cgc_4, cgc_2 presentes → É CNPJ real, verificar migração
```

### Regra da Chave Primária para Dualidade

A duplicação de colunas CNPJ em INSERTs de tabelas de dualidade é **obrigatória apenas para colunas que fazem parte da chave primária (PK)** da tabela.

| Situação | Diagnóstico |
|----------|-------------|
| Coluna CNPJ é PK e não tem par legado/novo | ❌ ERRO — duplicação obrigatória |
| Coluna CNPJ **não é PK** e não tem par | ✅ OK — duplicação não obrigatória |
| `cgc_2` / dígito verificador sem par | ✅ OK — dígito nunca precisa ser duplicado |

**Quando em dúvida sobre PK, classificar como ADVERTÊNCIA, não CRÍTICO.**

### Regra da Palavra-Chave de Domínio

Antes de reportar uma coluna como CNPJ, verificar se alguma parte do nome (separada por `_`) pertence a `PALAVRAS_CNPJ`:
```
cnpj, cgc, cod_part, corretora, despachante, courier, facc, tran, terc, cons, cli, for
```

Se nenhuma parte do nome pertencer à lista → **FALSO POSITIVO**.

Exemplos:
- `fornec_9` → `fornec` contém `for` → pode ser CNPJ, verificar trio
- `constante4` → nenhuma parte em PALAVRAS_CNPJ → FALSO POSITIVO
- `cgc_9` → `cgc` está na lista → verificar trio

---

## Tabelas Já Migradas para VARCHAR2 Nativo

Algumas tabelas já foram migradas para VARCHAR2 nativamente **antes** do processo de migração CNPJ alfanumérico. Para essas tabelas, as colunas CNPJ já são String por natureza — não há dualidade, não há colunas legadas numéricas, e o código que as referencia está **correto como está**.

### Lista de tabelas nativas VARCHAR2

| Tabela | Situação |
|--------|----------|
| `CREC_050` | Já migrada — colunas CNPJ são VARCHAR2 nativo |

### Regra de análise

Quando encontrar código que referencia `CREC_050`:

- **NÃO reportar** ausência de colunas legadas (`_9`/`_4`) como erro
- **NÃO reportar** como dualidade incompleta
- **NÃO reportar** `getString()` como suspeito
- Classificar como **VERIFICADO (OK)** — o código está correto
- Se houver `getInt()` em coluna CNPJ dessa tabela → aí sim é ERRO (estava errado antes da migração)

### Exemplo correto para CREC_050
```java
// CORRETO — CREC_050 ja e VARCHAR2 nativo, getString e o esperado
String cgcR = rs.getString("cgc_r");
String cgcO = rs.getString("cgc_o");

// INSERT sem colunas legadas — CORRETO para CREC_050
INSERT INTO CREC_050 (cgc_r, cgc_o, cgc_2, ...)
VALUES (?, ?, ?, ...)
-- Nao precisa de cgc_9/cgc_4 pois CREC_050 nao tem dualidade
```

---

## Padrão de Nomenclatura com Sufixo no Meio

Algumas colunas CNPJ têm o sufixo de tipo **no meio do nome**, não no final. O padrão é:

```
Legado:  cgc9_tbm  / cgc4_tbm  / cgc2_tbm
Novo:    cgc_tbm_r / cgc_tbm_o / cgc2_tbm
```

### Regra de identificação

Para colunas onde o sufixo numérico (`9`, `4`, `2`) aparece **antes** de um sufixo textual:

| Padrão legado | Padrão novo | Exemplo |
|--------------|-------------|---------|
| `cgcN_xxx` | `cgc_xxx_r` | `cgc9_tbm` → `cgc_tbm_r` |
| `cgcN_xxx` | `cgc_xxx_o` | `cgc4_tbm` → `cgc_tbm_o` |
| `cgcN_xxx` | `cgc_xxx_2` | `cgc2_tbm` → inalterado |

### Critério de validação

1. Verificar se existe o trio completo: `cgc9_xxx`, `cgc4_xxx`, `cgc2_xxx`
2. Se existe o trio → é CNPJ real com nomenclatura especial
3. Verificar se a versão nova (`cgc_xxx_r`, `cgc_xxx_o`) também existe no contexto
4. Se **ambos** os pares existem → **VERIFICADO (OK)** — dualidade correta
5. Se só existe o legado sem o novo → **CRÍTICO** — migração incompleta
6. Se só existe o novo sem o legado (em tabela de dualidade) → **CRÍTICO** — falta par legado

### Exemplo correto
```java
// cgc9_tbm + cgc_tbm_r presentes — dualidade correta
SELECT cgc9_tbm, cgc4_tbm, cgc2_tbm,
       cgc_tbm_r, cgc_tbm_o
FROM tabela
```

### Exemplo com erro
```java
// Só cgc9_tbm sem cgc_tbm_r — migracao incompleta
SELECT cgc9_tbm, cgc4_tbm, cgc2_tbm
FROM tabela
-- FALTA: cgc_tbm_r, cgc_tbm_o
```

---

## Regra de Severidade por Origem do Bug

| Situação | Severidade |
|----------|-----------|
| `pre_existente=false` + qualquer bug CNPJ | **CRÍTICO** |
| `pre_existente=true` + código legado CNPJ (`cgc_9`, `getInt` em `_r/_o`, etc) | **CRÍTICO** — arquivo não migrado |
| `pre_existente=true` + bug estrutural sem relação com CNPJ | **ADVERTÊNCIA** |

### Exemplos de bugs estruturais (ADVERTÊNCIA quando pre_existente=true)
- Mismatch de placeholders SQL (`INSERT` com 5 `?` mas 7 parâmetros)
- Lógica `AND` onde deveria ser `OR`
- NullPointerException não relacionado a campos CNPJ
- Encoding corrompido em comentários
- Qualquer bug que já existia no WEB e não envolve campos CNPJ

---

## Regra BUG_3 — CNPJ.ZEROS.equals()

O detector `BUG_3` verifica comparações incorretas com `CNPJ.ZEROS`. A regra é:

| Código | Diagnóstico |
|--------|-------------|
| `CNPJ.ZEROS.equals(outroCNPJ)` | ✅ **CORRETO** — compara objeto CNPJ com CNPJ, funciona |
| `CNPJ.ZEROS.equals(umaString)` | ❌ **ERRO** — compara CNPJ com String, sempre retorna false |
| `cnpjVar.equals(CNPJ.ZEROS)` | ✅ **CORRETO** — comparação válida entre objetos CNPJ |
| `cnpjVar.isZeros()` | ✅ **CORRETO** — método utilitário da classe CNPJ |

### Como identificar o tipo do argumento

Verificar o tipo da variável passada para `equals()`:
- Se for `String` (ex: `getString(...)`, literal `"..."`, variável `String x`) → **ERRO**
- Se for objeto `CNPJ` (ex: variável declarada como `CNPJ`, retorno de `CNPJ.get(...)`) → **CORRETO**
- Se o tipo não puder ser determinado pelo contexto → **FALSO_POSITIVO**

Reportar como `BUG_3 CRÍTICO` apenas quando for confirmado que o argumento é `String`.

---

## Tabelas com Regras Especiais de Migração

### OPER_001 — Substituição sem Dualidade

A `OPER_001` usa campos genéricos numerados. A migração **substitui** a coluna numérica pela alfanumérica — **sem duplicar**.

| Antes (NUMBER) | Depois (VARCHAR2) |
|----------------|-------------------|
| `campo_01` | `campo_52` |
| `campo_02` | `campo_53` |
| `campo_03` (dígito) | `campo_03` (inalterado) |

**Regra de validação:**
- INSERT em `OPER_001` usando `campo_01`/`campo_02` sem `campo_52`/`campo_53` → **CRÍTICO**
- INSERT em `OPER_001` usando `campo_52`/`campo_53` sem `campo_01`/`campo_02` → **CORRETO** (não precisa duplicar)
- Não aplicar regra de dualidade padrão para esta tabela

```java
// CORRETO para OPER_001
INSERT INTO oper_001 (campo_52, campo_53, campo_03) VALUES (?, ?, ?)
new AppConnection(conn, sql, cnpj.r, cnpj.o, cnpj.d);

// ERRO — ainda usa campos numericos
INSERT INTO oper_001 (campo_01, campo_02, campo_03) VALUES (?, ?, ?)
```

---

### OPER_TMP — Dualidade Obrigatória (Jasper/Crystal)

A `OPER_TMP` é usada por relatórios Jasper e Crystal que **não serão migrados agora**. Por isso, **deve manter ambos os campos** (duplicidade obrigatória).

| Antes (NUMBER) | Depois — manter ambos |
|----------------|----------------------|
| `int_01` | `str_02` (novo) + `int_01` (manter) |
| `int_02` | `str_03` (novo) + `int_02` (manter) |
| `int_03` (dígito) | `int_03` (inalterado) |

Campos disponíveis para VARCHAR2: `str_02` a `str_15` — usar sempre o menor disponível.

**Regra de validação:**
- INSERT em `OPER_TMP` com `str_0x` mas sem `int_01`/`int_02` → **CRÍTICO** (quebra Jasper)
- INSERT em `OPER_TMP` com `int_01`/`int_02` mas sem `str_0x` → **CRÍTICO** (migração incompleta)
- INSERT com ambos os pares → **CORRETO**

```java
// CORRETO para OPER_TMP — duplica ambos os pares
INSERT INTO oper_tmp (str_02, str_03, int_03, int_01, int_02) VALUES (?, ?, ?, ?, ?)
new AppConnection(conn, sql, cnpj.r, cnpj.o, cnpj.d, cnpj.r, cnpj.o);
```

---

### RCNB_060 — Campos Gêmeos com Sufixo _STR

A `RCNB_060` é uma tabela temporária. O CNPJ alfanumérico usa os campos gêmeos com sufixo `_STR`.

**Ordem de preferência para campos STRING:**
1. Campo gêmeo: `nivel_estrutura_str`, `grupo_estrutura_str`, `subgrupo_estrutura_str`, `item_estrutura_str`
2. Se ocupado: `campo_str_01` → `_02` → `_03` → `_04` → `_05`

**Regra de validação:**
- `getInt("nivel_estrutura")` onde deveria ser `getString("nivel_estrutura_str")` → **CRÍTICO**
- `nivel_estrutura` sem `nivel_estrutura_str` no mesmo SELECT → **CRÍTICO**
- `nivel_estrutura_str` presente → **CORRETO**

```java
// CORRETO para RCNB_060
SELECT temp.nivel_estrutura_str, temp.grupo_estrutura_str, temp.subgrupo_estrutura
cnpj = CNPJ.get(select.getString("nivel_estrutura_str"),
                select.getString("grupo_estrutura_str"),
                select.getInt("subgrupo_estrutura"));
```

---

## Regra initField em Arquivos .fj

Campos CNPJ em formulários `.fj` que possuem a propriedade `INIT FIELD` devem conter `super.initField()` dentro dela. Sem isso o campo não inicializa corretamente em runtime.

### Como identificar

1. No branch WEB, campo CNPJ tinha `INIT FIELD { ... super.initField(); ... }`
2. No branch CNPJ, o mesmo campo existe mas `super.initField()` foi removido ou não foi adicionado

### Regra de validação

Um FIELD só é considerado CNPJ se:
1. O widget extende `systextil.widgets.cliente.R`, `.O` ou `.D`, **OU**
2. O nome do campo termina com `_r`, `_o` ou `_2` **E** contém palavra CNPJ (cgc, cnpj, cli, forn, etc.)

Campos como `tipos_forn`, `cod_fornecedor`, `nome_cli` **NÃO** são CNPJ — não possuem sufixo `_r`/`_o`/`_2` nem widget CNPJ.

Para cada `FIELD` que é CNPJ conforme os critérios acima:
- Se tem bloco `INIT FIELD` sem `super.initField()` → **CRÍTICO**
- Se não tem bloco `INIT FIELD` → **OK** (não é obrigatório ter)
- Se tem `INIT FIELD` com `super.initField()` → **CORRETO**

### Exemplo com erro
```
FIELD cgc_r : String {
    INIT FIELD {
        // falta super.initField() aqui
        this.setMaxLength(9);
    }
}
```

### Exemplo correto
```
FIELD cgc_r : String {
    INIT FIELD {
        super.initField();
        this.setMaxLength(9);
    }
}
```

---

## BUG_LEGADO em Blocos EXEC SQL de Arquivos .fj

Em arquivos `.fj`, SQL é escrito diretamente no código dentro de blocos `EXEC SQL ... INTO`, **sem aspas**. O detector padrão de SQL legado só procura em strings Java (`"..."`), então este é um detector específico para `.fj`.

### O que detecta

Blocos `EXEC SQL` que usam colunas CNPJ legadas (`cgc_9`, `cgc_4`, `fornecedor9`, etc.) sem a versão nova (`cgc_r`, `cgc_o`, `fornecedor_r`, etc.).

### Regra de validação

| Situação | Diagnóstico |
|----------|-------------|
| `EXEC SQL ... cgc_9 ... cgc_r ...` | ✅ **CORRETO** — ambas presentes |
| `EXEC SQL ... cgc_r ... cgc_o ...` (sem legado) | ✅ **CORRETO** — SELECT/WHERE pode usar só a nova |
| `EXEC SQL ... cgc_9 ... cgc_4 ...` (sem _r/_o) | ❌ **ERRO** — SQL ainda usa colunas legadas |

### Exemplo com erro (arquivo .fj)
```
FIELD campo_numerico03 extends systextil.widgets.cliente.D
{
    WHEN VALUE CHANGES
    {
        EXEC SQL
        select pedi_010.nome_cliente from pedi_010
        where pedi_010.cgc_9 = :campo_numerico01
        and pedi_010.cgc_4 = :campo_numerico02
        and pedi_010.cgc_2 = :campo_numerico03
        INTO nome_cliente ;
    }
}
```
**Erro**: `cgc_9` e `cgc_4` devem ser `cgc_r` e `cgc_o`.

### Exemplo correto (arquivo .fj)
```
FIELD campo_numerico01 extends systextil.widgets.cliente.R
{
    WHEN VALUE CHANGES
    {
        EXEC SQL
        select pedi_010.nome_cliente from pedi_010
        where pedi_010.cgc_r = :campo_numerico01
        and pedi_010.cgc_o = :campo_numerico02
        and pedi_010.cgc_2 = :campo_numerico03
        INTO nome_cliente ;
    }
}
```

---

## CAMPO_NUMERICO_CNPJ — Campos Numéricos Usados para CNPJ em .fj

Em formulários `.fj`, campos CNPJ eram historicamente armazenados em `campo_numerico*` (tipo numérico). Com a migração para CNPJ alfanumérico (VARCHAR2/String), esses campos precisam ser alterados para `descricao*` (tipo String).

### Como identificar

Um `FIELD campo_numerico*` está sendo usado para CNPJ se atender a **qualquer** destes critérios:

1. **Extends widget CNPJ**: `systextil.widgets.cliente.R`, `.O` ou `.D`
2. **SQL no bloco referencia coluna CNPJ** com bind variable `:campo_numerico*` (ex: `cgc_r = :campo_numerico01`)
3. **Atribuição global**: `formId.campo_numerico01 = CNPJ.ZEROS.r`

### Regra de validação

| Situação | Diagnóstico |
|----------|-------------|
| `FIELD campo_numerico01 extends systextil.widgets.cliente.R` | ❌ **ERRO** — alterar para `descricao*` |
| `FIELD campo_numerico01 extends objetos.intFieldBase` (sem referência CNPJ) | ✅ **OK** — campo numérico real |
| `formId.campo_numerico01 = CNPJ.ZEROS.r` | ❌ **ERRO** — campo recebe CNPJ mas é numérico |

### Correção

Trocar `campo_numerico*` por campo de tipo String (`descricao*` ou equivalente) em:
- Declaração do FIELD
- Todas as referências no formulário (`formId.campo_numerico01` → `formId.descricao01`)
- Blocos `EXEC SQL` que usam `:campo_numerico*` como bind variable para colunas CNPJ

### Exemplo com erro
```
// ERRO: campo_numerico01 e numerico mas recebe CNPJ (String)
formId.campo_numerico01 = CNPJ.ZEROS.r;
formId.campo_numerico02 = CNPJ.ZEROS.o;

FIELD campo_numerico01 extends systextil.widgets.cliente.R
{
    WHEN VALUE CHANGES
    {
        EXEC SQL
        select nome_cliente from pedi_010
        where pedi_010.cgc_r = :campo_numerico01
        INTO nome_cliente ;
    }
}
```

### Exemplo correto
```
// CORRETO: usa descricao (String) para CNPJ alfanumerico
formId.descricao01 = CNPJ.ZEROS.r;
formId.descricao02 = CNPJ.ZEROS.o;

FIELD descricao01 extends systextil.widgets.cliente.R
{
    WHEN VALUE CHANGES
    {
        EXEC SQL
        select nome_cliente from pedi_010
        where pedi_010.cgc_r = :descricao01
        INTO nome_cliente ;
    }
}
```

### Atenção

Nem todo `campo_numerico*` é CNPJ. Apenas os que atendem aos critérios acima. Por exemplo, `campo_numerico04` que recebe um inteiro normal (tipo de processo, sequência, etc.) **não deve ser alterado**.