# -*- coding: utf-8 -*-
"""Conversao de tempo usada no nome dos quadros e no roteiro."""
import re


def hhmmss(segundos: float) -> str:
    """Formato do nome do arquivo: 76 -> '000116'."""
    s = int(segundos)
    return f"{s // 3600:02d}{s % 3600 // 60:02d}{s % 60:02d}"


def hh_mm_ss(segundos: float) -> str:
    """Formato de leitura: 76 -> '00:01:16'."""
    s = int(segundos)
    return f"{s // 3600:02d}:{s % 3600 // 60:02d}:{s % 60:02d}"


def ler_tempo(texto: str) -> int:
    """Aceita 'HH:MM:SS', 'MM:SS' ou segundos ('76') e devolve segundos inteiros."""
    texto = texto.strip()
    if re.fullmatch(r"\d+", texto):
        return int(texto)
    partes = texto.split(":")
    if not 2 <= len(partes) <= 3 or not all(re.fullmatch(r"\d+", p) for p in partes):
        raise ValueError(f"tempo invalido: {texto!r} (use HH:MM:SS)")
    total = 0
    for p in partes:
        total = total * 60 + int(p)
    return total
