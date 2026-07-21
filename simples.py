"""
Regras de domínio do Simples Nacional (MG) — sem dependência de interface.

Reúne as tabelas dos Anexos, o cálculo do RBT12 (com receita de abertura e a
regra proporcional de início de atividade), a alíquota efetiva, o DAS estimado
e a agregação mensal/anual. Tudo em funções puras, fáceis de testar.

Os valores de DAS são ESTIMATIVAS pelas tabelas da LC 123/2006; a apuração
oficial é feita no PGDAS-D.
"""

from __future__ import annotations

import re
from datetime import date

# ---------------------------------------------------------------- tabelas

ANEXOS = {
    "I": {"nome": "Anexo I — Comércio", "faixas": [
        {"ate": 180000, "aliq": 0.04, "ded": 0}, {"ate": 360000, "aliq": 0.073, "ded": 5940},
        {"ate": 720000, "aliq": 0.095, "ded": 13860}, {"ate": 1800000, "aliq": 0.107, "ded": 22500},
        {"ate": 3600000, "aliq": 0.143, "ded": 87300}, {"ate": 4800000, "aliq": 0.19, "ded": 378000}]},
    "II": {"nome": "Anexo II — Indústria", "faixas": [
        {"ate": 180000, "aliq": 0.045, "ded": 0}, {"ate": 360000, "aliq": 0.078, "ded": 5940},
        {"ate": 720000, "aliq": 0.10, "ded": 13860}, {"ate": 1800000, "aliq": 0.112, "ded": 22500},
        {"ate": 3600000, "aliq": 0.147, "ded": 85500}, {"ate": 4800000, "aliq": 0.30, "ded": 720000}]},
    "III": {"nome": "Anexo III — Serviços", "faixas": [
        {"ate": 180000, "aliq": 0.06, "ded": 0}, {"ate": 360000, "aliq": 0.112, "ded": 9360},
        {"ate": 720000, "aliq": 0.135, "ded": 17640}, {"ate": 1800000, "aliq": 0.16, "ded": 35640},
        {"ate": 3600000, "aliq": 0.21, "ded": 125640}, {"ate": 4800000, "aliq": 0.33, "ded": 648000}]},
    "IV": {"nome": "Anexo IV — Serviços (construção, advocacia…)", "faixas": [
        {"ate": 180000, "aliq": 0.045, "ded": 0}, {"ate": 360000, "aliq": 0.09, "ded": 8100},
        {"ate": 720000, "aliq": 0.102, "ded": 12420}, {"ate": 1800000, "aliq": 0.14, "ded": 39780},
        {"ate": 3600000, "aliq": 0.22, "ded": 183780}, {"ate": 4800000, "aliq": 0.33, "ded": 828000}]},
    "V": {"nome": "Anexo V — Serviços intelectuais", "faixas": [
        {"ate": 180000, "aliq": 0.155, "ded": 0}, {"ate": 360000, "aliq": 0.18, "ded": 4500},
        {"ate": 720000, "aliq": 0.195, "ded": 9900}, {"ate": 1800000, "aliq": 0.205, "ded": 17100},
        {"ate": 3600000, "aliq": 0.23, "ded": 62100}, {"ate": 4800000, "aliq": 0.305, "ded": 540000}]},
}

LIMITE_SIMPLES = 4_800_000
SUBLIMITE_MG = 3_600_000

MESES_ABREV = ["jan", "fev", "mar", "abr", "mai", "jun",
               "jul", "ago", "set", "out", "nov", "dez"]
MESES_NOME = ["janeiro", "fevereiro", "março", "abril", "maio", "junho",
              "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"]

# ---------------------------------------------------------------- utilidades

def so_digitos(s) -> str:
    return re.sub(r"\D", "", s or "")


def parse_num(s) -> float:
    """Valor vindo de XML: ponto como separador decimal ('1250.00')."""
    try:
        return float(str(s or "").strip())
    except ValueError:
        return 0.0


def parse_valor(s) -> float:
    """Digitação manual em formato brasileiro ('1.250,00')."""
    if isinstance(s, (int, float)):
        return float(s)
    limpo = re.sub(r"[R$\s.]", "", str(s)).replace(",", ".")
    try:
        return float(limpo)
    except ValueError:
        return 0.0


