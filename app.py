"""
Controle de Notas — Simples Nacional (MG) · interface Streamlit.

Execute com:  streamlit run app.py
Os dados são gravados em controle_dados.json na pasta do projeto.
"""

from __future__ import annotations

from datetime import date

import pandas as pd
import streamlit as st

import armazenamento as store
from notas_xml import parsear_xml
from simples import (
    ANEXOS, LIMITE_SIMPLES, SUBLIMITE_MG,
    calcular, calcular_ano, deslocar_mes, rotulo_mes, mes_chave,
    brl, pct, so_digitos,
)

st.set_page_config(page_title="Controle de Notas · Simples MG", page_icon="🧾", layout="wide")

# ------------------------------------------------------------ estado

if "dados" not in st.session_state:
    st.session_state.dados = store.carregar()
if "mes_ref" not in st.session_state:
    h = date.today()
    st.session_state.mes_ref = f"{h.year}-{h.month:02d}"
if "ano_ref" not in st.session_state:
    st.session_state.ano_ref = date.today().year

dados = st.session_state.dados


def salvar():
    store.salvar(dados)


def fmt_cnpj(v: str) -> str:
    d = so_digitos(v)[:14]
    if len(d) == 14:
        return f"{d[:2]}.{d[2:5]}.{d[5:8]}/{d[8:12]}-{d[12:]}"
    return v


# ------------------------------------------------------------ cabeçalho

col_a, col_b = st.columns([3, 1])
with col_a:
    st.caption("SIMPLES NACIONAL · MINAS GERAIS")
    st.title(dados.get("empresa") or "Minha Empresa")
    if dados.get("cnpj"):
        st.caption(f"CNPJ {fmt_cnpj(dados['cnpj'])}")
with col_b:
    st.markdown(
        f"<div style='text-align:right;font-weight:700;color:#14634A'>"
        f"{ANEXOS[dados['anexo']]['nome'].split(' — ')[0]}</div>",
        unsafe_allow_html=True,
    )

aba_painel, aba_importar, aba_notas, aba_hist, aba_manual, aba_empresa = st.tabs(
    ["Painel", "Importar XML", f"Notas ({len(dados['notas'])})", "Histórico", "Manual", "Empresa"]
)


# ============================================================ PAINEL

def regua_limites(acumulado, titulo):
    st.progress(min(acumulado / LIMITE_SIMPLES, 1.0))
    st.caption(f"{titulo} · {brl(acumulado)}  —  sublimite MG {brl(SUBLIMITE_MG)} · teto {brl(LIMITE_SIMPLES)}")
    if acumulado > LIMITE_SIMPLES:
        st.error("Receita acima do teto do Simples. Procure seu contador: risco de exclusão do regime.")
    elif acumulado > SUBLIMITE_MG:
        st.warning("Acima do sublimite de MG: ICMS e ISS passam a ser apurados fora do DAS.")


