import pandas as pd

from vlab.drivers import factors
from vlab.projection import add_sand, empties_by_group, scale_matrices, yearly

CODES = ["EGU", "QCP", "SRO"]


def _m(rows):
    return pd.DataFrame(rows, index=CODES, columns=CODES, dtype=float)


def _matrices():
    return {("granos", "soja"): _m([[0, 0, 100], [0, 0, 0], [10, 0, 0]]),
            ("mineria", "arena silicea"): _m([[0, 20, 0], [0, 0, 0], [0, 0, 0]]),
            ("carnes", "bovinos"): _m([[0, 5, 0], [5, 0, 0], [0, 0, 0]])}


def test_factores_y_escala():
    drivers = pd.DataFrame({"soja": {2018: 50.0, 2023: 25.0}, "arena_t": {2018: 1000.0, 2023: 5000.0}})
    f = factors(drivers, 2023)
    assert f["soja"] == 0.5 and f["arena_t"] == 5.0
    m, tabla = scale_matrices(_matrices(), f)
    assert m[("granos", "soja")].loc["EGU", "SRO"] == 50.0                     # soja a la mitad, como la sequía
    assert m[("carnes", "bovinos")].loc["EGU", "QCP"] == 5.0                    # sin driver, plano
    assert tabla.set_index("producto").loc["bovinos", "driver"] == "sin driver, plano"


def test_add_sand_descuenta_lo_que_la_matriz_ya_tenia():
    m = add_sand(_matrices(), arena_t=1000.0)
    extra = m[("mineria arena de fractura", "arena de fractura no vista")]
    assert extra.loc["EGU", "QCP"] == 980.0 and extra.values.sum() == 980.0   # 1.000 menos las 20 que ya iban a Neuquén
    assert add_sand(_matrices(), arena_t=10.0)[("mineria arena de fractura", "arena de fractura no vista")].values.sum() == 0.0


def test_vacio_por_grupo_y_por_anio():
    g = empties_by_group(_matrices())
    assert g.loc["carnes", "pct_sin_vuelta"] == 0.0                              # ida y vuelta iguales
    assert abs(g.loc["granos", "pct_sin_vuelta"] - 100 * 90 / 110) < 1e-9
    drivers = pd.DataFrame({"soja": {2018: 1.0, 2020: 1.0}, "arena_t": {2018: 1.0, 2020: 1.0}})
    arena = pd.Series({2018: 20.0, 2020: 2000.0})
    y = yearly(_matrices(), drivers, arena, (2018, 2020))
    assert y.loc[2020, "vacio_mt"] > y.loc[2018, "vacio_mt"] and y.loc[2020, "pct_sin_vuelta"] > y.loc[2018, "pct_sin_vuelta"]
