# =============================================================================
# config.py — Conhecimento de domínio da migração CNPJ alfanumérico
# Atualize aqui conforme a migração evolui. O restante do código não muda.
# =============================================================================

# Palavras-chave que identificam variáveis/colunas relacionadas a CNPJ
PALAVRAS_CNPJ = (
    'cnpj', 'cgc', 'cod_part', 'corretora', 'despachante',
    'courier', 'facc', 'tran', 'terc', 'cons', 'cli', 'for',
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
    "FATU_036", "FATU_050", "FATU_052", "FATU_070", "FATU_075", "FATU_076", "FATU_120", "FATU_125", "FATU_155", "FATU_157", "FATU_440",
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
    "OPER_001", "OPER_284", "OPER_TMP",
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
}

# Sufixos legados (numérico) vs novos (varchar)
SUFIXOS_LEGADOS = ('_9', '_4', '9', '4')
SUFIXOS_NOVOS   = ('_r', '_o')

# Extensões de arquivo por tipo
EXTENSOES = {
    "java":     [".java"],
    "forms":    [".fj"],
    "frontend": [".jsp"],
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