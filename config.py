# =============================================================================
# config.py — Conhecimento de domínio da migração CNPJ alfanumérico
# Atualize aqui conforme a migração evolui. O restante do código não muda.
# =============================================================================

# Palavras-chave que identificam variáveis/colunas relacionadas a CNPJ
PALAVRAS_CNPJ = (
    'cnpj', 'cgc', 'cod_part', 'corretora', 'despachante',
    'courier', 'facc', 'tran', 'terc', 'cons', 'cli', 'for',
    'tbm',  # sufixo especial: cgc9_tbm / cgc_tbm_r
)

# Tabelas que possuem colunas CNPJ (dualidade numérico/alfanumérico)
# Quando uma dessas tabelas aparece no código, verificar se as colunas CNPJ estão corretas
TABELAS_DUALIDADE = {
    "BASI_008", "BASI_037", "BASI_041", "BASI_245", "BASI_460", "BASI_572", "BASI_969",
    "CONS_001", "CONS_010", "CONT_030", "COST_001",
    "CPAG_010", "CPAG_010_PED_COMPRA", "CPAG_015", "CPAG_090", "CPAG_168", "CPAG_350", "CPAG_450", "CPAG_850",
    "CREC_060", "CREC_070", "CREC_101", "CREC_102", "CREC_150", "CREC_170", "CREC_180", "CREC_180_SIMULA",
    "CREC_200", "CREC_209", "CREC_250", "CREC_251", "CREC_252", "CREC_450", "CREC_563", "CREC_960", "CREC_962",
    "EFIC_012", "EIXO_003", "EMPR_073", "EMPR_090", "ESTQ_400", "ESTQ_405", "EXPT_040", "EXTC_020",
    "FATU_036", "FATU_052",  # FATU_050 removida — nao tem PK com CNPJ "FATU_070", "FATU_075", "FATU_076", "FATU_120", "FATU_125", "FATU_155", "FATU_157", "FATU_440",
    "FATX_070", "FATX_075", "FINA_030", "FINX_030", "FNDC_001", "FNDC_007",
    "HDOC_001", "HDOC_050", "HDOC_060", "HDOC_110", "HDOC_115", "HIST_VOL_01",
    "INTE_055", "INTE_067", "INTE_084", "INTE_305", "INTE_360", "INTE_385", "INTE_406",
    "INTE_510", "INTE_511", "INTE_520", "INTE_560", "INTE_570", "INTE_WMS_TAGS_NOTA",
    "IXML_010", "I_OBRF_017",
    "LIVE_001", "LIVE_002", "LIVE_010",
    "LOJA_020", "LOJA_060", "LOJA_061", "LOJA_850", "LOJA_855",
    "MONK_020", "MTTM_004",
    "OBRF_002", "OBRF_010", "OBRF_010_DEVOL_OK", "OBRF_014", "OBRF_015", "OBRF_016", "OBRF_017", "OBRF_019",
    "OBRF_056", "OBRF_057", "OBRF_060", "OBRF_074", "OBRF_075", "OBRF_076", "OBRF_077", "OBRF_095", "OBRF_100",
    "OBRF_115", "OBRF_116", "OBRF_122", "OBRF_130", "OBRF_141", "OBRF_160", "OBRF_186", "OBRF_195", "OBRF_206",
    "OBRF_250", "OBRF_275", "OBRF_297", "OBRF_430", "OBRF_431", "OBRF_665",
    "OBRF_700", "OBRF_701", "OBRF_702", "OBRF_709", "OBRF_710", "OBRF_715",
    "OBRF_721", "OBRF_722", "OBRF_725", "OBRF_743", "OBRF_772", "OBRF_783", "OBRF_788",
    "OBRF_810", "OBRF_823", "OBRF_832", "OBRF_851", "OBRF_971",
    "OPER_284",  # OPER_001 e OPER_TMP removidas — tem regras proprias de migracao
    "PCPC_012", "PCPC_340", "PCPC_341", "PCPC_343", "PCPF_080", "PCPF_081", "PCPT_016",
    "PEDI_005", "PEDI_010", "PEDI_011", "PEDI_012", "PEDI_013", "PEDI_014", "PEDI_015", "PEDI_028", "PEDI_035",
    "PEDI_055", "PEDI_058", "PEDI_065", "PEDI_067", "PEDI_068", "PEDI_074", "PEDI_084", "PEDI_103", "PEDI_112",
    "PEDI_117", "PEDI_118", "PEDI_119", "PEDI_121", "PEDI_150", "PEDI_156", "PEDI_160", "PEDI_170", "PEDI_175",
    "PEDI_178", "PEDI_181", "PEDI_187", "PEDI_230", "PEDI_235", "PEDI_240", "PEDI_245", "PEDI_265", "PEDI_307",
    "PEDI_341", "PEDI_400", "PEDI_405", "PEDI_406", "PEDI_410", "PEDI_411", "PEDI_420", "PEDI_430", "PEDI_440",
    "PEDI_450", "PEDI_475", "PEDI_490", "PEDI_711", "PEDI_728", "PEDI_799", "PEDI_806", "PEDI_807", "PEDI_905",
    "PEDX_010",
    "RCNB_030", "RCNB_033", "RCNB_080", "RCNB_140", "RCNB_200", "RCNB_204", "RCNB_216",
    "SPED_0000", "SPED_0150", "SPED_1601", "SPED_C100", "SPED_C170", "SPED_K200_H010",
    "SPED_PC_0000", "SPED_PC_0019", "SPED_PC_0145", "SPED_PC_0150", "SPED_PC_0190", "SPED_PC_0200",
    "SPED_PC_0400", "SPED_PC_0450", "SPED_PC_0500", "SPED_PC_056", "SPED_PC_0600",
    "SPED_PC_C100", "SPED_PC_C170", "SPED_PC_P100",
    "SUPP_010",
    "SUPR_004", "SUPR_005", "SUPR_010", "SUPR_011", "SUPR_012", "SUPR_015", "SUPR_017", "SUPR_021", "SUPR_025",
    "SUPR_027", "SUPR_027_AUX", "SUPR_028", "SUPR_029", "SUPR_030", "SUPR_060", "SUPR_063",
    "SUPR_132", "SUPR_180", "SUPR_200", "SUPR_210", "SUPR_440", "SUPR_580",
}

