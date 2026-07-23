"""Testes de sanidade do estudo de preço. Rode com: python test_estudo_preco.py"""

from estudo_preco import calcular_das_sobre_valor, calcular_icms_st, calcular_difal, estudo_completo


def test_das_sobre_valor_faixa_1():
    # RBT12 = 100.000 (1ª faixa do Anexo III: aliq 6%, dedução 0)
    r = calcular_das_sobre_valor(1000, 100000, "III")
    assert abs(r["aliq_efetiva"] - 0.06) < 1e-9
    assert abs(r["valor"] - 60) < 1e-9


def test_icms_st_exemplo_conhecido():
    # Exemplo do guia: venda de 1.000, MVA 40%, aliq interna destino 18%,
    # aliq própria (interestadual) 12% → ICMS-ST esperado = R$ 132
    r = calcular_icms_st(1000, aliq_interna_destino=0.18, mva=0.40, icms_proprio_aliq=0.12)
    assert abs(r["base_st"] - 1400) < 1e-9          # 1000 * 1.4
    assert abs(r["icms_proprio"] - 120) < 1e-9      # 1000 * 0.12
    assert abs(r["icms_st"] - 132) < 0.01, r["icms_st"]  # 1400*0.18 - 120 = 132


def test_icms_st_nao_fica_negativo():
    r = calcular_icms_st(1000, aliq_interna_destino=0.12, mva=0.0, icms_proprio_aliq=0.18)
    assert r["icms_st"] == 0.0  # ICMS próprio maior que o devido no destino não gera ST negativo


def test_difal_exemplo_6_pontos():
    # aliq interna destino 18%, interestadual 12% → diferença 6 pontos
    r = calcular_difal(1000, aliq_interna_destino=0.18, aliq_interestadual=0.12)
    assert abs(r["difal"] - 60) < 1e-9
    assert r["fcp"] == 0.0


def test_difal_com_fcp():
    r = calcular_difal(1000, aliq_interna_destino=0.18, aliq_interestadual=0.12, fcp_destino=0.02)
    assert abs(r["difal"] - 60) < 1e-9
    assert abs(r["fcp"] - 20) < 1e-9
    assert abs(r["total"] - 80) < 1e-9


def test_estudo_completo_sem_st_nem_difal():
    e = estudo_completo(1000, rbt12=100000, anexo="III", custo=600)
    assert abs(e["das"]["valor"] - 60) < 1e-9
    assert e["icms_st"] is None
    assert e["difal"] is None
    assert abs(e["total_encargos"] - 60) < 1e-9
    assert abs(e["margem_liquida"] - (1000 - 60 - 600)) < 1e-9


def test_estudo_completo_substituto_com_st():
    e = estudo_completo(
        1000, rbt12=100000, anexo="III",
        tem_icms_st=True, papel_st="substituto",
        aliq_interna_destino=0.18, mva=0.40, icms_proprio_aliq=0.12,
    )
    assert e["icms_st"] is not None
    assert abs(e["icms_st"]["icms_st"] - 132) < 0.01
    # total = DAS (60) + ICMS-ST (132)
    assert abs(e["total_encargos"] - 192) < 0.01


def test_estudo_completo_substituido_apenas_avisa():
    e = estudo_completo(
        1000, rbt12=100000, anexo="III",
        tem_icms_st=True, papel_st="substituido",
    )
    assert e["aviso_substituido"] is True
    assert e["icms_st"] is None  # não recalcula ICMS-ST: já foi retido antes


def test_estudo_completo_com_extras():
    e = estudo_completo(
        1000, rbt12=100000, anexo="III",
        encargos_extras=[{"nome": "Taxa de cartão", "valor": 30}, {"nome": "Frete", "valor": 50}],
    )
    assert abs(e["total_extras"] - 80) < 1e-9
    assert abs(e["total_encargos"] - (60 + 80)) < 1e-9


if __name__ == "__main__":
    testes = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in testes:
        t()
        print(f"  ok  {t.__name__}")
    print(f"\n{len(testes)} testes passaram.")
