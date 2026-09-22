import numpy as np
import pandas as pd

from vlab.od import asymmetry, clean_name, parse_sheet, structural_empty

CODES = ["AAA", "BBB", "CCC"]


def test_parse_sheet_con_codigos_y_numeros_como_2018():
    rows = [("", "", "AAA", "BBB", "CCC"), ("", "", 1, 2, 3), ("AAA", 1, 5, 10, 0), ("BBB", 2, 0, 0, 7), ("CCC", 3, 2, 0, 0)]
    m = parse_sheet(rows, CODES)
    assert list(m.index) == CODES and list(m.columns) == CODES
    assert m.loc["AAA", "BBB"] == 10 and m.loc["CCC", "AAA"] == 2 and m.loc["BBB", "BBB"] == 0


def test_parse_sheet_solo_numeros_como_2014():
    rows = [("", 1, 2, 3), (1, 0, 4, 0), (2, 1, 0, 0), (3, 0, 0, 9)]
    m = parse_sheet(rows, CODES)
    assert m.loc["AAA", "BBB"] == 4 and m.loc["BBB", "AAA"] == 1 and m.loc["CCC", "CCC"] == 9


def test_parse_sheet_con_titulo_como_2016():
    rows = [("Carne Bovinos", "", 1, 2, 3), ("", "", "AAA", "BBB", "CCC"), (1, "AAA", 0, 6, 0), (2, "BBB", 0, 0, 0), (3, "CCC", 3, 0, 0)]
    m = parse_sheet(rows, CODES)
    assert m.loc["AAA", "BBB"] == 6 and m.loc["CCC", "AAA"] == 3 and m.values.sum() == 9


def test_asymmetry_y_vacio_estructural():
    m = pd.DataFrame([[0, 100, 0], [20, 0, 0], [0, 0, 50]], index=CODES, columns=CODES, dtype=float)
    a = asymmetry(m)
    assert len(a) == 1 and a.iloc[0].origen == "AAA" and a.iloc[0].destino == "BBB"
    assert a.iloc[0].ida == 100 and a.iloc[0].vuelta == 20 and abs(a.iloc[0].sin_vuelta - 0.8) < 1e-9
    e = structural_empty(m)
    assert e["total"] == 120 and e["emparejado"] == 40 and e["vacio_estructural"] == 80 and e["intrazonal"] == 50
    assert abs(e["pct_sin_vuelta"] - 100 * 80 / 120) < 1e-9


def test_clean_name():
    assert clean_name("Arena Silicea Toneladas 2018") == "arena silicea"
    assert clean_name("TOTAL CARNES TONELADAS 2016") == "total carnes"
    assert clean_name("Limon Tonealdas 2018") == "limon" and clean_name("Aluminio Elab. Ton 2018") == "aluminio elab."
