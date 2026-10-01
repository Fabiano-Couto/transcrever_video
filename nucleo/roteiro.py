# -*- coding: utf-8 -*-
"""Junta falas e quadros: 00-ROTEIRO.md (para o agente ler) e 00-INDICE.json (para maquina)."""
import json

from .tempo import hh_mm_ss

ARQUIVO_ROTEIRO = "00-ROTEIRO.md"
ARQUIVO_INDICE = "00-INDICE.json"

_TIPOS = {
    "inicio": "inicio do video",
    "tela": "TELA NOVA",
    "parcial": "mudanca parcial",
    "mouse": "mouse/detalhe",
}


def _regiao(r):
    return f"x{r[0]}-{r[2]} y{r[1]}-{r[3]}" if r else ""


def _linha_quadro(q):
    rotulo = _TIPOS.get(q["tipo"], q["tipo"])
    if q["tipo"] in ("parcial", "mouse") and q.get("regiao"):
        rotulo += f" em {_regiao(q['regiao'])}"
    elif q["tipo"] == "tela":
        rotulo += f" ({round(q['fracao'] * 100)}% da area)"
    return f"- {hh_mm_ss(q['tempo_s'])} {rotulo} -> {q['arquivo']}"


def _cabecalho_fala(fala):
    if fala["falante"]:
        return f"### [{hh_mm_ss(fala['inicio'])}] {fala['falante']}"
    fim = f" -> {hh_mm_ss(fala['fim'])}" if fala["fim"] is not None else ""
    return f"### [{hh_mm_ss(fala['inicio'])}{fim}]"


def montar_roteiro(titulo, video, transcricao, extracao, parametros):
    info = extracao["info"]
    quadros = sorted(extracao["quadros"], key=lambda q: q["tempo_s"])
    falas = transcricao["falas"]
    ext = parametros["formato"]

    linhas = [
        f"# Roteiro do video {titulo}",
        "",
        f"- Video: {video} ({hh_mm_ss(info['duracao_s'] or 0)}, {info['largura']}x{info['altura']})",
        f"- Transcricao: {transcricao['fonte']}",
        f"- Quadros: {len(quadros)} salvos de {extracao['instantes']} instantes analisados "
        f"(a cada {parametros['intervalo_s']}s). So entra quadro quando a tela muda, "
        f"inclusive movimento de mouse e selecao.",
        f"- Nome dos quadros: {titulo}_HHMMSS.{ext}, nesta pasta.",
    ]
    if extracao["regioes_ignoradas"]:
        linhas.append("- Regioes ignoradas na comparacao (participantes da chamada, que mudam o tempo todo):")
        for trecho in extracao["regioes_ignoradas"]:
            caixas = "; ".join(_regiao(c["regiao"]) + ("" if c["inteira"] else " (so os pontos que piscam)")
                               for c in trecho["caixas"])
            linhas.append(f"  - {hh_mm_ss(trecho['de_s'])} a {hh_mm_ss(trecho['ate_s'])}: {caixas}")
    linhas += [
        "- Como ler: em cada fala, \"tela vigente\" e o que estava na tela quando a fala comecou; "
        "as linhas seguintes sao as mudancas durante a fala, com a regiao da imagem onde mudou "
        "(em pixels do video). Mouse/detalhe = ponteiro, selecao ou digitacao.",
        "- Instante exato que nao esta aqui: rodar o script com --quadro HH:MM:SS.",
        "",
        "## Linha do tempo",
        "",
    ]

    if not falas:
        linhas += [_linha_quadro(q) for q in quadros]
        return "\n".join(linhas) + "\n"

    i = 0
    antes = []
    while i < len(quadros) and quadros[i]["tempo_s"] < falas[0]["inicio"]:
        antes.append(quadros[i])
        i += 1
    if antes:
        linhas += ["### Antes da primeira fala"] + [_linha_quadro(q) for q in antes] + [""]

    vigente = antes[-1] if antes else None
    for n, fala in enumerate(falas):
        limite = falas[n + 1]["inicio"] if n + 1 < len(falas) else float("inf")
        linhas.append(_cabecalho_fala(fala))
        linhas.append(fala["texto"])
        durante = []
        while i < len(quadros) and quadros[i]["tempo_s"] < limite:
            durante.append(quadros[i])
            i += 1
        if vigente and not (durante and durante[0]["tempo_s"] == fala["inicio"]):
            linhas.append(f"- tela vigente: {vigente['arquivo']}")
        linhas += [_linha_quadro(q) for q in durante]
        if durante:
            vigente = durante[-1]
        linhas.append("")
    return "\n".join(linhas).rstrip() + "\n"


def montar_indice(titulo, video, transcricao, extracao, parametros):
    return {
        "versao": 1,
        "titulo": titulo,
        "video": dict(extracao["info"], arquivo=video),
        "parametros": parametros,
        "regioes_ignoradas": extracao["regioes_ignoradas"],
        "transcricao": {"fonte": transcricao["fonte"], "arquivo": transcricao["arquivo"]},
        "instantes_analisados": extracao["instantes"],
        "quadros": extracao["quadros"],
        "falas": transcricao["falas"],
    }


def gravar(caminho_roteiro, caminho_indice, roteiro, indice):
    with open(caminho_roteiro, "w", encoding="utf-8") as fh:
        fh.write(roteiro)
    with open(caminho_indice, "w", encoding="utf-8") as fh:
        json.dump(indice, fh, ensure_ascii=False, indent=1)
