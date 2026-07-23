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
from estudo_preco import estudo_completo
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

aba_painel, aba_importar, aba_notas, aba_ncm, aba_estudo, aba_hist, aba_manual, aba_empresa = st.tabs(
    ["Painel", "Importar XML", f"Notas ({len(dados['notas'])})", "Tabela de NCM", "Estudo de Preço",
     "Histórico", "Manual", "Empresa"]
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
                         dados["aberturas"], dados["inicio_atividade"], dados["ncms"])

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

            if c["receita_mes_st"] > 0:
                st.success(
                    f"Segregação automática de ICMS-ST: {brl(c['receita_mes_st'])} da receita do mês "
                    f"vieram de NCMs marcados como substituída — {brl(c['economia_icms_st'])} de ICMS "
                    f"já retido antes foram excluídos do DAS acima (percentual de ICMS na "
                    f"{pct(c['percentual_icms_faixa'])} desta faixa)."
                )

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
                             dados["aberturas"], dados["inicio_atividade"], dados["ncms"])

            if a["rbt12_incompleto"]:
                st.warning("Alguns meses com receita têm RBT12 incompleto — o DAS anual está subestimado. "
                           "Complete na aba **Histórico**.")

            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Faturamento do ano", brl(a["saidas_ano"]), help=f"{a['qtd_saidas']} nota(s) emitida(s)")
            m2.metric("Entradas do ano", brl(a["entradas_ano"]), help=f"{a['qtd_entradas']} nota(s) recebida(s)")
            m3.metric("Resultado do ano", brl(a["resultado_ano"]), help="saídas − entradas")
            m4.metric("DAS estimado do ano", brl(a["das_ano"]), help="soma das 12 competências")

            if a["receita_st_ano"] > 0:
                st.success(
                    f"Segregação automática de ICMS-ST no ano: {brl(a['receita_st_ano'])} de receita "
                    f"com NCM marcado como substituída — {brl(a['economia_icms_st_ano'])} de ICMS já "
                    "retido antes foram excluídos do DAS somado acima."
                )

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

            multiplos = sum(1 for n in previa if n.get("itens_multiplos"))
            if multiplos:
                st.caption(
                    f"⚠ {multiplos} nota(s) têm mais de um item — o NCM não foi preenchido "
                    "automaticamente para elas (para não atribuir um NCM errado). Preencha manualmente "
                    "na coluna NCM se quiser aplicar a segregação de ICMS-ST."
                )

            df_previa = pd.DataFrame([{
                "Tipo": n["tipo"], "Número": n["numero"],
                "Direção": "emitida" if n["direcao"] == "saida" else "recebida",
                "Cliente/Fornecedor": n["cliente"], "Data": n["data"], "Valor (R$)": n["valor"],
                "NCM": n.get("ncm", ""),
            } for n in previa])

            df_editado = st.data_editor(
                df_previa, use_container_width=True, hide_index=True,
                disabled=["Tipo", "Número", "Direção", "Cliente/Fornecedor", "Data", "Valor (R$)"],
                column_config={"NCM": st.column_config.TextColumn(
                    help="Preencha para vincular esta nota a um perfil cadastrado na Tabela de NCM "
                         "(ICMS-ST) e permitir a segregação automática no painel.")},
                key="editor_previa_xml",
            )

            if st.button(f"Adicionar {len(previa)} nota(s)", type="primary"):
                for n, ncm_editado in zip(previa, df_editado["NCM"]):
                    n["ncm"] = (ncm_editado or "").strip()
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
            novo_ncm = st.text_input("NCM vinculado a esta nota (para segregação de ICMS-ST)",
                                     value=alvo.get("ncm", ""), key=f"ncm_edit_{id(alvo)}")
            if novo_ncm.strip() != (alvo.get("ncm") or ""):
                if st.button("Salvar NCM"):
                    alvo["ncm"] = novo_ncm.strip()
                    salvar()
                    st.rerun()
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


# ============================================================ TABELA DE NCM