# Mapeamento de colunas legadas ? novas (para validação cruzada)
COLUNAS_RENOMEADAS = {
    "cgc_9":              "cgc_r",
    "cgc_4":              "cgc_o",
    "fornecedor9":        "fornecedor_r",
    "fornecedor4":        "fornecedor_o",
    "fornec_9":           "fornec_r",
    "fornec_4":           "fornec_o",
    "cli_ped_cgc_cli9":   "cli_ped_cgc_cli_r",
    "cli_ped_cgc_cli4":   "cli_ped_cgc_cli_o",
    # Padrao com sufixo no meio: cgcN_xxx -> cgc_xxx_r/o
    # cgc9_tbm/cgc4_tbm pertencem a CREC_050 (VARCHAR2 nativo) — nao sao erros
    # "cgc9_tbm": "cgc_tbm_r",  <- removido, CREC_050 e nativa
    # "cgc4_tbm": "cgc_tbm_o",  <- removido, CREC_050 e nativa
}

# Sufixos legados (numérico) vs novos (varchar)
SUFIXOS_LEGADOS = ('_9', '_4', '9', '4')
SUFIXOS_NOVOS   = ('_r', '_o')

# Extensões de arquivo por tipo
EXTENSOES = {
    "java":     [".java"],
    "forms":    [".fj"],
    "frontend": [".fx", ".jsp"],
    "config":   ["pom.xml", "java.xml"],
}

# Arquivos a ignorar na analise (DTOs, Enums, etc nao tem logica CNPJ)
IGNORAR_PADROES = [
    "*Dto*", "*DTO*", "*Enum*", "*Config*",
    "*Application*", "*Exception*", "*Mapper*",
    "*package-info*"
]

# Pastas que DEVEM ser analisadas — so codigo fonte
# Arquivos fora dessas pastas sao ignorados (output, build, etc)
PASTAS_INCLUIR = {"src", "sources", "batch", "controller", "systextil"}

# Pastas que NUNCA devem ser analisadas
PASTAS_EXCLUIR = {"output", "temp", "target", ".git", "build", "node_modules",
                  "webnxj", "unify", "compilation", "ear-contents", "war-contents"}

# Extensoes analisadas — .fx e layout gerado, nao precisa verificar
EXTENSOES_ANALISAR = {".java", ".fj", ".jsp"}

# Tabelas que ja foram migradas para VARCHAR2 nativo ANTES da migracao CNPJ.
# Para essas tabelas, colunas CNPJ ja sao String — nao ha dualidade.
# O grep_engine e o Claude devem ignorar checks de dualidade para elas.
TABELAS_NATIVAS_VARCHAR2 = {
    "CREC_050",
}

