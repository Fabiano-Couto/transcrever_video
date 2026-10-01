# -*- coding: utf-8 -*-
"""Extracao dos quadros do video, salvando so quando a tela muda.

O video e lido duas vezes (PyAV, sem precisar de ffmpeg instalado):

1. Mede com que frequencia cada ponto da tela muda de um instante para o outro.
   O que muda o tempo todo (quadradinho dos participantes, borda laranja de quem
   fala, anel animado do avatar) vira "regiao ignorada" na comparacao. A conta e
   feita por trecho de layout: quando a chamada troca de layout (ex.: comeca o
   compartilhamento), os participantes mudam de lugar e a estatistica recomeca.
2. Percorre de novo e salva o quadro quando a area util mudou mais que o limiar
   em relacao ao ultimo quadro salvo. O limiar e baixo de proposito: movimento de
   mouse e selecao de celula tem de gerar quadro, porque e assim que quem
   apresenta aponta o que esta explicando.

Calibrado numa reuniao real gravada pelo tl;dv (1280x720, 18 fps, Excel e ERP
compartilhados, dois participantes na lateral).
"""
import os
import re
from collections import deque

import av
import numpy as np

from .tempo import hhmmss

LARGURA_CMP = 640        # largura da imagem de comparacao (o quadro salvo e o original)
NIVEL = 20               # diferenca de cinza (0-255) para contar um ponto como alterado
GRADE = 8                # tamanho da celula na deteccao das regioes ruidosas
CORTE_RUIDO = 0.10       # ponto que muda em mais de 10% dos instantes e ruido
AREA_MAX_REGIAO = 0.40   # regiao ruidosa maior que isso nao e preenchida inteira
MIN_AMOSTRAS = 30        # trecho curto demais nao tem estatistica para achar ruido
CORTE_LAYOUT = 0.35      # mais que isso da tela mudando de uma vez = layout novo
FRACAO_TELA = 0.20       # a partir daqui a mudanca e "tela nova"
FRACAO_PARCIAL = 0.01    # a partir daqui e "parcial"; abaixo, mouse/detalhe

LIMIAR_PADRAO = 20       # pontos alterados (na comparacao 640 px) para salvar quadro


def _inicio(container):
    """Instante zero do arquivo. O .ts traz relogio interno (ex.: 51148s)."""
    if container.start_time is not None:
        return container.start_time / av.time_base
    return None


