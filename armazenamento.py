"""Persistência local em arquivo JSON (equivalente ao localStorage da versão web)."""

from __future__ import annotations

import json
import os

ARQUIVO = os.environ.get("CONTROLE_NOTAS_ARQUIVO", "controle_dados.json")

PADRAO = {
    "empresa": "Minha Empresa LTDA",
    "cnpj": "",
    "anexo": "III",
    "aberturas": {},
    "inicio_atividade": "",
    "notas": [],
    "ncms": {},
}


def carregar() -> dict:
    if not os.path.exists(ARQUIVO):
        return dict(PADRAO)
    try:
        with open(ARQUIVO, "r", encoding="utf-8") as f:
            dados = json.load(f)
        base = dict(PADRAO)
        base.update({k: dados[k] for k in PADRAO if k in dados})
        return base
    except (json.JSONDecodeError, OSError):
        return dict(PADRAO)


def salvar(dados: dict) -> None:
    limpo = {k: dados.get(k, PADRAO[k]) for k in PADRAO}
    with open(ARQUIVO, "w", encoding="utf-8") as f:
        json.dump(limpo, f, ensure_ascii=False, indent=2)


def dedup_por_chave(existentes: list, novas: list):
    """Adiciona `novas` ignorando chaves já presentes. Retorna (lista, adicionadas, duplicadas)."""
    chaves = {n.get("chave") for n in existentes if n.get("chave")}
    unicas, dup = [], 0
    for n in novas:
        ch = n.get("chave")
        if ch and ch in chaves:
            dup += 1
            continue
        if ch:
            chaves.add(ch)
        unicas.append(n)
    return existentes + unicas, len(unicas), dup