# Colunas que pertencem a tabelas nativas VARCHAR2 e nunca devem ser reportadas como erro.
# Mesmo que apareçam sem o par novo, estao corretas.
COLUNAS_NATIVAS_VARCHAR2 = {
    # CREC_050 — todas as colunas CNPJ ja sao VARCHAR2 nativo
    # grupo tbm (terceiro banco mandante)
    "cgc9_tbm",
    "cgc4_tbm",
    "cgc2_tbm",
    "cgc_tbm_r",
    "cgc_tbm_o",
    # grupo sacado
    "cgc9_sacado",
    "cgc4_sacado",
    "cgc2_sacado",
    "cgc_sacado_r",
    "cgc_sacado_o",
}

# =============================================================================
# Tabelas com regras especiais de migracao CNPJ
# =============================================================================

# OPER_001 — campos genericos, substitui coluna numerica pela alfanumerica (sem duplicar)
# Antes: campo_01(NUMBER), campo_02(NUMBER) -> Depois: campo_52(VARCHAR2), campo_53(VARCHAR2)
TABELAS_OPER001 = {"OPER_001"}

# OPER_TMP — duplica campos pois e usada por Jasper/Crystal que nao serao migrados agora
# Antes: int_01, int_02 -> Depois: str_02, str_03, int_01, int_02 (ambos presentes)
TABELAS_OPERTMP = {"OPER_TMP"}

# RCNB_060 — tabela temporaria, usa campos gemeos com sufixo _STR
# nivel_estrutura -> nivel_estrutura_str
# grupo_estrutura -> grupo_estrutura_str  
# Se gemeo ocupado, usar nivel_estrutura_str > grupo_... > subgrupo_... > item_...
# Se todos ocupados, usar campo_str_01..05
TABELAS_RCNB060 = {"RCNB_060"}