def _amostras(caminho, intervalo):
    """Percorre o video e entrega (segundo, quadro) a cada `intervalo` segundos."""
    with av.open(caminho) as c:
        v = c.streams.video[0]
        v.thread_type = "AUTO"
        t0 = _inicio(c)
        proximo = 0
        for f in c.decode(v):
            if f.time is None:
                continue
            if t0 is None:
                t0 = f.time
            t = max(0.0, f.time - t0)
            if t + 1e-3 < proximo:
                continue
            seg = int((t + 1e-3) // intervalo) * intervalo
            proximo = seg + intervalo
            yield seg, f


def info_video(caminho):
    with av.open(caminho) as c:
        v = c.streams.video[0]
        duracao = c.duration / av.time_base if c.duration else None
        fps = float(v.average_rate) if v.average_rate else None
        return {
            "largura": v.codec_context.width,
            "altura": v.codec_context.height,
            "fps": fps,
            "duracao_s": round(duracao, 3) if duracao else None,
        }


def _dimensoes_cmp(largura, altura):
    alt = max(GRADE, round(LARGURA_CMP * altura / largura / GRADE) * GRADE)
    return LARGURA_CMP, alt


def _cinza(quadro, dims):
    return quadro.reformat(width=dims[0], height=dims[1], format="gray").to_ndarray().astype(np.int16)


def _regioes_ruidosas(freq, amostras, dims):
    """Devolve (mascara, caixas) das regioes que mudam o tempo todo.

    Cada grupo de celulas ruidosas e trocado pelo retangulo que o contem: a borda
    do participante acende, mas o que se quer ignorar e o quadradinho inteiro
    (inclusive o avatar no meio dele). Cada caixa vem como (retangulo, inteira):
    inteira=False quando o grupo era grande demais e so os pontos foram ignorados.
    """
    larg, alt = dims
    mascara = np.zeros((alt, larg), dtype=bool)
    if freq is None or amostras < MIN_AMOSTRAS:
        return mascara, []
    quente = freq / (amostras - 1) > CORTE_RUIDO
    grade = quente.reshape(alt // GRADE, GRADE, larg // GRADE, GRADE).any(axis=(1, 3))
    gh, gw = grade.shape
    visto = np.zeros_like(grade)
    caixas = []
    for y in range(gh):
        for x in range(gw):
            if not grade[y, x] or visto[y, x]:
                continue
            fila = deque([(y, x)])
            visto[y, x] = True
            celulas = []
            while fila:
                cy, cx = fila.popleft()
                celulas.append((cy, cx))
                for dy in (-1, 0, 1):
                    for dx in (-1, 0, 1):
                        ny, nx = cy + dy, cx + dx
                        if 0 <= ny < gh and 0 <= nx < gw and grade[ny, nx] and not visto[ny, nx]:
                            visto[ny, nx] = True
                            fila.append((ny, nx))
            ys = [c[0] for c in celulas]
            xs = [c[1] for c in celulas]
            y0, y1 = max(0, min(ys) - 1), min(gh, max(ys) + 2)
            x0, x1 = max(0, min(xs) - 1), min(gw, max(xs) + 2)
            if (y1 - y0) * (x1 - x0) / (gh * gw) <= AREA_MAX_REGIAO:
                mascara[y0 * GRADE:y1 * GRADE, x0 * GRADE:x1 * GRADE] = True
                caixas.append(((x0 * GRADE, y0 * GRADE, x1 * GRADE, y1 * GRADE), True))
            else:
                # grande demais para ser participante: ignora so os pontos ruidosos
                for cy, cx in celulas:
                    mascara[cy * GRADE:(cy + 1) * GRADE, cx * GRADE:(cx + 1) * GRADE] = True
                caixas.append(((min(xs) * GRADE, min(ys) * GRADE, (max(xs) + 1) * GRADE, (max(ys) + 1) * GRADE),
                               False))
    # o avatar e um grupo a parte, mas cai dentro do quadradinho: so polui o relatorio
    dentro = lambda a, b: a != b and b[0] <= a[0] and b[1] <= a[1] and a[2] <= b[2] and a[3] <= b[3]
    caixas = [(a, i) for a, i in caixas if not any(dentro(a, b) for b, _ in caixas)]
    return mascara, caixas


def _trechos_de_layout(caminho_video, intervalo, dims):
    """Leitura 1: divide o video em trechos de layout e acha o ruido de cada um.

    Devolve [{"inicio_s", "fim_s", "mascara", "caixas"}], em ordem de tempo.
    """
    trechos = []
    atual = {"inicio_s": 0, "freq": None, "n": 0}
    ant, ultimo_seg = None, 0
    for seg, f in _amostras(caminho_video, intervalo):
        g = _cinza(f, dims)
        if ant is not None:
            d = np.abs(g - ant) > NIVEL
            if d.mean() > CORTE_LAYOUT:
                trechos.append(atual)
                atual = {"inicio_s": seg, "freq": None, "n": 0}
            else:
                atual["freq"] = d.astype(np.int32) if atual["freq"] is None else atual["freq"] + d
        atual["n"] += 1
        ant, ultimo_seg = g, seg
    trechos.append(atual)

    saida = []
    for i, t in enumerate(trechos):
        mascara, caixas = _regioes_ruidosas(t["freq"], t["n"], dims)
        fim = trechos[i + 1]["inicio_s"] if i + 1 < len(trechos) else ultimo_seg + intervalo
        saida.append({"inicio_s": t["inicio_s"], "fim_s": fim, "mascara": mascara, "caixas": caixas})
    return saida


def _para_original(caixa, dims, info):
    ex = info["largura"] / dims[0]
    ey = info["altura"] / dims[1]
    x0, y0, x1, y1 = caixa
    return [int(x0 * ex), int(y0 * ey), min(info["largura"], int(x1 * ex)), min(info["altura"], int(y1 * ey))]


def _limpar_quadros_antigos(pasta, prefixo):
    padrao = re.compile(re.escape(prefixo) + r"_\d{6}\.(jpg|png)$", re.IGNORECASE)
    for nome in os.listdir(pasta):
        if padrao.match(nome):
            os.remove(os.path.join(pasta, nome))


def _salvar(quadro, caminho, formato, qualidade):
    img = quadro.to_image()
    if formato == "png":
        img.save(caminho, "PNG")
    else:
        img.save(caminho, "JPEG", quality=qualidade)


def extrair_quadros(caminho_video, pasta_saida, prefixo, intervalo=1, limiar_px=LIMIAR_PADRAO,
                    todos=False, ignorar_ruido=True, formato="jpg", qualidade=90, progresso=None):
    """Grava os quadros em `pasta_saida` e devolve o que foi feito.

    Retorno: {"info", "instantes", "regioes_ignoradas", "quadros": [...]}; cada
    quadro tem tempo_s, arquivo, tipo (inicio/tela/parcial/mouse), pixels_alterados,
    fracao e regiao (retangulo da mudanca, em pixels do video original).
    """
    avisar = progresso or (lambda _m: None)
    info = info_video(caminho_video)
    dims = _dimensoes_cmp(info["largura"], info["altura"])
    duracao = info["duracao_s"] or 0

    if ignorar_ruido and not todos:
        avisar("[quadros] leitura 1/2: procurando regioes que mudam o tempo todo ...")
        trechos = _trechos_de_layout(caminho_video, intervalo, dims)
    else:
        trechos = [{"inicio_s": 0, "fim_s": None, "caixas": [],
                    "mascara": np.zeros((dims[1], dims[0]), dtype=bool)}]
    for t in trechos:
        t["valido"] = ~t["mascara"]
        t["n_valido"] = max(1, int(t["valido"].sum()))

    os.makedirs(pasta_saida, exist_ok=True)
    _limpar_quadros_antigos(pasta_saida, prefixo)
    avisar("[quadros] leitura 2/2: salvando quando a tela muda ..." if not todos
           else "[quadros] salvando todos os instantes ...")

    quadros = []
    ultimo = None
    instantes = 0
    marco = 0.1
    it = 0
    for seg, f in _amostras(caminho_video, intervalo):
        instantes += 1
        while it + 1 < len(trechos) and seg >= trechos[it + 1]["inicio_s"]:
            it += 1
        valido, n_valido = trechos[it]["valido"], trechos[it]["n_valido"]
        g = _cinza(f, dims)
        if ultimo is None:
            px, regiao, tipo = 0, None, "inicio"
        else:
            d = (np.abs(g - ultimo) > NIVEL) & valido
            px = int(d.sum())
            if not todos and px <= limiar_px:
                continue
            fracao = px / n_valido
            tipo = "tela" if fracao >= FRACAO_TELA else "parcial" if fracao >= FRACAO_PARCIAL else "mouse"
            regiao = None
            if px:
                ys, xs = np.nonzero(d)
                regiao = _para_original((xs.min(), ys.min(), xs.max() + 1, ys.max() + 1), dims, info)
        nome = f"{prefixo}_{hhmmss(seg)}.{formato}"
        _salvar(f, os.path.join(pasta_saida, nome), formato, qualidade)
        quadros.append({
            "tempo_s": seg,
            "arquivo": nome,
            "tipo": tipo,
            "pixels_alterados": px,
            "fracao": round(px / n_valido, 4),
            "regiao": regiao,
        })
        ultimo = g
        if duracao and seg / duracao >= marco:
            avisar(f"[quadros] {int(seg / duracao * 100)}% ({len(quadros)} salvos)")
            marco = (int(seg / duracao * 10) + 1) / 10

    regioes = [{
        "de_s": t["inicio_s"],
        "ate_s": t["fim_s"],
        "caixas": [{"regiao": _para_original(c, dims, info), "inteira": inteira} for c, inteira in t["caixas"]],
    } for t in trechos if t["caixas"]]
    return {
        "info": info,
        "instantes": instantes,
        "regioes_ignoradas": regioes,
        "quadros": quadros,
    }


def extrair_instante(caminho_video, pasta_saida, prefixo, segundos, formato="png", qualidade=95):
    """Grava o quadro exato de um instante (para o que caiu entre dois quadros salvos)."""
    os.makedirs(pasta_saida, exist_ok=True)
    nome = f"{prefixo}_{hhmmss(segundos)}_exato.{formato}"
    destino = os.path.join(pasta_saida, nome)

    with av.open(caminho_video) as c:
        v = c.streams.video[0]
        t0 = _inicio(c) or 0.0
        alvo = t0 + segundos
        c.seek(int(alvo * av.time_base), backward=True, any_frame=False)
        for f in c.decode(v):
            if f.time is None:
                continue
            if f.time > alvo + 0.5:
                break  # a busca passou do ponto: cai na leitura sequencial abaixo
            if f.time >= alvo - 1e-3:
                _salvar(f, destino, formato, qualidade)
                return destino

    for seg, f in _amostras(caminho_video, 1):
        if seg >= segundos:
            _salvar(f, destino, formato, qualidade)
            return destino
    raise ValueError(f"o video termina antes de {segundos}s")
