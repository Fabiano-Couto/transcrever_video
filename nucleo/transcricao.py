# -*- coding: utf-8 -*-
"""Transcricao: aproveita a que ja existe ao lado do video ou roda o Whisper.

Formatos lidos:
- falantes (tl;dv):    "[00:00:16] Fabiano Couto Pereira:" e o texto nas linhas seguintes
- faixas HH:MM:SS:     "[00:00:16 -> 00:00:20] texto" (o que esta ferramenta grava)
- faixas MM:SS:        "[00:16 -> 00:20] texto" (saida da skill transcrever-audio)

Toda fala vira {"inicio", "fim", "falante", "texto"}; fim e falante podem ser None.
"""
import os
import re

from .tempo import hh_mm_ss

ARQUIVO_TRANSCRICAO = "00-TRANSCRICAO.txt"

_RE_FALANTE = re.compile(r"^\[(\d{1,2}):(\d{2}):(\d{2})\]\s*(.*)$")
_RE_FAIXA_H = re.compile(r"^\[(\d{1,2}):(\d{2}):(\d{2})\s*->\s*(\d{1,2}):(\d{2}):(\d{2})\]\s*(.*)$")
_RE_FAIXA_M = re.compile(r"^\[(\d+):(\d{2})\s*->\s*(\d+):(\d{2})\]\s*(.*)$")


def _ler_texto(caminho):
    for cod in ("utf-8-sig", "cp1252"):
        try:
            with open(caminho, encoding=cod) as fh:
                return fh.read()
        except UnicodeDecodeError:
            continue
    raise ValueError(f"nao consegui ler {caminho}")


def ler_transcricao(caminho):
    """Le um .txt em qualquer dos formatos aceitos. Devolve (falas, fonte_do_cabecalho)."""
    falas = []
    fonte = None
    atual = None
    for linha in _ler_texto(caminho).splitlines():
        crua = linha.strip()
        if fonte is None and crua.lower().startswith("fonte:"):
            fonte = crua.split(":", 1)[1].strip()
            continue
        m = _RE_FAIXA_H.match(crua)
        if m:
            g = [int(x) for x in m.groups()[:6]]
            falas.append({"inicio": g[0] * 3600 + g[1] * 60 + g[2], "fim": g[3] * 3600 + g[4] * 60 + g[5],
                          "falante": None, "texto": m.group(7).strip()})
            atual = None
            continue
        m = _RE_FAIXA_M.match(crua)
        if m:
            g = [int(x) for x in m.groups()[:4]]
            falas.append({"inicio": g[0] * 60 + g[1], "fim": g[2] * 60 + g[3],
                          "falante": None, "texto": m.group(5).strip()})
            atual = None
            continue
        m = _RE_FALANTE.match(crua)
        if m:
            h, mi, s, resto = int(m.group(1)), int(m.group(2)), int(m.group(3)), m.group(4).strip()
            falante, texto = (resto[:-1].strip(), "") if resto.endswith(":") else (None, resto)
            atual = {"inicio": h * 3600 + mi * 60 + s, "fim": None, "falante": falante, "texto": texto}
            falas.append(atual)
            continue
        if atual is not None and crua:
            atual["texto"] = (atual["texto"] + " " + crua).strip()
        elif not crua:
            atual = None

    falas.sort(key=lambda f: f["inicio"])
    for i, fala in enumerate(falas):
        if fala["fim"] is None and i + 1 < len(falas):
            fala["fim"] = falas[i + 1]["inicio"]
    return falas, fonte


def localizar_vizinha(caminho_video):
    """Procura, na pasta do video, um .txt que comece com o nome dele e tenha falas."""
    pasta = os.path.dirname(os.path.abspath(caminho_video))
    raiz = os.path.splitext(os.path.basename(caminho_video))[0].lower()
    for nome in sorted(os.listdir(pasta)):
        if not nome.lower().endswith(".txt") or not nome.lower().startswith(raiz):
            continue
        caminho = os.path.join(pasta, nome)
        try:
            falas, _ = ler_transcricao(caminho)
        except (OSError, ValueError):
            continue
        if len(falas) >= 3:
            return caminho
    return None


