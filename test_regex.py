import re
from collections import defaultdict
import sys
sys.path.append('.')
from grep_engine import _e_coluna_cnpj, _achar

def detectar_implements_cnpj_nao_duplicado(texto_limpo):
    erros = []
    
    # 1. Verifica se a classe parece implementar alguma interface
    if ' implements ' not in texto_limpo and '\nimplements ' not in texto_limpo:
        return erros
        
    # Regex para pegar declaracao de metodos:
    # Captura algo como: public void setCnpj(int cgc9, int cgc4, int cgc2) {
    method_pattern = re.compile(r'\b([a-zA-Z_]\w*)\s*\(([^)]*)\)\s*(?:throws\s+[^{]+)?\s*\{')
    
    metodos = defaultdict(list)
    
    for m in method_pattern.finditer(texto_limpo):
        m_name = m.group(1)
        # Ignorar constructs que parecem chamadas de metodo
        if m_name in ['if', 'while', 'for', 'switch', 'catch', 'synchronized', 'else']:
            continue
            
        params_str = m.group(2)
        idx_match = m.start()
        # Aproximar contagem de linha contando as quebras antes do match
        num_linha = texto_limpo[:idx_match].count('\n') + 1
        
        # Verificar se algum dos parametros e' ref a CNPJ
        tem_cnpj = False
        if params_str.strip():
            for param in params_str.split(','):
                param = param.strip()
                if not param: continue
                parts = param.split()
                if len(parts) >= 2:
                    ptype = parts[-2]
                    pname = parts[-1]
                    
                    # Checar se e tipo CNPJ ou nome sugere CNPJ (via config config.PALAVRAS_CNPJ)
                    if ptype == 'CNPJ' or _e_coluna_cnpj(pname):
                        tem_cnpj = True
                        break
                        
        metodos[m_name].append({
            "linha": num_linha,
            "params_str": params_str,
            "tem_cnpj": tem_cnpj
        })
        
    # Verificar se os metodos com ref ao CNPJ tem a sobrecarga correspondente
    for m_name, overloads in metodos.items():
        cnpj_overloads = [ov for ov in overloads if ov["tem_cnpj"]]
        
        # Se tem exatmente 1 overload lidando com CNPJ, significa que a 
        # equivalencia legado/novo (int vs CNPJ/String) nao foi criada.
        if len(cnpj_overloads) == 1:
            ov = cnpj_overloads[0]
            _achar(
                erros, 
                ov["linha"], 
                "BUG_IMPLEMENTS_NAO_DUPLICADO", 
                "ERRO", 
                f"Classe com 'implements'. O metodo '{m_name}' possui parametro CNPJ mas nao foi duplicado (esperado overloads legado/novo)."
            )
            
    return erros

texto_limpo = """
public class X implements Y {
    public void setCnpj(int cgc9, int cgc4, int cgc2) {
    }
}
"""
print(detectar_implements_cnpj_nao_duplicado(texto_limpo))