with aba_ncm:
    st.write(
        "Cadastre aqui cada NCM dos produtos que você vende, uma única vez, dizendo se ele está "
        "sujeito a **ICMS-ST** e qual o seu papel na operação. Depois, basta informar o NCM ao "
        "adicionar ou revisar uma nota — o painel principal passa a **segregar automaticamente** a "
        "parcela de ICMS já retida antes, excluindo-a do DAS."
    )
    st.info(
        "⚠ MVA e alíquota interna variam por NCM/CEST e são definidas por convênio ou legislação "
        "estadual — não há uma tabela pronta aqui. Preencha com base no RICMS/MG vigente, na nota do "
        "seu fornecedor ou com orientação do seu contador."
    )

    ncms = dados["ncms"]

    with st.form("form_ncm", clear_on_submit=True):
        c1, c2, c3 = st.columns([1, 2, 1])
        ncm_novo = c1.text_input("NCM", help="Só números, ex.: 84713012")
        descricao_novo = c2.text_input("Descrição do produto (opcional)")
        cest_novo = c3.text_input("CEST (opcional)")
        c4, c5 = st.columns(2)
        sujeito_st_novo = c4.checkbox("Sujeito a ICMS-ST?")
        papel_novo = c5.selectbox("Papel", ["substituido", "substituto"],
                                  format_func=lambda p: "Substituído (ST já retida)" if p == "substituido"
                                  else "Substituto (recolho o ST)")
        c6, c7, c8 = st.columns(3)
        aliq_interna_novo = c6.number_input("Alíquota interna (%)", min_value=0.0, max_value=100.0,
                                            value=18.0, step=0.5)
        mva_novo = c7.number_input("MVA (%)", min_value=0.0, max_value=200.0, step=1.0)
        aliq_propria_novo = c8.number_input("Alíquota própria (%)", min_value=0.0, max_value=100.0, step=0.5)

        if st.form_submit_button("Cadastrar/atualizar NCM", type="primary"):
            ncm_limpo = so_digitos(ncm_novo) or ncm_novo.strip()
            if not ncm_limpo:
                st.error("Informe o NCM.")
            else:
                ncms[ncm_limpo] = {
                    "descricao": descricao_novo.strip(), "cest": cest_novo.strip(),
                    "sujeito_st": sujeito_st_novo, "papel": papel_novo,
                    "aliq_interna": aliq_interna_novo / 100, "mva": mva_novo / 100,
                    "aliq_propria": aliq_propria_novo / 100,
                }
                salvar()
                st.success(f"NCM {ncm_limpo} cadastrado.")

    if ncms:
        st.subheader("NCMs cadastrados")
        linhas_ncm = [{
            "NCM": k, "Descrição": v.get("descricao", ""), "CEST": v.get("cest", ""),
            "ST?": "Sim" if v.get("sujeito_st") else "Não",
            "Papel": "Substituído" if v.get("papel") == "substituido" else "Substituto",
            "Alíq. interna": pct(v.get("aliq_interna", 0)), "MVA": pct(v.get("mva", 0)),
        } for k, v in ncms.items()]
        st.dataframe(linhas_ncm, use_container_width=True, hide_index=True)

        ncm_remover = st.selectbox("Remover um NCM cadastrado", ["—"] + list(ncms.keys()))
        if ncm_remover != "—" and st.button("Remover NCM selecionado", type="secondary"):
            del ncms[ncm_remover]
            salvar()
            st.rerun()
    else:
        st.caption("Nenhum NCM cadastrado ainda.")


# ============================================================ ESTUDO DE PREÇO