with aba_painel:
    if not dados["notas"]:
        st.info("Nenhuma nota ainda. Comece importando seus XMLs na aba **Importar XML**.")
    else:
        modo = st.radio("Período", ["Mês", "Ano"], horizontal=True, label_visibility="collapsed")

        if modo == "Mês":
            nav1, nav2, nav3 = st.columns([1, 3, 1])
            with nav1:
                if st.button("‹ mês anterior", use_container_width=True):
                    st.session_state.mes_ref = deslocar_mes(st.session_state.mes_ref, -1)
            with nav3:
                if st.button("próximo mês ›", use_container_width=True):
                    st.session_state.mes_ref = deslocar_mes(st.session_state.mes_ref, 1)
            with nav2:
                st.markdown(f"<h3 style='text-align:center;margin:0'>{rotulo_mes(st.session_state.mes_ref)}</h3>",
                            unsafe_allow_html=True)

            c = calcular(dados["notas"], dados["anexo"], st.session_state.mes_ref,
                         dados["aberturas"], dados["inicio_atividade"])

            if c["rbt12_incompleto"]:
                st.warning(
                    f"RBT12 incompleto: faltam dados de {len(c['meses_faltando'])} mês(es) dos 12 "
                    "anteriores — a alíquota está subestimada. Complete na aba **Histórico**."
                )

            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Faturamento do mês", brl(c["receita_mes"]),
                      help=f"{c['qtd_saidas_mes']} nota(s) emitida(s)")
            m2.metric("RBT12", brl(c["rbt12"]),
                      help="regra proporcional (início de atividade)" if c["regime_inicio"] else "12 meses anteriores")
            m3.metric("Alíquota efetiva", pct(c["aliq_efetiva"]),
                      help=f"nominal {pct(c['faixa_nominal'])}")
            m4.metric("DAS estimado do mês", brl(c["das_estimado"]), help="vence dia 20 do mês seguinte")

            st.subheader("Entradas e saídas")
            e1, e2, e3 = st.columns(3)
            e1.metric("Saídas — emitidas", brl(c["saidas_mes"]), help=f"{c['qtd_saidas_mes']} nota(s) · receita")
            e2.metric("Entradas — recebidas", brl(c["entradas_mes"]), help=f"{c['qtd_entradas_mes']} nota(s) · compras")
            e3.metric("Resultado (saídas − entradas)", brl(c["resultado_mes"]))

            st.subheader("Limites")
            regua_limites(c["acumulado_ano"], f"Receita acumulada em {st.session_state.mes_ref[:4]}")

            st.subheader("Faturamento — 12 meses")
            df = pd.DataFrame(c["serie"]).set_index("label")[["valor"]]
            st.bar_chart(df, color="#14634A")

        else:  # Ano
            nav1, nav2, nav3 = st.columns([1, 3, 1])
            with nav1:
                if st.button("‹ ano anterior", use_container_width=True):
                    st.session_state.ano_ref -= 1
            with nav3:
                if st.button("próximo ano ›", use_container_width=True):
                    st.session_state.ano_ref += 1
            with nav2:
                st.markdown(f"<h3 style='text-align:center;margin:0'>{st.session_state.ano_ref}</h3>",
                            unsafe_allow_html=True)

            a = calcular_ano(dados["notas"], dados["anexo"], st.session_state.ano_ref,
                             dados["aberturas"], dados["inicio_atividade"])

            if a["rbt12_incompleto"]:
                st.warning("Alguns meses com receita têm RBT12 incompleto — o DAS anual está subestimado. "
                           "Complete na aba **Histórico**.")

            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Faturamento do ano", brl(a["saidas_ano"]), help=f"{a['qtd_saidas']} nota(s) emitida(s)")
            m2.metric("Entradas do ano", brl(a["entradas_ano"]), help=f"{a['qtd_entradas']} nota(s) recebida(s)")
            m3.metric("Resultado do ano", brl(a["resultado_ano"]), help="saídas − entradas")
            m4.metric("DAS estimado do ano", brl(a["das_ano"]), help="soma das 12 competências")

            st.subheader("Limites")
            regua_limites(a["acumulado_ano"], f"Receita do ano {st.session_state.ano_ref}")

            st.subheader(f"Saídas mês a mês em {st.session_state.ano_ref}")
            df = pd.DataFrame(a["serie"]).set_index("label")[["valor"]]
            st.bar_chart(df, color="#14634A")


# ============================================================ IMPORTAR XML

