import io

import pandas as pd
import pytest

from vlab.panel import empty_share, publishable, read_panel, week_report

CSV = """flota,vehiculo,equipo,fecha,origen,destino,ruta,km,cargado,producto,toneladas
A,A1,tolva,2026-10-05,Bell Ville,Rosario,RN 9,240,1,maiz,30
A,A1,tolva,2026-10-05,Rosario,Bell Ville,RN 9,240,0,,
A,A2,batea,2026-10-06,Gualeguaychu,Anelo,RN 152,1400,1,arena,30
B,B1,tolva,2026-10-05,Marcos Juarez,Rosario,RN 9,180,1,soja,30
B,B1,tolva,2026-10-05,Rosario,Marcos Juarez,RN 9,180,0,,
C,C1,tolva,2026-10-07,Venado Tuerto,Rosario,RN 33,160,1,trigo,29
C,C1,tolva,2026-10-07,Rosario,Venado Tuerto,RN 33,160,1,fertilizante,28
D,D1,tolva,2026-10-08,Canals,Rosario,RN 9,200,1,soja,30
D,D1,tolva,2026-10-08,Rosario,Canals,RN 9,200,0,,
"""


def _panel():
    return read_panel(io.StringIO(CSV))


def test_lee_y_valida():
    df = _panel()
    assert len(df) == 9 and set(df["equipo"]) == {"tolva", "batea"}
    with pytest.raises(ValueError):
        read_panel(io.StringIO(CSV.replace("tolva", "camion")))
    with pytest.raises(ValueError):
        read_panel(io.StringIO(CSV.replace(",240,0,", ",240,2,")))


def test_vacio_total_y_por_equipo():
    df = _panel()
    t = empty_share(df)
    assert t.loc[0, "km"] == 2960 and t.loc[0, "km_vacio"] == 620 and abs(t.loc[0, "pct_vacio"] - 100 * 620 / 2960) < 1e-9
    e = empty_share(df, ["equipo"]).set_index("equipo")
    assert e.loc["batea", "pct_vacio"] == 0.0 and e.loc["tolva", "flotas"] == 4


def test_regla_de_publicacion_tres_flotas():
    df = _panel()
    r = publishable(empty_share(df, ["ruta"])).set_index("ruta")
    assert r.loc["RN 9", "publicable"] and r.loc["RN 9", "pct_vacio"] == 50.0
    assert not r.loc["RN 152", "publicable"] and pd.isna(r.loc["RN 152", "pct_vacio"])
    inf = week_report(df)
    assert set(inf) == {"total", "por_equipo", "por_ruta", "por_flota"} and len(inf["por_flota"]) == 4
