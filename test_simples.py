"""Testes de sanidade da lógica. Rode com: python test_simples.py"""

from simples import (
    calcular, calcular_ano, deslocar_mes, meses_entre, parse_num, parse_valor,
    classificar, brl,
)
from notas_xml import parsear_xml


def nota(data, valor, direcao="saida", chave=None):
    return {"data": data, "valor": valor, "direcao": direcao,
            "status": "autorizada", "chave": chave or f"{data}-{valor}-{direcao}"}


def test_helpers():
    assert deslocar_mes("2026-01", -1) == "2025-12"
    assert deslocar_mes("2026-12", 1) == "2027-01"
    assert meses_entre("2025-11", "2026-02") == ["2025-11", "2025-12", "2026-01", "2026-02"]
    assert meses_entre("2026-05", "2026-01") == []
    assert parse_num("1250.00") == 1250.0          # XML: ponto decimal
    assert parse_valor("1.250,00") == 1250.0       # manual: formato BR
    assert classificar("11111111000199", "", "11111111000199") == "saida"
    assert classificar("22222222000188", "11111111000199", "11111111000199") == "entrada"


def test_rbt12_com_abertura():
    # 12 meses de abertura a 10.000 → RBT12 = 120.000
    aberturas = {deslocar_mes("2026-06", -i): 10000 for i in range(1, 13)}
    c = calcular([nota("2026-06-10", 5000)], "III", "2026-06", aberturas)
    assert abs(c["rbt12"] - 120000) < 0.01, c["rbt12"]
    assert not c["rbt12_incompleto"]
    # DAS = receita do mês (5000) * alíquota efetiva do Anexo III na faixa de 120k
    faixa = {"aliq": 0.06, "ded": 0}  # RBT12 120k está na 1ª faixa (<=180k)
    aliq = (120000 * faixa["aliq"] - faixa["ded"]) / 120000
    assert abs(c["das_estimado"] - 5000 * aliq) < 0.01


def test_rbt12_incompleto_avisa():
    # sem abertura e sem histórico → meses faltando, sinaliza incompleto
    c = calcular([nota("2026-06-10", 5000)], "III", "2026-06")
    assert c["rbt12_incompleto"] is True
    assert len(c["meses_faltando"]) == 12


def test_inicio_de_atividade_proporcional():
    # empresa abriu em 2026-01; competência 2026-03; meses decorridos: jan, fev
    notas = [nota("2026-01-15", 10000), nota("2026-02-15", 20000), nota("2026-03-15", 30000)]
    c = calcular(notas, "III", "2026-03", inicio_atividade="2026-01")
    assert c["regime_inicio"] is True
    # média (jan+fev)/2 * 12 = (30000/2)*12 = 180000
    assert abs(c["rbt12"] - 180000) < 0.01, c["rbt12"]


def test_so_saidas_viram_receita():
    notas = [nota("2026-06-10", 5000, "saida"), nota("2026-06-11", 9000, "entrada")]
    c = calcular(notas, "III", "2026-06")
    assert c["saidas_mes"] == 5000
    assert c["entradas_mes"] == 9000
    assert c["resultado_mes"] == 5000 - 9000
    assert c["receita_mes"] == 5000  # entrada não conta como receita


def test_anual_soma_meses():
    notas = [nota(f"2026-{m:02d}-10", 1000) for m in range(1, 13)]
    a = calcular_ano(notas, "III", 2026)
    assert a["saidas_ano"] == 12000
    assert a["qtd_saidas"] == 12


def test_parse_nfe_xml():
    xml = """<?xml version="1.0"?>
    <nfeProc xmlns="http://www.portalfiscal.inf.br/nfe">
      <NFe><infNFe Id="NFe31260812345678000199550010000010421000000429">
        <ide><nNF>1042</nNF><serie>1</serie><dhEmi>2026-06-10T10:00:00-03:00</dhEmi></ide>
        <emit><CNPJ>12345678000199</CNPJ><xNome>Minha Empresa LTDA</xNome></emit>
        <dest><CNPJ>99887766000155</CNPJ><xNome>Cliente Exemplo SA</xNome></dest>
        <total><ICMSTot><vNF>1250.00</vNF></ICMSTot></total>
      </infNFe></NFe>
    </nfeProc>"""
    nota_dict, erro = parsear_xml(xml, "nota.xml", "12345678000199")
    assert erro is None
    assert nota_dict["numero"] == "1042"
    assert nota_dict["valor"] == 1250.00, nota_dict["valor"]   # não 125000!
    assert nota_dict["direcao"] == "saida"                     # empresa é a emitente
    assert nota_dict["cliente"] == "Cliente Exemplo SA"
    assert nota_dict["data"] == "2026-06-10"


def test_parse_nfe_recebida():
    xml = """<?xml version="1.0"?>
    <nfeProc xmlns="http://www.portalfiscal.inf.br/nfe">
      <NFe><infNFe Id="NFe312608...">
        <ide><nNF>77</nNF><serie>2</serie><dhEmi>2026-05-02T09:00:00-03:00</dhEmi></ide>
        <emit><CNPJ>55555555000155</CNPJ><xNome>Fornecedor XPTO</xNome></emit>
        <dest><CNPJ>12345678000199</CNPJ><xNome>Minha Empresa LTDA</xNome></dest>
        <total><ICMSTot><vNF>430.50</vNF></ICMSTot></total>
      </infNFe></NFe>
    </nfeProc>"""
    nota_dict, erro = parsear_xml(xml, "entrada.xml", "12345678000199")
    assert erro is None
    assert nota_dict["direcao"] == "entrada"           # empresa é a destinatária
    assert nota_dict["cliente"] == "Fornecedor XPTO"
    assert nota_dict["valor"] == 430.50