with aba_importar:
    if not dados.get("cnpj"):
        st.warning("Informe o CNPJ da empresa na aba **Empresa** para separar emitidas de recebidas.")

    arquivos = st.file_uploader("Arraste os XMLs (NF-e e NFS-e), vários de uma vez",
                                type="xml", accept_multiple_files=True)
    if arquivos:
        previa, erros = [], []
        for f in arquivos:
            try:
                conteudo = f.getvalue().decode("utf-8", errors="replace")
                n, motivo = parsear_xml(conteudo, f.name, dados.get("cnpj", ""))
                if n:
                    previa.append(n)
                else:
                    erros.append(motivo)
            except Exception as exc:  # noqa: BLE001
                erros.append(f"{f.name}: {exc}")

        for e in erros:
            st.error(f"⚠ {e}")

        if previa:
            emit = sum(n["valor"] for n in previa if n["direcao"] == "saida")
            receb = sum(n["valor"] for n in previa if n["direcao"] == "entrada")
            st.write(f"**{len(previa)}** nota(s) lida(s) — emitidas {brl(emit)} · recebidas {brl(receb)}")
            st.dataframe(
                [{"Tipo": n["tipo"], "Número": n["numero"], "Direção": "emitida" if n["direcao"] == "saida" else "recebida",
                  "Cliente/Fornecedor": n["cliente"], "Data": n["data"], "Valor": brl(n["valor"])} for n in previa],
                use_container_width=True, hide_index=True,
            )
            if st.button(f"Adicionar {len(previa)} nota(s)", type="primary"):
                dados["notas"], add, dup = store.dedup_por_chave(dados["notas"], previa)
                salvar()
                msg = f"✓ {add} nota(s) adicionada(s)."
                if dup:
                    msg += f" {dup} já existia(m) (ignorada(s) pela chave)."
                st.success(msg)

    st.caption("Os XMLs vêm do seu emissor (emitidas) e do portal da SEFAZ ou do contador (recebidas). "
               "Tudo é processado localmente. O app não busca notas na SEFAZ — isso exigiria certificado digital.")


# ============================================================ NOTAS

with aba_notas:
    if not dados["notas"]:
        st.info("Nenhuma nota registrada.")
    else:
        f1, f2 = st.columns([2, 1])
        busca = f1.text_input("Buscar por cliente, número ou descrição", "")
        filtro = f2.selectbox("Filtro", ["Todas", "Emitidas (receita)", "Recebidas (entrada)", "NF-e", "NFS-e"])

        def visivel(n):
            if filtro == "Emitidas (receita)" and (n.get("direcao") or "saida") != "saida":
                return False
            if filtro == "Recebidas (entrada)" and n.get("direcao") != "entrada":
                return False
            if filtro in ("NF-e", "NFS-e") and n.get("tipo") != filtro:
                return False
            if busca:
                q = busca.lower()
                return (q in (n.get("cliente") or "").lower()
                        or q in str(n.get("numero") or "")
                        or q in (n.get("descricao") or "").lower())
            return True

        lista = sorted([n for n in dados["notas"] if visivel(n)],
                       key=lambda n: n.get("data") or "", reverse=True)

        st.dataframe(
            [{"Tipo": n["tipo"], "Número": n.get("numero"),
              "Direção": "emitida" if (n.get("direcao") or "saida") == "saida" else "recebida",
              "Cliente/Fornecedor": n.get("cliente"), "Data": n.get("data"),
              "Valor": brl(n.get("valor")), "Status": n.get("status")} for n in lista],
            use_container_width=True, hide_index=True,
        )

        st.divider()
        rotulos = {f"{n['tipo']} nº {n.get('numero')} · {n.get('cliente')} · {brl(n.get('valor'))} "
                   f"({n.get('data')})": n for n in lista}
        escolha = st.selectbox("Selecionar nota para editar", ["—"] + list(rotulos.keys()))
        if escolha != "—":
            alvo = rotulos[escolha]
            b1, b2 = st.columns(2)
            if alvo.get("status") == "autorizada" and b1.button("Marcar como cancelada"):
                for n in dados["notas"]:
                    if n is alvo:
                        n["status"] = "cancelada"
                salvar()
                st.rerun()
            if b2.button("Excluir definitivamente", type="secondary"):
                dados["notas"] = [n for n in dados["notas"] if n is not alvo]
                salvar()
                st.rerun()


# ============================================================ HISTÓRICO

