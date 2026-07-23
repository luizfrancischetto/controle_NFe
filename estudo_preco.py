"""
Estudo de preço — encargos tributários sobre uma venda/nota, para empresa
optante pelo Simples Nacional em Minas Gerais.

Escopo e limites (leia antes de usar em produção):

- O DAS (Simples Nacional) é calculado com a MESMA alíquota efetiva do
  restante do app (função `simples.calcular`), então já reflete o RBT12
  correto da empresa.
- O ICMS-ST NÃO faz parte do DAS — por força do art. 13, §1º, XIII, "a" da
  LC 123/2006, é recolhido separadamente, fora do regime unificado. Este
  módulo calcula o ICMS-ST pela fórmula padrão (Convênio ICMS 52/2017):

      Base ST = (valor da operação + frete + seguro + outras despesas) × (1 + MVA)
      ICMS-ST = Base ST × alíquota interna do destino − ICMS próprio da operação

  MVA e alíquota interna são definidos por estado, por convênio/protocolo e
  variam por NCM/CEST do produto — **não há uma tabela única e este módulo
  não tenta advinhá-las**. Você informa os percentuais aplicáveis ao seu
  produto (consulte o RICMS/MG vigente ou seu contador). Quando o optante
  pelo Simples Nacional é o substituto tributário em operação interestadual,
  o Convênio ICMS 35/2011 determina o uso da "MVA ST original" (não a "MVA
  ajustada") — o formulário lembra isso.
- Quando a empresa é a **substituída** (recebeu a mercadoria com o ICMS-ST já
  retido por quem vendeu para ela), ela não recolhe ICMS de novo sobre essa
  revenda — mas a apuração correta exige segregar essa receita no PGDAS-D
  (ela entra numa faixa de tributação sem o percentual de ICMS). Este app
  ainda não segrega receita por tipo de tributação no cálculo do DAS geral;
  o Estudo de Preço apenas sinaliza a situação — a segregação fina deve ser
  conferida no PGDAS-D com o contador.
- O DIFAL (diferencial de alíquota) aparece em vendas interestaduais a
  consumidor final não contribuinte (EC 87/2015) ou em compras para uso e
  consumo próprio. Fórmula: Base × (alíquota interna destino − alíquota
  interestadual) [+ FCP do destino, se houver].
- Nenhum valor de DAS, ICMS-ST ou DIFAL aqui é uma apuração oficial. Use como
  estudo/estimativa e confirme com seu contador antes de precificar de fato.
"""

from __future__ import annotations

from simples import ANEXOS


def calcular_das_sobre_valor(valor: float, rbt12: float, anexo: str) -> dict:
    """DAS estimado para um valor específico, dada a alíquota efetiva vigente
    (mesma fórmula usada no restante do app, aplicada aqui a um valor pontual
    em vez do faturamento do mês inteiro)."""
    faixas = ANEXOS[anexo]["faixas"]
    faixa = next((f for f in faixas if max(rbt12, 1) <= f["ate"]), faixas[-1])
    aliq_efetiva = ((rbt12 * faixa["aliq"] - faixa["ded"]) / rbt12) if rbt12 > 0 else faixas[0]["aliq"]
    aliq_efetiva = max(aliq_efetiva, 0.0)
    return {
        "aliq_efetiva": aliq_efetiva,
        "aliq_nominal": faixa["aliq"],
        "valor": valor * aliq_efetiva,
    }


def calcular_icms_st(valor_operacao: float, aliq_interna_destino: float, mva: float,
                      icms_proprio_aliq: float = 0.0, frete: float = 0.0,
                      seguro: float = 0.0, outras_despesas: float = 0.0) -> dict:
    """ICMS-ST pela fórmula do Convênio ICMS 52/2017.

    `aliq_interna_destino`, `mva` e `icms_proprio_aliq` em fração (ex.: 0.18).
    O ICMS próprio é calculado sobre o valor da operação (sem os acréscimos).
    """
    base_propria = valor_operacao + frete + seguro + outras_despesas
    base_st = base_propria * (1 + mva)
    icms_proprio = valor_operacao * icms_proprio_aliq
    icms_st = base_st * aliq_interna_destino - icms_proprio
    return {
        "base_propria": base_propria,
        "base_st": base_st,
        "icms_proprio": icms_proprio,
        "icms_st": max(icms_st, 0.0),
    }


def calcular_difal(valor_operacao: float, aliq_interna_destino: float,
                    aliq_interestadual: float, fcp_destino: float = 0.0) -> dict:
    """DIFAL (EC 87/2015) + FCP do estado de destino, se houver.

    Percentuais em fração (ex.: 0.18). Retorna os dois valores separados,
    porque em MG o FCP tem destinação e tratamento próprios.
    """
    diferenca = max(aliq_interna_destino - aliq_interestadual, 0.0)
    difal = valor_operacao * diferenca
    fcp = valor_operacao * fcp_destino
    return {"difal": difal, "fcp": fcp, "total": difal + fcp}


def estudo_completo(
    valor_operacao: float,
    rbt12: float,
    anexo: str,
    *,
    custo: float = 0.0,
    tem_icms_st: bool = False,
    papel_st: str = "substituto",  # "substituto" | "substituido"
    aliq_interna_destino: float = 0.0,
    mva: float = 0.0,
    icms_proprio_aliq: float = 0.0,
    frete: float = 0.0,
    seguro: float = 0.0,
    outras_despesas_st: float = 0.0,
    tem_difal: bool = False,
    aliq_interestadual: float = 0.0,
    fcp_destino: float = 0.0,
    encargos_extras: list[dict] | None = None,  # [{"nome": str, "valor": float}]
) -> dict:
    """Monta o estudo de preço completo para um valor de operação.

    Reúne DAS, ICMS-ST (se aplicável e a empresa for substituta), DIFAL (se
    aplicável) e quaisquer encargos extras informados (frete, taxas de
    cartão, comissões etc.), e devolve o total de encargos e a margem líquida
    se um custo tiver sido informado.
    """
    encargos_extras = encargos_extras or []

    das = calcular_das_sobre_valor(valor_operacao, rbt12, anexo)

    icms_st = None
    aviso_substituido = False
    if tem_icms_st:
        if papel_st == "substituto":
            icms_st = calcular_icms_st(
                valor_operacao, aliq_interna_destino, mva, icms_proprio_aliq,
                frete, seguro, outras_despesas_st,
            )
        else:
            aviso_substituido = True

    difal = None
    if tem_difal:
        difal = calcular_difal(valor_operacao, aliq_interna_destino, aliq_interestadual, fcp_destino)

    total_extras = sum(e.get("valor", 0.0) for e in encargos_extras)

    total_encargos = das["valor"]
    if icms_st:
        total_encargos += icms_st["icms_st"]
    if difal:
        total_encargos += difal["total"]
    total_encargos += total_extras

    resultado = {
        "valor_operacao": valor_operacao,
        "das": das,
        "icms_st": icms_st,
        "aviso_substituido": aviso_substituido,
        "difal": difal,
        "encargos_extras": encargos_extras,
        "total_extras": total_extras,
        "total_encargos": total_encargos,
        "liquido_apos_encargos": valor_operacao - total_encargos,
    }
    if custo > 0:
        margem = valor_operacao - total_encargos - custo
        resultado["custo"] = custo
        resultado["margem_liquida"] = margem
        resultado["margem_pct"] = (margem / valor_operacao) if valor_operacao else 0.0

    return resultado
