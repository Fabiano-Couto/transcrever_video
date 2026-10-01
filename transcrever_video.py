# -*- coding: utf-8 -*-
"""Transcreve um video e extrai os quadros da tela, para o agente ver o que foi mostrado.

Uso:
    python transcrever_video.py <video> [--intervalo 1] [--limiar 20] [--todos]
                             [--transcricao auto|whisper|nenhuma|<arquivo.txt>]
                             [--modelo large-v3-turbo] [--idioma pt]
                             [--formato jpg|png] [--qualidade 90] [--refazer]
    python transcrever_video.py <video> --quadro 00:07:22 [00:07:25 ...]

Cria, ao lado do video, a pasta <nome do video> com:
    <nome>_HHMMSS.jpg   um quadro cada vez que a tela muda (inclusive mouse)
    00-ROTEIRO.md       transcricao + marcacao de quando e onde a tela mudou
    00-TRANSCRICAO.txt  transcricao normalizada em HH:MM:SS
    00-INDICE.json      tudo em formato de maquina
"""
import argparse
import io
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

from nucleo import (ARQUIVO_ROTEIRO, LIMIAR_PADRAO, analisar, extrair_instante,  # noqa: E402
                    pasta_padrao)
from nucleo.tempo import hh_mm_ss, ler_tempo  # noqa: E402


def avisar(msg):
    print(msg, file=sys.stderr, flush=True)


def main() -> int:
    ap = argparse.ArgumentParser(description="Transcricao + quadros da tela de um video.")
    ap.add_argument("video")
    ap.add_argument("--intervalo", type=int, default=1, help="de quantos em quantos segundos olhar a tela (padrao: 1)")
    ap.add_argument("--limiar", type=int, default=LIMIAR_PADRAO,
                    help=f"pontos alterados para salvar quadro; menor = mais sensivel (padrao: {LIMIAR_PADRAO})")
    ap.add_argument("--todos", action="store_true", help="salva todos os instantes, sem descartar repetidos")
    ap.add_argument("--sem-mascara", action="store_true",
                    help="nao ignora as regioes que mudam o tempo todo (participantes)")
    ap.add_argument("--transcricao", default="auto",
                    help="auto (arquivo vizinho, senao Whisper) | whisper | nenhuma | caminho de um .txt")
    ap.add_argument("--modelo", default="large-v3-turbo", help="modelo do Whisper (padrao: large-v3-turbo)")
    ap.add_argument("--idioma", default="pt", help="idioma do Whisper (padrao: pt)")
    ap.add_argument("--formato", choices=("jpg", "png"), default="jpg")
    ap.add_argument("--qualidade", type=int, default=90, help="qualidade do JPG (padrao: 90)")
    ap.add_argument("--pasta", help="pasta de saida (padrao: pasta com o nome do video, ao lado dele)")
    ap.add_argument("--refazer", action="store_true", help="nao reaproveita a transcricao da rodada anterior")
    ap.add_argument("--quadro", nargs="+", metavar="HH:MM:SS",
                    help="so extrai o quadro exato destes instantes (PNG) e sai")
    args = ap.parse_args()

    if not os.path.isfile(args.video):
        avisar(f"ERRO: video nao encontrado: {args.video}")
        return 1
    if args.intervalo < 1:
        avisar("ERRO: --intervalo tem de ser 1 ou mais (o nome do quadro e em segundos)")
        return 1

    pasta = args.pasta or pasta_padrao(args.video)
    titulo = os.path.splitext(os.path.basename(args.video))[0]

    if args.quadro:
        for texto in args.quadro:
            caminho = extrair_instante(args.video, pasta, titulo, ler_tempo(texto))
            print(caminho)
        return 0

    indice = analisar(args.video, pasta_saida=pasta, intervalo=args.intervalo, limiar_px=args.limiar,
                      todos=args.todos, ignorar_ruido=not args.sem_mascara, formato=args.formato,
                      qualidade=args.qualidade, transcricao=args.transcricao, modelo=args.modelo,
                      idioma=args.idioma, refazer=args.refazer, progresso=avisar)

    quadros = indice["quadros"]
    tipos = {}
    for q in quadros:
        tipos[q["tipo"]] = tipos.get(q["tipo"], 0) + 1
    print(f"Pasta: {indice['pasta']}")
    print(f"Roteiro: {os.path.join(indice['pasta'], ARQUIVO_ROTEIRO)}")
    print(f"Duracao: {hh_mm_ss(indice['video']['duracao_s'] or 0)}")
    print(f"Quadros: {len(quadros)} salvos de {indice['instantes_analisados']} instantes "
          f"(tela nova {tipos.get('tela', 0)}, parcial {tipos.get('parcial', 0)}, "
          f"mouse/detalhe {tipos.get('mouse', 0)})")
    print(f"Transcricao: {indice['transcricao']['fonte']} ({len(indice['falas'])} falas)")
    for trecho in indice["regioes_ignoradas"]:
        print(f"Ignorado de {hh_mm_ss(trecho['de_s'])} a {hh_mm_ss(trecho['ate_s'])}: "
              f"{[c['regiao'] for c in trecho['caixas']]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