def mes_chave(data_iso: str | None) -> str:
    return data_iso[:7] if data_iso else ""


def deslocar_mes(ref_key: str, delta: int) -> str:
    a, m = map(int, ref_key.split("-"))
    total = a * 12 + (m - 1) + delta
    return f"{total // 12}-{total % 12 + 1:02d}"


def meses_entre(a_key: str, b_key: str) -> list[str]:
    """Chaves 'YYYY-MM' de a_key até b_key, inclusive (vazio se a_key > b_key)."""
    if not a_key or not b_key or a_key > b_key:
        return []
    a1, a2 = map(int, a_key.split("-"))
    b1, b2 = map(int, b_key.split("-"))
    cur, fim = a1 * 12 + (a2 - 1), b1 * 12 + (b2 - 1)
    out = []
    while cur <= fim:
        out.append(f"{cur // 12}-{cur % 12 + 1:02d}")
        cur += 1
    return out


def rotulo_mes(ref_key: str) -> str:
    a, m = map(int, ref_key.split("-"))
    return f"{MESES_NOME[m - 1]} de {a}"


def rotulo_curto(ref_key: str) -> str:
    a, m = map(int, ref_key.split("-"))
    return f"{MESES_ABREV[m - 1]}/{str(a)[2:]}"


def classificar(cnpj_emit, cnpj_dest, cnpj_empresa) -> str:
    """'saida' = empresa emitiu (receita); 'entrada' = empresa recebeu."""
    emp = so_digitos(cnpj_empresa)
    e = so_digitos(cnpj_emit)
    d = so_digitos(cnpj_dest)
    if not emp:
        return "saida"

    def igual(a, b):
        return bool(a and b and (a == b or a[:8] == b[:8]))

    if igual(e, emp):
        return "saida"
    if igual(d, emp):
        return "entrada"
    return "saida"


# ---------------------------------------------------------------- cálculo mensal

