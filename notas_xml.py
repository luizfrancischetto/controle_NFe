"""
Leitura de XML de nota fiscal → dicionário de nota.

Suporta NF-e/NFC-e (infNFe), NFS-e nacional (infNFSe) e NFS-e padrão ABRASF
(InfNfse). Ignora namespaces comparando pelo nome local da tag, e classifica
automaticamente entre emitida e recebida pelo CNPJ da empresa.

O valor é lido com ponto decimal (parse_num), corrigindo o formato do XML.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET

from simples import parse_num, classificar, so_digitos


def _local(tag: str) -> str:
    return tag.split("}")[-1]


def _find(node, tag):
    if node is None:
        return None
    for el in node.iter():
        if _local(el.tag) == tag:
            return el
    return None


def _text(node, tag) -> str:
    el = _find(node, tag)
    return (el.text or "").strip() if el is not None else ""


def _fmt_cnpj(v: str) -> str:
    d = so_digitos(v)[:14]
    if len(d) == 14:
        return f"{d[:2]}.{d[2:5]}.{d[5:8]}/{d[8:12]}-{d[12:]}"
    return v


def parsear_xml(conteudo: str, nome_arquivo: str, cnpj_empresa: str):
    """Retorna (nota_dict, None) em sucesso ou (None, motivo) em erro."""
    try:
        root = ET.fromstring(conteudo)
    except ET.ParseError:
        return None, f"{nome_arquivo}: XML inválido"

    if _find(root, "infNFe") is not None:
        return _parsear_nfe(_find(root, "infNFe"), cnpj_empresa), None
    if _find(root, "infNFSe") is not None:
        return _parsear_nfse_nacional(root, cnpj_empresa), None
    if _find(root, "InfNfse") is not None:
        return _parsear_nfse_abrasf(_find(root, "InfNfse"), cnpj_empresa), None

    return None, f"{nome_arquivo}: não parece ser NF-e nem NFS-e"


def _parsear_nfe(inf, cnpj_empresa):
    chave = (inf.get("Id") or "").replace("NFe", "")
    ide = _find(inf, "ide")
    emit = _find(inf, "emit")
    dest = _find(inf, "dest")
    total = _find(inf, "total")

    dh = _text(ide, "dhEmi") or _text(ide, "dEmi")
    cnpj_emit = _text(emit, "CNPJ") or _text(emit, "CPF")
    cnpj_dest = _text(dest, "CNPJ") or _text(dest, "CPF")
    direcao = classificar(cnpj_emit, cnpj_dest, cnpj_empresa)
    contraparte = _text(dest, "xNome") if direcao == "saida" else _text(emit, "xNome")

    return {
        "tipo": "NF-e",
        "numero": _text(ide, "nNF"),
        "serie": _text(ide, "serie"),
        "data": dh[:10] if dh else "",
        "chave": chave,
        "cliente": contraparte or "—",
        "doc": cnpj_dest if direcao == "saida" else cnpj_emit,
        "valor": parse_num(_text(total, "vNF")),
        "direcao": direcao,
        "descricao": "",
        "status": "autorizada",
        "origem": "xml",
    }


def _parsear_nfse_nacional(root, cnpj_empresa):
    inf = _find(root, "infNFSe")
    dh = _text(inf, "dhProc") or _text(inf, "dhEmi")
    emit = _find(inf, "emit")
    cnpj_emit = _text(emit, "CNPJ") or _text(emit, "CPF")
    toma = _find(root, "toma") or _find(root, "infDPS")
    cnpj_dest = _text(toma, "CNPJ") or _text(toma, "CPF")
    direcao = classificar(cnpj_emit, cnpj_dest, cnpj_empresa)
    contraparte = _text(toma, "xNome") if direcao == "saida" else _text(emit, "xNome")
    numero = _text(inf, "nNFSe")

    return {
        "tipo": "NFS-e",
        "numero": numero,
        "serie": "",
        "data": dh[:10] if dh else "",
        "chave": (inf.get("Id") or numero),
        "cliente": contraparte or "—",
        "doc": cnpj_dest if direcao == "saida" else cnpj_emit,
        "valor": parse_num(_text(inf, "vLiq") or _text(inf, "vServ") or _text(inf, "vNF")),
        "direcao": direcao,
        "descricao": "",
        "status": "autorizada",
        "origem": "xml",
    }


def _parsear_nfse_abrasf(inf, cnpj_empresa):
    dh = _text(inf, "DataEmissao")
    prest = _find(inf, "PrestadorServico") or _find(inf, "Prestador")
    toma = _find(inf, "TomadorServico") or _find(inf, "Tomador")
    cnpj_emit = _text(prest, "Cnpj") or _text(prest, "CpfCnpj")
    cnpj_dest = _text(toma, "Cnpj") or _text(toma, "CpfCnpj")
    direcao = classificar(cnpj_emit, cnpj_dest, cnpj_empresa)
    contraparte = _text(toma, "RazaoSocial") if direcao == "saida" else _text(prest, "RazaoSocial")

    return {
        "tipo": "NFS-e",
        "numero": _text(inf, "Numero"),
        "serie": "",
        "data": dh[:10] if dh else "",
        "chave": _text(inf, "CodigoVerificacao") or _text(inf, "Numero"),
        "cliente": contraparte or "—",
        "doc": cnpj_dest if direcao == "saida" else cnpj_emit,
        "valor": parse_num(_text(inf, "ValorLiquidoNfse") or _text(inf, "ValorServicos") or _text(inf, "BaseCalculo")),
        "direcao": direcao,
        "descricao": _text(inf, "Discriminacao")[:120],
        "status": "autorizada",
        "origem": "xml",
    }