# Mapeamento tabela -> pares de colunas PK CNPJ que precisam ser duplicadas
# Gerado automaticamente do CSV de PKs
# Formato: (col_legada_9, col_legada_4, col_nova_r, col_nova_o)
PARES_PK_POR_TABELA = {
    "BASI_037": [("cnpj_cliente9", "cnpj_cliente4", "cnpj_cliente_r", "cnpj_cliente_o")],
    "BASI_041": [("cnpj_cliente9", "cnpj_cliente4", "cnpj_cliente_r", "cnpj_cliente_o")],
    "BASI_245": [("fornecedor_9", "fornecedor_4", "fornecedor_r", "fornecedor_o")],
    "BASI_460": [("cnpj9", "cnpj4", "cnpj_r", "cnpj_o")],
    "BASI_572": [("terc_cnpj9", "terc_cnpj4", "terc_cnpj_r", "terc_cnpj_o")],
    "BASI_969": [("cliente9", "cliente4", "cliente_r", "cliente_o"), ("col_cliente9", "col_cliente4", "col_cliente_r", "col_cliente_o")],
    "CONS_001": [("cnpj9", "cnpj4", "cnpj_r", "cnpj_o")],
    "CONS_010": [("cnpj9", "cnpj4", "cnpj_r", "cnpj_o")],
    "COST_001": [("cnpj9", "cnpj4", "cnpj_r", "cnpj_o")],
    "CPAG_010": [("cgc_9", "cgc_4", "cgc_r", "cgc_o")],
    "CPAG_010_PED_COMPRA": [("cgc_9", "cgc_4", "cgc_r", "cgc_o")],
    "CPAG_015": [("dupl_for_for_cli9", "dupl_for_for_cli4", "dupl_for_for_cli_r", "dupl_for_for_cli_o")],
    "CPAG_090": [("cgc_9", "cgc_4", "cgc_r", "cgc_o")],
    "CPAG_168": [("tcre_cnpj9", "tcre_cnpj4", "tcre_cnpj_r", "tcre_cnpj_o"), ("tpag_cnpj9", "tpag_cnpj4", "tpag_cnpj_r", "tpag_cnpj_o")],
    "CPAG_350": [("fornecedor9", "fornecedor4", "fornecedor_r", "fornecedor_o")],
    "CPAG_450": [("cnpj_cli9", "cnpj_cli4", "cnpj_cli_r", "cnpj_cli_o")],
    "CREC_101": [("cnpj_cliente9", "cnpj_cliente4", "cnpj_cliente_r", "cnpj_cliente_o")],
    "CREC_102": [("cnpj_cliente9", "cnpj_cliente4", "cnpj_cliente_r", "cnpj_cliente_o")],
    "CREC_150": [("cgc_9", "cgc_4", "cgc_r", "cgc_o")],
    "CREC_180_SIMULA": [("cnpj9", "cnpj4", "cnpj_r", "cnpj_o")],
    "CREC_200": [("cgc_9", "cgc_4", "cgc_r", "cgc_o")],
    "CREC_209": [("cgc_9", "cgc_4", "cgc_r", "cgc_o")],
    "CREC_450": [("cnpj_cli9", "cnpj_cli4", "cnpj_cli_r", "cnpj_cli_o")],
    "CREC_563": [("cli_dup_cgc_cli9", "cli_dup_cgc_cli4", "cli_dup_cgc_cli_r", "cli_dup_cgc_cli_o")],
    "CREC_960": [("cnpj9", "cnpj4", "cnpj_r", "cnpj_o")],
    "CREC_962": [("cnpj9", "cnpj4", "cnpj_r", "cnpj_o")],
    "EFIC_012": [("cgc_cli_for9", "cgc_cli_for4", "cgc_cli_for_r", "cgc_cli_for_o")],
    "EIXO_003": [("cnpj_9", "cnpj_4", "cnpj_r", "cnpj_o")],
    "EIXO_027": [("cgc_9", "cgc_4", "cgc_r", "cgc_o")],
    "ESTQ_400": [("cliente9", "cliente4", "cliente_r", "cliente_o")],
    "ESTQ_405": [("cliente9", "cliente4", "cliente_r", "cliente_o")],
    "EXPT_040": [("cgc9", "cgc4", "cgc_r", "cgc_o")],
    "EXTC_020": [("cgc_9", "cgc_4", "cgc_r", "cgc_o")],
    "FATU_036": [("fornecedor_9", "fornecedor_4", "fornecedor_r", "fornecedor_o")],
    "FATU_052": [("cnpj9", "cnpj4", "cnpj_r", "cnpj_o")],
    "FATU_070": [("cli_dup_cgc_cli9", "cli_dup_cgc_cli4", "cli_dup_cgc_cli_r", "cli_dup_cgc_cli_o")],
    "FATU_075": [("nr_titul_cli_dup_cgc_cli9", "nr_titul_cli_dup_cgc_cli4", "nr_titul_cli_dup_cgc_cli_r", "nr_titul_cli_dup_cgc_cli_o")],
    "FATU_076": [("tit_cgc9", "tit_cgc4", "tit_cgc_r", "tit_cgc_o")],
    "FATU_125": [("transpor_forne9", "transpor_forne4", "transpor_forne_r", "transpor_forne_o")],
    "FATU_155": [("transp_forne9", "transp_forne4", "transp_forne_r", "transp_forne_o")],
    "FATU_157": [("tarifa_transp_forne9", "tarifa_transp_forne4", "tarifa_transp_forne_r", "tarifa_transp_forne_o")],
    "FATU_440": [("transp9", "transp4", "transp_r", "transp_o")],
    "FATX_070": [("cli_dupx_cgc_cli9", "cli_dupx_cgc_cli4", "cli_dupx_cgc_cli_r", "cli_dupx_cgc_cli_o")],
    "FATX_075": [("nr_titux_cli_dupx_cgc_cli9", "nr_titux_cli_dupx_cgc_cli4", "nr_titux_cli_dupx_cgc_cli_r", "nr_titux_cli_dupx_cgc_cli_o")],
    "FINA_030": [("nro_dupl_cli_dup_cgc_cli9", "nro_dupl_cli_dup_cgc_cli4", "nro_dupl_cli_dup_cgc_cli_r", "nro_dupl_cli_dup_cgc_cli_o")],
    "FINX_030": [("nro_dupx_cli_dupx_cgc_cli9", "nro_dupx_cli_dupx_cgc_cli4", "nro_dupx_cli_dupx_cgc_cli_r", "nro_dupx_cli_dupx_cgc_cli_o")],
    "FNDC_001": [("cnpj9", "cnpj4", "cnpj_r", "cnpj_o")],
    "FNDC_007": [("cgc9", "cgc4", "cgc_r", "cgc_o")],
    "HDOC_050": [("cgc9", "cgc4", "cgc_r", "cgc_o")],
    "HDOC_060": [("cnpj9", "cnpj4", "cnpj_r", "cnpj_o")],
    "HDOC_110": [("cgc9", "cgc4", "cgc_r", "cgc_o")],
    "HDOC_115": [("cgc9", "cgc4", "cgc_r", "cgc_o")],
    "INTE_055": [("cliban_cgc_cli9", "cliban_cgc_cli4", "cliban_cgc_cli_r", "cliban_cgc_cli_o")],
    "INTE_067": [("clifinan_cgc_cli9", "clifinan_cgc_cli4", "clifinan_cgc_cli_r", "clifinan_cgc_cli_o")],
    "INTE_084": [("cnpj9", "cnpj4", "cnpj_r", "cnpj_o")],
    "INTE_305": [("cnpj9", "cnpj4", "cnpj_r", "cnpj_o")],
    "INTE_385": [("cnpj9", "cnpj4", "cnpj_r", "cnpj_o")],
    "INTE_406": [("fornecedor_9", "fornecedor_4", "fornecedor_r", "fornecedor_o")],
    "INTE_510": [("cnpj9", "cnpj4", "cnpj_r", "cnpj_o")],
    "INTE_520": [("cliente_cgc9", "cliente_cgc4", "cliente_cgc_r", "cliente_cgc_o")],
    "INTE_560": [("ch_it_nf_cgc_9", "ch_it_nf_cgc_4", "ch_it_nf_cgc_r", "ch_it_nf_cgc_o")],
    "INTE_570": [("cli_dup_cgc_cli9", "cli_dup_cgc_cli4", "cli_dup_cgc_cli_r", "cli_dup_cgc_cli_o")],
    "INTE_WMS_TAGS_NOTA": [("cnpj_9", "cnpj_4", "cnpj_r", "cnpj_o")],
    "I_OBRF_017": [("cgc_cli_for_9", "cgc_cli_for_4", "cgc_cli_for_r", "cgc_cli_for_o")],
    "LIVE_001": [("cnpj9", "cnpj4", "cnpj_r", "cnpj_o")],
    "LIVE_002": [("cnpj9", "cnpj4", "cnpj_r", "cnpj_o")],
    "LOJA_020": [("cgc_9", "cgc_4", "cgc_r", "cgc_o")],
    "LOJA_060": [("cnpj9", "cnpj4", "cnpj_r", "cnpj_o")],
    "LOJA_061": [("cnpj9", "cnpj4", "cnpj_r", "cnpj_o")],
    "MONK_020": [("cgc_9", "cgc_4", "cgc_r", "cgc_o")],
    "MTTM_004": [("cgc_9", "cgc_4", "cgc_r", "cgc_o")],
    "OBRF_002": [("cgc_9", "cgc_4", "cgc_r", "cgc_o")],
    "OBRF_010": [("cgc_cli_for_9", "cgc_cli_for_4", "cgc_cli_for_r", "cgc_cli_for_o")],
    "OBRF_010_DEVOL_OK": [("cnpj9", "cnpj4", "cnpj_r", "cnpj_o")],
    "OBRF_014": [("cnpj9", "cnpj4", "cnpj_r", "cnpj_o")],
    "OBRF_015": [("capa_ent_forcli9", "capa_ent_forcli4", "capa_ent_forcli_r", "capa_ent_forcli_o")],
    "OBRF_016": [("fornecedor9", "fornecedor4", "fornecedor_r", "fornecedor_o"), ("transportadora9", "transportadora4", "transportadora_r", "transportadora_o")],
    "OBRF_017": [("cgc_cli_for_9", "cgc_cli_for_4", "cgc_cli_for_r", "cgc_cli_for_o")],
    "OBRF_019": [("num_cnpj_9", "num_cnpj_4", "num_cnpj_r", "num_cnpj_o")],
    "OBRF_056": [("capa_ent_forcli9", "capa_ent_forcli4", "capa_ent_forcli_r", "capa_ent_forcli_o")],
    "OBRF_057": [("capa_ent_forcli9", "capa_ent_forcli4", "capa_ent_forcli_r", "capa_ent_forcli_o")],
    "OBRF_060": [("fornecedor9", "fornecedor4", "fornecedor_r", "fornecedor_o")],
    "OBRF_074": [("cnpj_9", "cnpj_4", "cnpj_r", "cnpj_o")],
    "OBRF_075": [("cnpj_terceiro9", "cnpj_terceiro4", "cnpj_terceiro_r", "cnpj_terceiro_o")],
    "OBRF_076": [("cnpj_terceiro9", "cnpj_terceiro4", "cnpj_terceiro_r", "cnpj_terceiro_o")],
    "OBRF_077": [("cnpj_terceiro9", "cnpj_terceiro4", "cnpj_terceiro_r", "cnpj_terceiro_o")],
    "OBRF_095": [("cgc_terceiro9", "cgc_terceiro4", "cgc_terceiro_r", "cgc_terceiro_o")],
    "OBRF_100": [("cgcfor_forne9", "cgcfor_forne4", "cgcfor_forne_r", "cgcfor_forne_o")],
    "OBRF_115": [("fornecedor9", "fornecedor4", "fornecedor_r", "fornecedor_o")],
    "OBRF_116": [("fornecedor9", "fornecedor4", "fornecedor_r", "fornecedor_o")],
    "OBRF_122": [("cd_forn_9", "cd_forn_4", "cd_forn_r", "cd_forn_o")],
    "OBRF_130": [("cgc9", "cgc4", "cgc_r", "cgc_o")],
    "OBRF_141": [("cgc9", "cgc4", "cgc_r", "cgc_o")],
    "OBRF_160": [("cnpj9", "cnpj4", "cnpj_r", "cnpj_o")],
    "OBRF_186": [("capa_ent_forcli9", "capa_ent_forcli4", "capa_ent_forcli_r", "capa_ent_forcli_o")],
    "OBRF_195": [("cnpj_9", "cnpj_4", "cnpj_r", "cnpj_o")],
    "OBRF_250": [("fornecedor9", "fornecedor4", "fornecedor_r", "fornecedor_o")],
    "OBRF_430": [("cnpj9", "cnpj4", "cnpj_r", "cnpj_o")],
    "OBRF_431": [("cnpj9", "cnpj4", "cnpj_r", "cnpj_o")],
    "OBRF_700": [("cod_part9", "cod_part4", "cod_part_r", "cod_part_o")],
    "OBRF_701": [("cod_part9", "cod_part4", "cod_part_r", "cod_part_o")],
    "OBRF_702": [("cod_part9", "cod_part4", "cod_part_r", "cod_part_o")],
    "OBRF_709": [("cnpj9", "cnpj4", "cnpj_r", "cnpj_o")],
    "OBRF_710": [("cnpj_suc_9", "cnpj_suc_4", "cnpj_suc_r", "cnpj_suc_o")],
    "OBRF_715": [("cnpj_9", "cnpj_4", "cnpj_r", "cnpj_o")],
    "OBRF_721": [("cnpj9", "cnpj4", "cnpj_r", "cnpj_o"), ("cod_part9", "cod_part4", "cod_part_r", "cod_part_o")],
    "OBRF_722": [("cnpj9", "cnpj4", "cnpj_r", "cnpj_o"), ("cod_part9", "cod_part4", "cod_part_r", "cod_part_o")],
    "OBRF_725": [("cnpj_9", "cnpj_4", "cnpj_r", "cnpj_o")],
    "OBRF_743": [("cnpj9", "cnpj4", "cnpj_r", "cnpj_o")],
    "OBRF_772": [("cnpj9", "cnpj4", "cnpj_r", "cnpj_o")],
    "OBRF_823": [("cnpj9", "cnpj4", "cnpj_r", "cnpj_o")],
    "OBRF_851": [("terc_9", "terc_4", "terc_r", "terc_o")],
    "PCPC_012": [("cliente_cgc9", "cliente_cgc4", "cliente_cgc_r", "cliente_cgc_o"), ("fornecedor_cgc9", "fornecedor_cgc4", "fornecedor_cgc_r", "fornecedor_cgc_o")],
    "PCPF_080": [("cgc9", "cgc4", "cgc_r", "cgc_o")],
    "PCPF_081": [("cgc9", "cgc4", "cgc_r", "cgc_o")],
    "PCPT_016": [("cgc_9", "cgc_4", "cgc_r", "cgc_o")],
    "PEDI_005": [("cgc_9", "cgc_4", "cgc_r", "cgc_o")],
    "PEDI_010": [("cgc_9", "cgc_4", "cgc_r", "cgc_o")],
    "PEDI_011": [("cliente_cgc9", "cliente_cgc4", "cliente_cgc_r", "cliente_cgc_o")],
    "PEDI_012": [("cliente9", "cliente4", "cliente_r", "cliente_o")],
    "PEDI_013": [("cgc9", "cgc4", "cgc_r", "cgc_o")],
    "PEDI_014": [("cgc_9", "cgc_4", "cgc_r", "cgc_o")],
    "PEDI_015": [("cliente_cgc_9", "cliente_cgc_4", "cliente_cgc_r", "cliente_cgc_o")],
    "PEDI_028": [("cgc9", "cgc4", "cgc_r", "cgc_o")],
    "PEDI_035": [("cgc9", "cgc4", "cgc_r", "cgc_o")],
    "PEDI_055": [("cliban_cgc_cli9", "cliban_cgc_cli4", "cliban_cgc_cli_r", "cliban_cgc_cli_o")],
    "PEDI_058": [("cnpj9", "cnpj4", "cnpj_r", "cnpj_o")],
    "PEDI_065": [("cgc_9", "cgc_4", "cgc_r", "cgc_o")],
    "PEDI_067": [("clifinan_cgc_cli9", "clifinan_cgc_cli4", "clifinan_cgc_cli_r", "clifinan_cgc_cli_o")],
    "PEDI_068": [("cnpj_cliente9", "cnpj_cliente4", "cnpj_cliente_r", "cnpj_cliente_o")],
    "PEDI_074": [("cnpj9", "cnpj4", "cnpj_r", "cnpj_o")],
    "PEDI_084": [("cnpj9", "cnpj4", "cnpj_r", "cnpj_o")],
    "PEDI_103": [("cnpj9", "cnpj4", "cnpj_r", "cnpj_o")],
    "PEDI_117": [("cgc9", "cgc4", "cgc_r", "cgc_o")],
    "PEDI_118": [("cgc9", "cgc4", "cgc_r", "cgc_o")],
    "PEDI_121": [("cgc9", "cgc4", "cgc_r", "cgc_o")],
    "PEDI_150": [("cd_cli_cgc_cli9", "cd_cli_cgc_cli4", "cd_cli_cgc_cli_r", "cd_cli_cgc_cli_o")],
    "PEDI_156": [("cgc_9", "cgc_4", "cgc_r", "cgc_o")],
    "PEDI_160": [("ve_cli_cgc_cli9", "ve_cli_cgc_cli4", "ve_cli_cgc_cli_r", "ve_cli_cgc_cli_o")],
    "PEDI_170": [("cliente9", "cliente4", "cliente_r", "cliente_o")],
    "PEDI_175": [("cnpj9", "cnpj4", "cnpj_r", "cnpj_o")],
    "PEDI_178": [("cliente9", "cliente4", "cliente_r", "cliente_o")],
    "PEDI_181": [("cnpj_9", "cnpj_4", "cnpj_r", "cnpj_o")],
    "PEDI_187": [("cnpj_cli9", "cnpj_cli4", "cnpj_cli_r", "cnpj_cli_o")],
    "PEDI_230": [("cgc_9", "cgc_4", "cgc_r", "cgc_o")],
    "PEDI_235": [("cgc_9", "cgc_4", "cgc_r", "cgc_o")],
    "PEDI_240": [("infocli_cgc_cli9", "infocli_cgc_cli4", "infocli_cgc_cli_r", "infocli_cgc_cli_o")],
    "PEDI_245": [("informe_infocli_cgc_cli9", "informe_infocli_cgc_cli4", "informe_infocli_cgc_cli_r", "informe_infocli_cgc_cli_o")],
    "PEDI_265": [("cnpj9", "cnpj4", "cnpj_r", "cnpj_o")],
    "PEDI_307": [("cnpj9", "cnpj4", "cnpj_r", "cnpj_o")],
    "PEDI_341": [("cnpj9", "cnpj4", "cnpj_r", "cnpj_o")],
    "PEDI_400": [("cliente9", "cliente4", "cliente_r", "cliente_o")],
    "PEDI_405": [("cliente9", "cliente4", "cliente_r", "cliente_o")],
    "PEDI_406": [("cliente9", "cliente4", "cliente_r", "cliente_o")],
    "PEDI_410": [("cliente9", "cliente4", "cliente_r", "cliente_o")],
    "PEDI_411": [("cliente9", "cliente4", "cliente_r", "cliente_o")],
    "PEDI_420": [("cliente9", "cliente4", "cliente_r", "cliente_o")],
    "PEDI_430": [("cgc9", "cgc4", "cgc_r", "cgc_o")],
    "PEDI_450": [("cgc_9", "cgc_4", "cgc_r", "cgc_o")],
    "PEDI_475": [("cgc_9", "cgc_4", "cgc_r", "cgc_o")],
    "PEDI_490": [("cgc_9", "cgc_4", "cgc_r", "cgc_o")],
    "PEDI_711": [("cgc_9", "cgc_4", "cgc_r", "cgc_o")],
    "PEDI_799": [("cgc9", "cgc4", "cgc_r", "cgc_o")],
    "PEDI_806": [("cgc_9", "cgc_4", "cgc_r", "cgc_o")],
    "PEDI_807": [("cgc_9", "cgc_4", "cgc_r", "cgc_o")],
    "PEDI_905": [("cnpj9", "cnpj4", "cnpj_r", "cnpj_o")],
    "PEDX_010": [("cgc_9", "cgc_4", "cgc_r", "cgc_o")],
    "RCNB_030": [("cnpj9", "cnpj4", "cnpj_r", "cnpj_o")],
    "RCNB_033": [("cnpj9", "cnpj4", "cnpj_r", "cnpj_o")],
    "RCNB_080": [("cgc9", "cgc4", "cgc_r", "cgc_o")],
    "RCNB_140": [("cnpj_fornecedor9", "cnpj_fornecedor4", "cnpj_fornecedor_r", "cnpj_fornecedor_o")],
    "RCNB_200": [("cgc_9", "cgc_4", "cgc_r", "cgc_o")],
    "RCNB_204": [("cgc_9", "cgc_4", "cgc_r", "cgc_o")],
    "SPED_0000": [("num_cnpj9", "num_cnpj4", "num_cnpj_r", "num_cnpj_o")],
    "SPED_0150": [("num_cnpj9", "num_cnpj4", "num_cnpj_r", "num_cnpj_o")],
    "SPED_1601": [("part_ip_cnpj9", "part_ip_cnpj4", "part_ip_cnpj_r", "part_ip_cnpj_o"), ("part_it_cnpj9", "part_it_cnpj4", "part_it_cnpj_r", "part_it_cnpj_o")],
    "SPED_C100": [("num_cnpj_9", "num_cnpj_4", "num_cnpj_r", "num_cnpj_o")],
    "SPED_C170": [("num_cnpj_9", "num_cnpj_4", "num_cnpj_r", "num_cnpj_o")],
    "SPED_PC_0000": [("num_cnpj9", "num_cnpj4", "num_cnpj_r", "num_cnpj_o")],
    "SPED_PC_0019": [("num_cnpj_9", "num_cnpj_4", "num_cnpj_r", "num_cnpj_o"), ("num_cnpj_empr9", "num_cnpj_empr4", "num_cnpj_empr_r", "num_cnpj_empr_o")],
    "SPED_PC_0150": [("num_cnpj9", "num_cnpj4", "num_cnpj_r", "num_cnpj_o")],
    "SPED_PC_0450": [("cnpj9", "cnpj4", "cnpj_r", "cnpj_o")],
    "SPED_PC_0500": [("num_cnpj_empr9", "num_cnpj_empr4", "num_cnpj_empr_r", "num_cnpj_empr_o")],
    "SPED_PC_056": [("capa_ent_forcli9", "capa_ent_forcli4", "capa_ent_forcli_r", "capa_ent_forcli_o")],
    "SPED_PC_0600": [("num_cnpj_empr9", "num_cnpj_empr4", "num_cnpj_empr_r", "num_cnpj_empr_o")],
    "SPED_PC_C100": [("num_cnpj_9", "num_cnpj_4", "num_cnpj_r", "num_cnpj_o")],
    "SPED_PC_C170": [("num_cnpj_9", "num_cnpj_4", "num_cnpj_r", "num_cnpj_o")],
    "SUPP_010": [("cgc9", "cgc4", "cgc_r", "cgc_o")],
    "SUPR_010": [("fornecedor9", "fornecedor4", "fornecedor_r", "fornecedor_o")],
    "SUPR_011": [("cnpj_fornecedor9", "cnpj_fornecedor4", "cnpj_fornecedor_r", "cnpj_fornecedor_o")],
    "SUPR_012": [("fornecedor9", "fornecedor4", "fornecedor_r", "fornecedor_o")],
    "SUPR_015": [("fornecedor9", "fornecedor4", "fornecedor_r", "fornecedor_o")],
    "SUPR_017": [("cgc_for9", "cgc_for4", "cgc_for_r", "cgc_for_o")],
    "SUPR_021": [("fornecedor_9", "fornecedor_4", "fornecedor_r", "fornecedor_o")],
    "SUPR_025": [("cnpj_trans9", "cnpj_trans4", "cnpj_trans_r", "cnpj_trans_o")],
    "SUPR_030": [("cgc_9", "cgc_4", "cgc_r", "cgc_o")],
    "SUPR_060": [("forn_060_forne9", "forn_060_forne4", "forn_060_forne_r", "forn_060_forne_o")],
    "SUPR_132": [("cnpj_transp9", "cnpj_transp4", "cnpj_transp_r", "cnpj_transp_o")],
    "SUPR_180": [("cod_for_forne9", "cod_for_forne4", "cod_for_forne_r", "cod_for_forne_o")],
    "SUPR_200": [("cgc_9", "cgc_4", "cgc_r", "cgc_o")],
    "SUPR_210": [("cgc_for9", "cgc_for4", "cgc_for_r", "cgc_for_o")],
    "SUPR_440": [("cgc_colig9", "cgc_colig4", "cgc_colig_r", "cgc_colig_o"), ("cgc_for9", "cgc_for4", "cgc_for_r", "cgc_for_o")],
    "SUPR_580": [("cgc_forn9", "cgc_forn4", "cgc_forn_r", "cgc_forn_o")],
}