with aba_estudo:
    st.write(
        "Calcule os encargos que incidem sobre um valor de venda: o **DAS** (Simples "
        "Nacional, na alíquota efetiva vigente), o **ICMS-ST** quando aplicável, o "
        "**DIFAL** em vendas interestaduais a consumidor final, e outros encargos que "
        "você quiser somar (frete, taxa de cartão, comissão etc.)."
    )
    st.info(
        "⚠ **MVA e alíquotas de ICMS-ST são definidas por convênio/protocolo estadual e "
        "variam por NCM/CEST do produto.** Este app não tem uma tabela por produto — você "
        "informa os percentuais aplicáveis (consulte o RICMS/MG vigente ou seu contador). "
        "O DAS calculado aqui é uma estimativa, não uma apuração oficial."
    )

    # RBT12 vigente, reaproveitando o mesmo cálculo do painel (mês de referência atual)
    calc_ref = calcular(dados["notas"], dados["anexo"], st.session_state.mes_ref,
                        dados["aberturas"], dados["inicio_atividade"], dados["ncms"])
    rbt12_atual = calc_ref["rbt12"]
    if calc_ref["rbt12_incompleto"]:
        st.warning(f"RBT12 incompleto para {rotulo_mes(st.session_state.mes_ref)} — o DAS "
                   "estimado abaixo pode estar subestimado. Complete o Histórico para precisão.")
    st.caption(f"RBT12 usado no cálculo: {brl(rbt12_atual)} (referente a {rotulo_mes(st.session_state.mes_ref)})")

    # origem do valor: nota existente ou digitado
    origem = st.radio("Valor de partida", ["Digitar um valor", "Usar uma nota existente"], horizontal=True)
    valor_base = 0.0
    if origem == "Usar uma nota existente":
        emitidas = [n for n in dados["notas"] if (n.get("direcao") or "saida") == "saida"]
        if not emitidas:
            st.info("Nenhuma nota emitida cadastrada ainda — digite um valor manualmente.")
        else:
            rotulos_n = {f"{n['tipo']} nº {n.get('numero')} · {n.get('cliente')} · "
                        f"{brl(n.get('valor'))} ({n.get('data')})": n for n in emitidas}
            escolha_n = st.selectbox("Nota", list(rotulos_n.keys()))
            valor_base = rotulos_n[escolha_n]["valor"]
    else:
        valor_base = st.number_input("Valor da operação (R$)", min_value=0.0, step=100.0)

    custo = st.number_input("Custo de aquisição/produção (opcional, para calcular a margem)",
                            min_value=0.0, step=50.0)

    st.subheader("Substituição tributária (ICMS-ST)")
    tem_st = st.checkbox("Este produto está sujeito a ICMS-ST?")
    papel_st, aliq_dest_st, mva, icms_proprio_aliq, frete, seguro, outras_desp = (
        "substituto", 0.0, 0.0, 0.0, 0.0, 0.0, 0.0
    )
    if tem_st:
        papel_st_label = st.radio(
            "Seu papel nesta operação",
            ["Sou o substituto tributário (fabricante/importador)",
             "Sou substituído — recebi a mercadoria com ICMS-ST já retido"],
        )
        papel_st = "substituto" if papel_st_label.startswith("Sou o substituto") else "substituido"

        if papel_st == "substituto":
            c1, c2, c3 = st.columns(3)
            aliq_dest_pct = c1.number_input("Alíquota interna no destino (%)", min_value=0.0,
                                            max_value=100.0, value=18.0, step=0.5,
                                            help="Regra geral em MG: 18% (RICMS/MG art. 42, I, e). "
                                                 "Pode ser diferente por produto — confira a tabela.")
            mva_pct = c2.number_input(
                "MVA (%)", min_value=0.0, max_value=200.0, step=1.0,
                help="Margem de Valor Agregado do produto, definida por convênio/protocolo/legislação "
                     "estadual. Em operação interestadual, optante pelo Simples deve usar a 'MVA ST "
                     "original', não a 'MVA ajustada' (Convênio ICMS 35/2011).",
            )
            icms_proprio_pct = c3.number_input(
                "Alíquota do ICMS próprio nesta operação (%)", min_value=0.0, max_value=100.0,
                step=0.5, help="Interestadual (ex.: 12% ou 7%) ou interna, conforme o caso.",
            )
            c4, c5 = st.columns(2)
            frete = c4.number_input("Frete (R$, se cobrado do destinatário)", min_value=0.0, step=10.0)
            seguro = c5.number_input("Seguro (R$)", min_value=0.0, step=10.0)
            outras_desp = st.number_input("Outras despesas acessórias (R$)", min_value=0.0, step=10.0)
            aliq_dest_st, mva, icms_proprio_aliq = aliq_dest_pct / 100, mva_pct / 100, icms_proprio_pct / 100
        else:
            st.caption(
                "Como substituída, você não recolhe ICMS de novo sobre esta revenda — o imposto já "
                "foi retido antes. No PGDAS-D essa receita deve ser destacada como sujeita à "
                "substituição tributária, para não compor a parcela de ICMS do DAS. Confira com seu "
                "contador se a segregação está sendo feita corretamente."
            )

    st.subheader("Diferencial de alíquota (DIFAL)")
    tem_difal = st.checkbox("Venda interestadual para consumidor final não contribuinte?",
                            help="EC 87/2015. Também se aplica a compras interestaduais para uso e "
                                 "consumo próprio (ativo imobilizado, material de uso).")
    aliq_interestadual, fcp_destino = 0.0, 0.0
    if tem_difal:
        d1, d2, d3 = st.columns(3)
        aliq_dest_difal_pct = d1.number_input("Alíquota interna no destino (%) ", min_value=0.0,
                                              max_value=100.0, value=18.0, step=0.5, key="difal_dest")
        aliq_inter_pct = d2.number_input("Alíquota interestadual (%)", min_value=0.0, max_value=100.0,
                                         value=12.0, step=0.5,
                                         help="Regra geral: 12% (Sul/Sudeste exceto ES ↔ demais regiões) "
                                              "ou 7% / 4% (importados), conforme a origem.")
        fcp_pct = d3.number_input("FCP do destino (%, se houver)", min_value=0.0, max_value=100.0,
                                  step=0.5, help="Fundo de combate à pobreza do estado de destino.")
        if not tem_st:
            aliq_dest_st = aliq_dest_difal_pct / 100
        aliq_interestadual, fcp_destino = aliq_inter_pct / 100, fcp_pct / 100

    st.subheader("Outros encargos (opcional)")
    st.caption("Ex.: taxa de maquininha/cartão, comissão de vendas, frete não incluso acima.")
    n_extras = st.number_input("Quantos encargos extras?", min_value=0, max_value=6, step=1)
    encargos_extras = []
    for i in range(int(n_extras)):
        ce1, ce2 = st.columns([2, 1])
        nome_e = ce1.text_input(f"Nome do encargo {i + 1}", key=f"extra_nome_{i}")
        valor_e = ce2.number_input(f"Valor (R$) {i + 1}", min_value=0.0, step=10.0, key=f"extra_valor_{i}")
        if nome_e:
            encargos_extras.append({"nome": nome_e, "valor": valor_e})

    if st.button("Calcular estudo de preço", type="primary"):
        if valor_base <= 0:
            st.error("Informe um valor de operação maior que zero.")
        else:
            e = estudo_completo(
                valor_base, rbt12_atual, dados["anexo"], custo=custo,
                tem_icms_st=tem_st, papel_st=papel_st,
                aliq_interna_destino=aliq_dest_st, mva=mva, icms_proprio_aliq=icms_proprio_aliq,
                frete=frete, seguro=seguro, outras_despesas_st=outras_desp,
                tem_difal=tem_difal, aliq_interestadual=aliq_interestadual, fcp_destino=fcp_destino,
                encargos_extras=encargos_extras,
            )

            st.divider()
            st.subheader("Resultado")
            linhas = [{"Encargo": "DAS (Simples Nacional)", "Valor": brl(e["das"]["valor"]),
                      "Detalhe": f"alíquota efetiva {pct(e['das']['aliq_efetiva'])}"}]
            if e["icms_st"]:
                linhas.append({"Encargo": "ICMS-ST", "Valor": brl(e["icms_st"]["icms_st"]),
                              "Detalhe": f"base {brl(e['icms_st']['base_st'])} · ICMS próprio {brl(e['icms_st']['icms_proprio'])}"})
            if e["aviso_substituido"]:
                st.caption("ICMS-ST não recalculado — você é a substituída nesta operação (ver nota acima).")
            if e["difal"]:
                linhas.append({"Encargo": "DIFAL + FCP", "Valor": brl(e["difal"]["total"]),
                              "Detalhe": f"DIFAL {brl(e['difal']['difal'])} · FCP {brl(e['difal']['fcp'])}"})
            for extra in e["encargos_extras"]:
                linhas.append({"Encargo": extra["nome"], "Valor": brl(extra["valor"]), "Detalhe": ""})

            st.dataframe(linhas, use_container_width=True, hide_index=True)

            m1, m2 = st.columns(2)
            m1.metric("Total de encargos", brl(e["total_encargos"]))
            m2.metric("Valor líquido após encargos", brl(e["liquido_apos_encargos"]))

            if "margem_liquida" in e:
                m3, m4 = st.columns(2)
                m3.metric("Margem líquida (após custo)", brl(e["margem_liquida"]))
                m4.metric("Margem líquida (%)", pct(e["margem_pct"]))
                if e["margem_liquida"] < 0:
                    st.error("Margem negativa: o preço não cobre custo + encargos calculados.")

            st.caption(
                "Estimativa para apoiar a formação de preço. Não substitui a apuração oficial no "
                "PGDAS-D nem orientação do seu contador, especialmente quanto a MVA, CEST e "
                "enquadramento do produto na substituição tributária."
            )


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
        ncm = st.text_input("NCM (opcional, para segregação de ICMS-ST)",
                            help="Se este NCM estiver cadastrado na aba Tabela de NCM como sujeito a "
                                 "ST e substituído, o painel excluirá a parcela de ICMS do DAS.")
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
                    "ncm": so_digitos(ncm) or ncm.strip(),
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