with aba_hist:
    st.write("Informe a receita bruta **real** dos meses anteriores (do seu PGDAS-D) para que o "
             "RBT12 fique correto ao começar a usar o app no meio do caminho. Meses com notas usam "
             "o valor das notas automaticamente.")

    inicio = st.text_input("Início de atividade (AAAA-MM, opcional)", dados.get("inicio_atividade", ""),
                           help="Meses anteriores contam como zero; os 12 primeiros usam a regra proporcional.")

    receita_notas = {}
    for n in dados["notas"]:
        if n.get("status") == "autorizada" and (n.get("direcao") or "saida") == "saida":
            k = mes_chave(n.get("data"))
            receita_notas[k] = receita_notas.get(k, 0.0) + n.get("valor", 0.0)

    base = st.session_state.mes_ref
    hoje = date.today()
    chave_hoje = f"{hoje.year}-{hoje.month:02d}"
    if base > chave_hoje:
        base = chave_hoje
    meses = [deslocar_mes(base, -i) for i in range(12, 0, -1)]

    novas_aberturas = dict(dados.get("aberturas", {}))
    with st.form("form_hist"):
        for k in meses:
            col1, col2 = st.columns([1, 2])
            col1.write(rotulo_mes(k))
            if k in receita_notas:
                col2.write(f"{brl(receita_notas[k])} · das notas")
            elif inicio and k < inicio:
                col2.write("— antes da abertura")
            else:
                val = col2.number_input(f"valor_{k}", min_value=0.0, step=100.0,
                                        value=float(dados.get("aberturas", {}).get(k, 0.0)),
                                        label_visibility="collapsed")
                if val > 0:
                    novas_aberturas[k] = val
                elif k in novas_aberturas:
                    del novas_aberturas[k]
        if st.form_submit_button("Salvar histórico", type="primary"):
            dados["aberturas"] = novas_aberturas
            dados["inicio_atividade"] = inicio.strip()
            salvar()
            st.success("Histórico salvo.")


# ============================================================ MANUAL

with aba_manual:
    st.write("Registro manual para casos avulsos — o normal é importar via XML.")
    with st.form("form_manual"):
        c1, c2, c3 = st.columns(3)
        tipo = c1.selectbox("Tipo", ["NFS-e", "NF-e"])
        direcao = c2.selectbox("Direção", ["Emitida (receita)", "Recebida (entrada)"])
        data_nota = c3.date_input("Data de emissão", value=date.today())
        c4, c5, c6 = st.columns(3)
        numero = c4.text_input("Número")
        serie = c5.text_input("Série (opcional)")
        valor = c6.number_input("Valor total", min_value=0.0, step=100.0)
        cliente = st.text_input("Contraparte (cliente ou fornecedor)")
        descricao = st.text_input("Descrição (opcional)")
        if st.form_submit_button("Salvar nota", type="primary"):
            if not numero.strip() or not cliente.strip() or valor <= 0:
                st.error("Informe número, contraparte e um valor maior que zero.")
            else:
                dados["notas"].append({
                    "tipo": tipo,
                    "direcao": "saida" if direcao.startswith("Emitida") else "entrada",
                    "numero": numero.strip(), "serie": serie.strip(),
                    "data": data_nota.isoformat(), "cliente": cliente.strip(),
                    "doc": "", "valor": float(valor), "descricao": descricao.strip(),
                    "status": "autorizada", "chave": "", "origem": "manual",
                })
                salvar()
                st.success("Nota adicionada.")


# ============================================================ EMPRESA

with aba_empresa:
    with st.form("form_empresa"):
        nome = st.text_input("Nome da empresa", dados.get("empresa", ""))
        cnpj = st.text_input("CNPJ da empresa", dados.get("cnpj", ""),
                             help="Usado para separar automaticamente notas emitidas das recebidas.")
        anexo = st.selectbox("Anexo do Simples Nacional", list(ANEXOS.keys()),
                             index=list(ANEXOS.keys()).index(dados.get("anexo", "III")),
                             format_func=lambda k: ANEXOS[k]["nome"])
        if st.form_submit_button("Salvar configurações", type="primary"):
            dados["empresa"] = nome.strip() or "Minha Empresa"
            dados["cnpj"] = cnpj.strip()
            dados["anexo"] = anexo
            salvar()
            st.success("Configurações salvas.")
    st.caption("Na dúvida sobre o anexo (ou sobre o Fator R, que move serviços entre os Anexos III e V), "
               "confirme com seu contador.")

st.divider()
st.caption("Valores de DAS são estimativas (LC 123/2006); a apuração oficial é no PGDAS-D. "
           "Só notas emitidas entram na receita. Este app não substitui orientação contábil.")
