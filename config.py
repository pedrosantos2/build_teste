# =============================================================================
# config.py — Conhecimento de dominio da migracao CNPJ alfanumerico
# Versao RT-only: apenas configuracoes necessarias para analise de tipagem RT.
# =============================================================================

# Palavras-chave que identificam variaveis/colunas relacionadas a CNPJ
PALAVRAS_CNPJ = (
    'cnpj', 'cgc', 'cod_part', 'corretora', 'despachante',
    'courier', 'facc',
    # Palavras longas (>4 chars) — match por substring sem restricao
    'fornecedor', 'fornec', 'forne', 'forn', 'forcli',
    'cliente', 'transp',
    # Palavras curtas (<=4 chars) — match exige delimitacao por _ ou inicio/fim
    # Isso evita falsos positivos como 'formato', 'consulta', 'translate', etc.
    'tran', 'terc', 'cons', 'cli', 'for',
    'tbm',  # sufixo especial: cgc9_tbm / cgc_tbm_r
)

# Arquivos a ignorar na analise (DTOs, Enums, etc nao tem logica CNPJ)
IGNORAR_PADROES = [
    "*Dto*", "*DTO*", "*Enum*", "*Config*",
    "*Application*", "*Exception*", "*Mapper*",
    "*package-info*"
]

# Pastas que DEVEM ser analisadas — so codigo fonte
PASTAS_INCLUIR = {"src", "sources", "batch", "controller", "systextil"}

# Pastas que NUNCA devem ser analisadas
PASTAS_EXCLUIR = {"output", "temp", "target", ".git", "build", "node_modules",
                  "webnxj", "unify", "compilation", "ear-contents", "war-contents"}

# Extensoes analisadas
EXTENSOES_ANALISAR = {".java", ".fj", ".jsp"}