def calcular(notas, anexo, ref_key, aberturas=None, inicio_atividade=""):
    """Apura a competência `ref_key` ('YYYY-MM').

    Só notas emitidas (direcao 'saida') compõem a receita. O RBT12 usa a receita
    real dos 12 meses anteriores, vinda das notas ou da receita de abertura
    informada; meses sem dado são reportados em `meses_faltando`.
    """
    aberturas = aberturas or {}
    inicio = inicio_atividade or ""
    ref_ano, ref_mes = map(int, ref_key.split("-"))
    chave_atual = ref_key

    receita = [n for n in notas
               if n.get("status") == "autorizada" and (n.get("direcao") or "saida") == "saida"]
    recebidas = [n for n in notas
                 if n.get("status") == "autorizada" and n.get("direcao") == "entrada"]

    notas_por_mes: dict[str, float] = {}
    for n in receita:
        k = mes_chave(n.get("data"))
        notas_por_mes[k] = notas_por_mes.get(k, 0.0) + n.get("valor", 0.0)

    def receita_do_mes(k):
        if k in notas_por_mes:
            return notas_por_mes[k]
        if k in aberturas and aberturas[k] not in (None, ""):
            try:
                return float(aberturas[k])
            except (TypeError, ValueError):
                return None
        return None

    def origem_do_mes(k):
        if k in notas_por_mes:
            return "notas"
        if k in aberturas and aberturas[k] not in (None, ""):
            return "abertura"
        return "vazio"

    receita_mes = receita_do_mes(chave_atual) or 0.0
    prev_key = deslocar_mes(ref_key, -1)

    rbt12 = 0.0
    faltando: list[str] = []
    regime_inicio = False

    if inicio and inicio <= ref_key:
        decorridos = meses_entre(inicio, prev_key)
        if len(decorridos) < 12:
            regime_inicio = True
            if len(decorridos) == 0:
                rbt12 = receita_mes * 12  # 1º mês de atividade
            else:
                soma, cont = 0.0, 0
                for k in decorridos:
                    v = receita_do_mes(k)
                    if v is None:
                        faltando.append(k)
                    else:
                        soma += v
                        cont += 1
                rbt12 = (soma / cont) * 12 if cont > 0 else 0.0

    if not regime_inicio:
        soma = 0.0
        for i in range(12, 0, -1):
            k = deslocar_mes(ref_key, -i)
            if inicio and k < inicio:
                continue  # antes de existir a empresa → legitimamente 0
            v = receita_do_mes(k)
            if v is None:
                faltando.append(k)
            else:
                soma += v
        rbt12 = soma

    faixas = ANEXOS[anexo]["faixas"]
    faixa = next((f for f in faixas if max(rbt12, 1) <= f["ate"]), faixas[-1])
    aliq_efetiva = ((rbt12 * faixa["aliq"] - faixa["ded"]) / rbt12) if rbt12 > 0 else faixas[0]["aliq"]
    aliq_efetiva = max(aliq_efetiva, 0.0)
    das_estimado = receita_mes * aliq_efetiva

    acumulado_ano = 0.0
    for k in meses_entre(f"{ref_ano}-01", chave_atual):
        v = receita_do_mes(k)
        if v is not None:
            acumulado_ano += v

    despesas_ano = sum(
        n.get("valor", 0.0) for n in recebidas
        if n.get("data") and n["data"][:7] <= chave_atual and n["data"].startswith(str(ref_ano))
    )

    serie = []
    for i in range(11, -1, -1):
        k = deslocar_mes(ref_key, -i)
        serie.append({
            "label": rotulo_curto(k),
            "valor": receita_do_mes(k) or 0.0,
            "atual": k == chave_atual,
            "origem": origem_do_mes(k),
            "key": k,
        })

    saidas_mes = notas_por_mes.get(chave_atual, 0.0)
    qtd_saidas_mes = sum(1 for n in receita if mes_chave(n.get("data")) == chave_atual)
    recebidas_mes = [n for n in recebidas if mes_chave(n.get("data")) == chave_atual]
    entradas_mes = sum(n.get("valor", 0.0) for n in recebidas_mes)
    qtd_entradas_mes = len(recebidas_mes)

    hoje = date.today()
    chave_hoje = f"{hoje.year}-{hoje.month:02d}"

    return {
        "receita_mes": receita_mes,
        "rbt12": rbt12,
        "aliq_efetiva": aliq_efetiva,
        "das_estimado": das_estimado,
        "acumulado_ano": acumulado_ano,
        "despesas_ano": despesas_ano,
        "serie": serie,
        "faixa_nominal": faixa["aliq"],
        "eh_mes_atual": ref_key == chave_hoje,
        "rbt12_incompleto": len(faltando) > 0,
        "meses_faltando": faltando,
        "regime_inicio": regime_inicio,
        "saidas_mes": saidas_mes,
        "qtd_saidas_mes": qtd_saidas_mes,
        "entradas_mes": entradas_mes,
        "qtd_entradas_mes": qtd_entradas_mes,
        "resultado_mes": saidas_mes - entradas_mes,
    }


# ---------------------------------------------------------------- cálculo anual

def calcular_ano(notas, anexo, ano, aberturas=None, inicio_atividade=""):
    """Agrega o ano inteiro reaproveitando o cálculo de cada competência."""
    saidas = entradas = das = 0.0
    qtd_saidas = qtd_entradas = 0
    rbt12_incompleto = False
    receita_ano = 0.0
    serie = []
    for m in range(1, 13):
        key = f"{ano}-{m:02d}"
        c = calcular(notas, anexo, key, aberturas, inicio_atividade)
        saidas += c["saidas_mes"]
        entradas += c["entradas_mes"]
        das += c["das_estimado"]
        qtd_saidas += c["qtd_saidas_mes"]
        qtd_entradas += c["qtd_entradas_mes"]
        if c["saidas_mes"] > 0 and c["rbt12_incompleto"]:
            rbt12_incompleto = True
        if m == 12:
            receita_ano = c["acumulado_ano"]
        serie.append({"label": MESES_ABREV[m - 1], "valor": c["saidas_mes"], "key": key})

    return {
        "saidas_ano": saidas,
        "entradas_ano": entradas,
        "das_ano": das,
        "qtd_saidas": qtd_saidas,
        "qtd_entradas": qtd_entradas,
        "resultado_ano": saidas - entradas,
        "serie": serie,
        "rbt12_incompleto": rbt12_incompleto,
        "acumulado_ano": receita_ano,
    }


# ---------------------------------------------------------------- formatação

def brl(v) -> str:
    v = v or 0.0
    s = f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {s}"


def pct(v) -> str:
    return f"{(v or 0.0) * 100:.2f}%".replace(".", ",")
