"""Recorta a area da tela compartilhada de um quadro e amplia, para ler texto pequeno.

Em gravacao de reuniao (tl;dv, Meet, Teams) em 720p, a tela compartilhada ocupa so uma
parte do quadro (os participantes ficam ao lado) e o texto de planilha, ERP ou codigo fica
pequeno demais. Recortar so a area compartilhada e ampliar 2 a 3 vezes torna legivel o que
no quadro inteiro nao se le.

Uso:
  python ampliar_quadro.py <quadro.png|jpg> [mais quadros...] [--area X0 Y0 X1 Y1] [--escala 2]
                           [--saida <pasta>]

  Sem --area, acha sozinho a area compartilhada: a maior faixa clara a partir da esquerda
  (o fundo da chamada e escuro). Confira no primeiro quadro; se errar, passe --area com os
  pixels do quadro original (x0 y0 x1 y1), o mesmo sistema do roteiro.
  A saida e <nome>_zoom.png ao lado do quadro (ou na pasta de --saida).

Dica: amplie o PNG exato (transcrever_video.py --quadro HH:MM:SS), nao o JPG do roteiro:
o JPG ja perdeu detalhe na compressao.
"""
import argparse
import sys
from pathlib import Path

from PIL import Image

LIMIAR_CLARO = 70      # brilho (0-255) acima do qual o pixel conta como "conteudo" (o fundo da chamada fica entre 15 e 45)
FRACAO_LINHA = 0.30    # fracao de pixels claros para a coluna/linha contar como conteudo
LARGURA_MIN = 0.30     # a area compartilhada tem pelo menos 30% da largura do quadro


def _faixas(valores, minimo):
    """Faixas contiguas de indices em que valores[i] >= minimo: [(inicio, fim_exclusivo), ...]."""
    faixas, ini = [], None
    for i, v in enumerate(valores):
        if v >= minimo and ini is None:
            ini = i
        elif v < minimo and ini is not None:
            faixas.append((ini, i))
            ini = None
    if ini is not None:
        faixas.append((ini, len(valores)))
    return faixas


def achar_area(img):
    """(x0, y0, x1, y1) da area compartilhada, ou None se nao achar."""
    cinza = img.convert("L")
    w, h = cinza.size
    px = cinza.load()
    passo = 2  # amostra 1 pixel a cada 2: rapido e suficiente
    colunas = []
    for x in range(w):
        claros = sum(1 for y in range(0, h, passo) if px[x, y] > LIMIAR_CLARO)
        colunas.append(claros / (h / passo))
    # junta buracos pequenos (barra de rolagem, borda) antes de medir as faixas
    faixas_x = [f for f in _faixas(colunas, FRACAO_LINHA) if f[1] - f[0] >= 8]
    if not faixas_x:
        return None
    unidas = [list(faixas_x[0])]
    for a, b in faixas_x[1:]:
        if a - unidas[-1][1] <= 12:
            unidas[-1][1] = b
        else:
            unidas.append([a, b])
    candidatas = [f for f in unidas if f[1] - f[0] >= LARGURA_MIN * w]
    if not candidatas:
        return None
    x0, x1 = candidatas[0]  # a primeira a partir da esquerda: tela compartilhada fica a esquerda
    linhas = []
    for y in range(h):
        claros = sum(1 for x in range(x0, x1, passo) if px[x, y] > LIMIAR_CLARO)
        linhas.append(claros / ((x1 - x0) / passo))
    faixas_y = _faixas(linhas, FRACAO_LINHA)
    if not faixas_y:
        return None
    y0, y1 = max(faixas_y, key=lambda f: f[1] - f[0])
    return x0, y0, x1, y1


def ampliar(caminho, area=None, escala=2.0, saida=None):
    img = Image.open(caminho)
    caixa = tuple(area) if area else achar_area(img)
    if not caixa:
        print(f"{caminho}: nao achei a area compartilhada; passe --area X0 Y0 X1 Y1", file=sys.stderr)
        return None
    recorte = img.crop(caixa)
    recorte = recorte.resize((int(recorte.width * escala), int(recorte.height * escala)), Image.LANCZOS)
    destino = Path(saida) if saida else Path(caminho).parent
    destino.mkdir(parents=True, exist_ok=True)
    arquivo = destino / f"{Path(caminho).stem}_zoom.png"
    recorte.save(arquivo)
    print(f"{arquivo}  (area {caixa[0]} {caixa[1]} {caixa[2]} {caixa[3]}, escala {escala:g})")
    return arquivo


def main():
    ap = argparse.ArgumentParser(description="Recorta a area da tela compartilhada e amplia.")
    ap.add_argument("quadros", nargs="+", help="quadro(s) PNG ou JPG")
    ap.add_argument("--area", nargs=4, type=int, metavar=("X0", "Y0", "X1", "Y1"),
                    help="area em pixels do quadro original (sem isto, detecta sozinho)")
    ap.add_argument("--escala", type=float, default=2.0, help="quantas vezes ampliar (padrao 2)")
    ap.add_argument("--saida", help="pasta de saida (padrao: a do quadro)")
    args = ap.parse_args()
    falhas = 0
    for q in args.quadros:
        if ampliar(q, args.area, args.escala, args.saida) is None:
            falhas += 1
    sys.exit(1 if falhas else 0)


if __name__ == "__main__":
    main()