def test_segregacao_st_reduz_das_anexo_i():
    # RBT12 na 1ª faixa do Anexo I → aliq nominal 4%, percentual ICMS 34%
    # 1000 de receita normal + 1000 de receita ST (substituída) no mês
    notas = [
        nota("2026-06-05", 1000, "saida", chave="normal"),
        {**nota("2026-06-06", 1000, "saida", chave="st"), "ncm": "8471.30.00"},
    ]
    ncms = {"8471.30.00": {"sujeito_st": True, "papel": "substituido"}}
    aberturas = {deslocar_mes("2026-06", -i): 0 for i in range(1, 13)}  # RBT12 baixo, 1ª faixa
    c = calcular(notas, "I", "2026-06", aberturas, ncms=ncms)
    aliq = 0.04  # 1ª faixa Anexo I, dedução 0
    esperado = 1000 * aliq + 1000 * aliq * (1 - 0.34)
    assert abs(c["das_estimado"] - esperado) < 0.01, (c["das_estimado"], esperado)
    assert c["receita_mes_st"] == 1000
    assert abs(c["economia_icms_st"] - 1000 * aliq * 0.34) < 0.01


def test_segregacao_st_sem_ncm_nao_afeta():
    # nota sem NCM cadastrado não é segregada, mesmo com tabela de ncms preenchida
    notas = [nota("2026-06-05", 1000, "saida")]
    ncms = {"8471.30.00": {"sujeito_st": True, "papel": "substituido"}}
    c = calcular(notas, "I", "2026-06", ncms=ncms)
    assert c["receita_mes_st"] == 0.0


def test_segregacao_st_papel_substituto_nao_reduz():
    # se o papel cadastrado é "substituto" (não "substituido"), não há segregação
    notas = [{**nota("2026-06-05", 1000, "saida"), "ncm": "1234"}]
    ncms = {"1234": {"sujeito_st": True, "papel": "substituto"}}
    c = calcular(notas, "I", "2026-06", ncms=ncms)
    assert c["receita_mes_st"] == 0.0


def test_segregacao_st_anexo_servico_sem_efeito():
    # Anexo III não tem ICMS na partilha do DAS: segregação tem efeito zero
    notas = [{**nota("2026-06-05", 1000, "saida"), "ncm": "9999"}]
    ncms = {"9999": {"sujeito_st": True, "papel": "substituido"}}
    c = calcular(notas, "III", "2026-06", ncms=ncms)
    assert c["percentual_icms_faixa"] == 0.0
    assert c["economia_icms_st"] == 0.0


def test_parse_nfe_extrai_ncm_item_unico():
    xml = """<?xml version="1.0"?>
    <nfeProc xmlns="http://www.portalfiscal.inf.br/nfe">
      <NFe><infNFe Id="NFe31260812345678000199550010000010421000000429">
        <ide><nNF>1042</nNF><serie>1</serie><dhEmi>2026-06-10T10:00:00-03:00</dhEmi></ide>
        <emit><CNPJ>12345678000199</CNPJ><xNome>Minha Empresa LTDA</xNome></emit>
        <dest><CNPJ>99887766000155</CNPJ><xNome>Cliente Exemplo SA</xNome></dest>
        <det nItem="1"><prod><NCM>84713012</NCM><vProd>1250.00</vProd></prod></det>
        <total><ICMSTot><vNF>1250.00</vNF></ICMSTot></total>
      </infNFe></NFe>
    </nfeProc>"""
    nota_dict, erro = parsear_xml(xml, "nota.xml", "12345678000199")
    assert erro is None
    assert nota_dict["ncm"] == "84713012"
    assert nota_dict["itens_multiplos"] is False


def test_parse_nfe_multiplos_itens_nao_preenche_ncm():
    xml = """<?xml version="1.0"?>
    <nfeProc xmlns="http://www.portalfiscal.inf.br/nfe">
      <NFe><infNFe Id="NFe312608...">
        <ide><nNF>50</nNF><serie>1</serie><dhEmi>2026-06-10T10:00:00-03:00</dhEmi></ide>
        <emit><CNPJ>12345678000199</CNPJ><xNome>Minha Empresa LTDA</xNome></emit>
        <dest><CNPJ>99887766000155</CNPJ><xNome>Cliente Exemplo SA</xNome></dest>
        <det nItem="1"><prod><NCM>1111</NCM><vProd>100.00</vProd></prod></det>
        <det nItem="2"><prod><NCM>2222</NCM><vProd>200.00</vProd></prod></det>
        <total><ICMSTot><vNF>300.00</vNF></ICMSTot></total>
      </infNFe></NFe>
    </nfeProc>"""
    nota_dict, erro = parsear_xml(xml, "nota.xml", "12345678000199")
    assert erro is None
    assert nota_dict["ncm"] == ""
    assert nota_dict["itens_multiplos"] is True


if __name__ == "__main__":
    testes = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in testes:
        t()
        print(f"  ok  {t.__name__}")
    print(f"\n{len(testes)} testes passaram.")
