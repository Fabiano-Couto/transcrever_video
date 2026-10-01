---
name: transcrever-video
description: Transcreve um video e extrai os quadros da tela (um a cada mudanca, inclusive movimento de mouse), para o agente LER a fala e VER o que foi mostrado - use quando o usuario apontar um video em que a imagem importa (reuniao gravada no tl;dv, Meet, Teams ou Zoom, gravacao de tela, demonstracao de sistema, treinamento; .ts .mp4 .mkv .webm .mov .avi) ou perguntar o que foi mostrado, apontado ou explicado na tela. Para audio puro (WhatsApp, recado de voz) use a skill transcrever-audio.
---

# Transcrever video (fala + tela)

Claude nao assiste video. Esta skill transforma o video numa pasta que da para ler:
a transcricao da fala e os quadros da tela, nomeados pelo segundo em que aparecem,
mais um roteiro que diz em que momento a tela mudou e onde. Tudo roda local: nenhum
video sai da maquina.

## 1. Ja foi processado?

Ao lado do video fica uma pasta com o nome dele. Se ela ja tem **00-ROTEIRO.md**,
pule para o passo 3: nao reprocesse sem motivo.

## 2. Processar

Use o Python do venv desta skill (a pasta que o Claude Code informa como
"Base directory for this skill"):

```bash
"<pasta-da-skill>/venv/Scripts/python.exe" "<pasta-da-skill>/transcrever_video.py" "<caminho/do/video.mp4>"
```

(fora do Windows: `venv/bin/python`). Sempre entre aspas: caminho de usuario tem
espaco e acento. Rode **em segundo plano com timeout alto**: os quadros levam cerca de
1 minuto para cada 20 de video; se precisar do Whisper, a transcricao leva de metade
ao tempo total do video em CPU.

A transcricao vem, nesta ordem: de um .txt ao lado do video cujo nome comece com o
nome dele (ex.: a transcricao exportada do tl;dv, que traz quem falou); da rodada
anterior; ou do Whisper (large-v3-turbo, pt).

Opcoes uteis:

| Flag | Padrao | Para que serve |
|---|---|---|
| `--intervalo` | 1 | de quantos em quantos segundos olhar a tela |
| `--limiar` | 20 | pontos alterados para salvar quadro; menor = mais sensivel |
| `--todos` | off | salva todos os instantes, sem descartar repetidos |
| `--transcricao` | auto | `auto`, `whisper`, `nenhuma` ou o caminho de um .txt |
| `--modelo` / `--idioma` | large-v3-turbo / pt | Whisper |
| `--refazer` | off | nao reaproveita a transcricao da rodada anterior |
| `--quadro HH:MM:SS ...` | - | so extrai o quadro exato desses instantes (PNG) |

## 3. Ler o roteiro

Abra **00-ROTEIRO.md** (em video longo, leia por partes). Cada fala traz:

- `tela vigente`: o que estava na tela quando a fala comecou;
- as mudancas durante a fala, uma por linha, com o tipo e a regiao em pixels do video:
  - **TELA NOVA**: troca de janela, tela ou aba (boa para ter a visao geral);
  - **mudanca parcial**: rolagem, popup, filtro aplicado;
  - **mouse/detalhe**: ponteiro, selecao de celula, digitacao. E aqui que se ve o que
    a pessoa estava apontando.

## 4. Abrir so os quadros que a fala pede

Nunca abra a pasta inteira. Os sinais de que a fala depende da tela sao frases como
"ta vendo", "vou abrir aqui", "essa coluna", "esse cara aqui", "clica ali", "esse
valor". Nesses pontos:

1. abra a `tela vigente` da fala para saber o contexto;
2. abra os quadros de **mouse/detalhe** daquele trecho e procure o ponteiro na regiao
   indicada (x/y em pixels do video);
3. se o momento exato caiu entre dois quadros, extraia com `--quadro HH:MM:SS`.

Quadro sobrando nao e problema; quadro faltando e. Por isso o limiar e baixo.

## 5. Antes de agir

- **Mostre ao usuario** o trecho da fala junto do que foi visto na tela, e peca
  conferencia de nomes proprios e numeros: o Whisper erra jargao ("Sanquia" =
  Sankhya, "Hiro" = hero1, "viu" = view) e numero ditado.
- Numero que aparece na tela vale mais que numero falado. Se divergirem, diga.
- Se o video pertence a um projeto, registre na documentacao do projeto o que for
  requisito: o que foi mostrado na reuniao e requisito, e requisito nao fica so no chat.

## Armadilhas

- **Video em 720p** tem texto pequeno. Se nao der para ler, extraia o instante em PNG
  com `--quadro` (sem perda de compressao) e, se ainda assim nao der, diga que nao
  conseguiu ler em vez de adivinhar.
- O Whisper **nao separa quem fala**. Quando quem falou importa, peca ao usuario a
  transcricao do tl;dv (ou da ferramenta de reuniao) e coloque ao lado do video.
- A comparacao ignora as regioes que mudam o tempo todo (quadradinho dos participantes,
  borda de quem fala). Isso e detectado sozinho e listado no topo do roteiro.
- Se o venv nao existir:
  `python -m venv venv` e `venv/Scripts/python.exe -m pip install -r requirements.txt`
  dentro da pasta da skill. O modelo do Whisper (~1,6 GB) baixa no primeiro uso e fica
  em cache.