def transcrever_whisper(caminho_video, modelo="large-v3-turbo", idioma="pt", progresso=None):
    """Mesmos ajustes da skill transcrever-audio, com tempo em HH:MM:SS."""
    avisar = progresso or (lambda _m: None)
    from faster_whisper import WhisperModel

    avisar(f"[transcricao] carregando modelo {modelo} ...")
    whisper = WhisperModel(modelo, device="cpu", compute_type="int8")
    segmentos, info = whisper.transcribe(
        caminho_video,
        language=idioma,
        vad_filter=True,
        beam_size=5,
        condition_on_previous_text=False,
    )
    avisar(f"[transcricao] audio de {info.duration:.0f}s, transcrevendo ...")
    falas = []
    marco = 0.1
    for seg in segmentos:
        falas.append({"inicio": int(seg.start), "fim": int(round(seg.end)), "falante": None,
                      "texto": seg.text.strip()})
        if info.duration and seg.end / info.duration >= marco:
            avisar(f"[transcricao] {int(seg.end / info.duration * 100)}%")
            marco = (int(seg.end / info.duration * 10) + 1) / 10
    return falas


def obter_transcricao(caminho_video, pasta_saida, modo="auto", modelo="large-v3-turbo", idioma="pt",
                      refazer=False, progresso=None):
    """Decide de onde vem a transcricao.

    modo: "auto" (arquivo vizinho > rodada anterior > Whisper), "whisper", "nenhuma"
    ou o caminho de um .txt. Devolve {"fonte", "arquivo", "falas"}.
    """
    avisar = progresso or (lambda _m: None)
    anterior = os.path.join(pasta_saida, ARQUIVO_TRANSCRICAO)

    if modo == "nenhuma":
        return {"fonte": "nenhuma", "arquivo": None, "falas": []}

    if modo not in ("auto", "whisper"):
        falas, _ = ler_transcricao(modo)
        return {"fonte": f"arquivo {os.path.basename(modo)}", "arquivo": os.path.abspath(modo), "falas": falas}

    if modo == "auto":
        vizinha = localizar_vizinha(caminho_video)
        if vizinha:
            avisar(f"[transcricao] usando a que ja existe: {os.path.basename(vizinha)}")
            falas, _ = ler_transcricao(vizinha)
            return {"fonte": f"arquivo {os.path.basename(vizinha)}", "arquivo": vizinha, "falas": falas}

    if os.path.isfile(anterior) and not refazer:
        falas, fonte = ler_transcricao(anterior)
        if falas and (modo == "auto" or (fonte or "").lower().startswith("whisper")):
            avisar(f"[transcricao] reaproveitando {ARQUIVO_TRANSCRICAO} da rodada anterior (--refazer para refazer)")
            return {"fonte": fonte or "rodada anterior", "arquivo": anterior, "falas": falas}

    falas = transcrever_whisper(caminho_video, modelo, idioma, progresso)
    return {"fonte": f"Whisper {modelo} ({idioma})", "arquivo": None, "falas": falas}


def gravar_transcricao(caminho, falas, fonte, titulo):
    """Grava a transcricao normalizada: com falante no formato tl;dv, sem falante em faixas."""
    linhas = [f"TRANSCRICAO - {titulo}", f"Fonte: {fonte}", "=" * 60, ""]
    for fala in falas:
        if fala["falante"]:
            linhas += [f"[{hh_mm_ss(fala['inicio'])}] {fala['falante']}:", fala["texto"], ""]
        else:
            fim = hh_mm_ss(fala["fim"]) if fala["fim"] is not None else hh_mm_ss(fala["inicio"])
            linhas.append(f"[{hh_mm_ss(fala['inicio'])} -> {fim}] {fala['texto']}")
    with open(caminho, "w", encoding="utf-8") as fh:
        fh.write("\n".join(linhas).rstrip() + "\n")
