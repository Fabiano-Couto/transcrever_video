# -*- coding: utf-8 -*-
"""Nucleo da analise de video: quadros, transcricao e roteiro.

Nao depende de terminal nem do Claude: recebe caminhos e parametros, devolve dados.
E o que um backend web (fase 2) importa direto.
"""
import os

from .quadros import LIMIAR_PADRAO, extrair_instante, extrair_quadros
from .roteiro import ARQUIVO_INDICE, ARQUIVO_ROTEIRO, gravar, montar_indice, montar_roteiro
from .transcricao import ARQUIVO_TRANSCRICAO, gravar_transcricao, obter_transcricao


def pasta_padrao(caminho_video):
    """Pasta com o nome do video, ao lado dele."""
    return os.path.splitext(os.path.abspath(caminho_video))[0]


def analisar(caminho_video, pasta_saida=None, intervalo=1, limiar_px=LIMIAR_PADRAO, todos=False,
             ignorar_ruido=True, formato="jpg", qualidade=90, transcricao="auto",
             modelo="large-v3-turbo", idioma="pt", refazer=False, progresso=None):
    """Roda tudo e devolve o indice (o mesmo conteudo do 00-INDICE.json)."""
    titulo = os.path.splitext(os.path.basename(caminho_video))[0]
    pasta = pasta_saida or pasta_padrao(caminho_video)
    os.makedirs(pasta, exist_ok=True)

    extracao = extrair_quadros(caminho_video, pasta, titulo, intervalo=intervalo, limiar_px=limiar_px,
                               todos=todos, ignorar_ruido=ignorar_ruido, formato=formato,
                               qualidade=qualidade, progresso=progresso)
    trans = obter_transcricao(caminho_video, pasta, modo=transcricao, modelo=modelo, idioma=idioma,
                              refazer=refazer, progresso=progresso)
    if trans["falas"]:
        gravar_transcricao(os.path.join(pasta, ARQUIVO_TRANSCRICAO), trans["falas"], trans["fonte"], titulo)

    parametros = {
        "intervalo_s": intervalo,
        "limiar_px": limiar_px,
        "comparacao": "640 px de largura, cinza, diferenca > 20",
        "todos": todos,
        "ignorar_ruido": ignorar_ruido,
        "formato": formato,
        "qualidade": qualidade,
    }
    video = os.path.basename(caminho_video)
    roteiro = montar_roteiro(titulo, video, trans, extracao, parametros)
    indice = montar_indice(titulo, video, trans, extracao, parametros)
    gravar(os.path.join(pasta, ARQUIVO_ROTEIRO), os.path.join(pasta, ARQUIVO_INDICE), roteiro, indice)
    indice["pasta"] = pasta
    return indice
