import numpy as np
import pandas as pd

from vlab.graduate import graduate, ipf, published_state, summarize_state, zone_factors

CODES = ["EGU", "QCP", "SRO"]


def _m(rows):
    return pd.DataFrame(rows, index=CODES, columns=CODES, dtype=float)


def _matrices():
    return {("ganado en pie", "bovinos"): _m([[10, 20, 30], [5, 0, 15], [40, 10, 0]]),
            ("carnes", "bovinos"): _m([[0, 8, 0], [0, 0, 0], [4, 0, 0]]),
            ("combustibles", "diesel"): _m([[0, 100, 100], [0, 0, 0], [0, 0, 0]]),
            ("granos", "soja"): _m([[0, 0, 100], [0, 0, 0], [10, 0, 0]]),
            ("carnes", "avicola"): _m([[0, 5, 0], [5, 0, 0], [0, 0, 0]])}


def _medido():
    filas = []
    # bovinos: las dos puntas, 2018 y 2022; la zona SRO duplica lo que sale y QCP lo que entra
    for anio, f in ((2018, 1.0), (2022, 1.0)):
        for o, d, t in (("EGU", "QCP", 100), ("SRO", "EGU", 50), ("EGU", "SRO", 30)):
            filas.append({"anio": anio, "origen": o, "destino": d, "producto": "bovinos", "t": t * (2.0 if anio == 2022 and o == "SRO" else 1.0), "fuente": "senasa"})
    # diesel: solo destino, 2018 y 2022; QCP triplica, SRO igual, EGU no aparece en 2022
    filas += [{"anio": 2018, "origen": None, "destino": "QCP", "producto": "diesel", "t": 100.0, "fuente": "eess"},
              {"anio": 2018, "origen": None, "destino": "SRO", "producto": "diesel", "t": 100.0, "fuente": "eess"},
              {"anio": 2018, "origen": None, "destino": "EGU", "producto": "diesel", "t": 10.0, "fuente": "eess"},
              {"anio": 2022, "origen": None, "destino": "QCP", "producto": "diesel", "t": 300.0, "fuente": "eess"},
              {"anio": 2022, "origen": None, "destino": "SRO", "producto": "diesel", "t": 100.0, "fuente": "eess"}]
    return pd.DataFrame(filas)


def test_ipf_converge_a_los_margenes():
    m = _m([[1, 2, 3], [4, 5, 6], [7, 8, 9]])
    r = pd.Series([10.0, 20.0, 30.0], index=CODES)
    c = pd.Series([30.0, 20.0, 10.0], index=CODES)
    a = ipf(m, r, c)
    assert np.allclose(a.sum(axis=1), r, rtol=1e-5) and np.allclose(a.sum(axis=0), c, rtol=1e-5)
    solo_filas = ipf(m, r, None)
    assert np.allclose(solo_filas.sum(axis=1), r)
    # totales distintos: se llevan a la media geométrica
    b = ipf(m, r, c * 4)
    assert abs(b.to_numpy().sum() - np.sqrt(60 * 240)) < 1e-6


def test_zone_factors_con_fallback_nacional():
    f = zone_factors(_medido()[lambda d: d["producto"] == "diesel"], 2022, 2018, "destino", codes=CODES)
    assert f["QCP"] == 3.0 and f["SRO"] == 1.0
    assert abs(f["EGU"] - 400 / 210) < 1e-9          # falta en 2022: factor nacional
    g = zone_factors(_medido()[lambda d: d["producto"] == "diesel"], 2022, 2018, "destino", codes=CODES + ["XXX"], clip=(0.5, 2.0))
    assert g["XXX"] == 400 / 210 and g["QCP"] == 2.0  # zona sin dato: nacional; y el recorte actúa


def test_graduacion_mide_lo_medido_y_deja_el_resto():
    drivers = pd.DataFrame({"soja": {2018: 50.0, 2022: 25.0}, "gasoil": {2018: 1.0, 2022: 1.0}})
    m, estado = graduate(_matrices(), 2022, _medido(), drivers, clip=None)
    e = estado.set_index(["grupo", "producto"])
    assert e.loc[("ganado en pie", "bovinos"), "tipo"] == "medido ambos"
    assert e.loc[("carnes", "bovinos"), "tipo"] == "plano"           # el mismo nombre en otro grupo no se toca
    assert e.loc[("combustibles", "diesel"), "tipo"] == "medido destino"
    assert e.loc[("granos", "soja"), "tipo"] == "escenario driver" and abs(e.loc[("granos", "soja"), "factor_nacional"] - 0.5) < 1e-9
    assert e.loc[("carnes", "avicola"), "tipo"] == "plano" and m[("carnes", "avicola")].equals(_matrices()[("carnes", "avicola")])
    # diesel: la columna QCP se triplica, SRO queda igual
    d = m[("combustibles", "diesel")]
    assert d.loc["EGU", "QCP"] == 300.0 and d.loc["EGU", "SRO"] == 100.0
    # bovinos: lo que sale de SRO se duplica, y la matriz cierra en los dos márgenes
    b = m[("ganado en pie", "bovinos")]
    b18 = _matrices()[("ganado en pie", "bovinos")]
    assert 1.7 < b.loc["SRO"].sum() / b18.loc["SRO"].sum() < 2.3          # origen SRO: factor 2
    assert 1.7 < b["EGU"].sum() / b18["EGU"].sum() < 2.3                  # destino EGU: factor 2
    assert abs(b.sum(axis=1).sum() - b.sum(axis=0).sum()) < 1e-6 and b.to_numpy().sum() > b18.to_numpy().sum()


def test_graduacion_encadena_con_el_driver_cuando_no_hay_base():
    medido = _medido()
    medido = medido[~((medido["producto"] == "diesel") & (medido["anio"] == 2018))]
    medido.loc[medido["producto"] == "diesel", "anio"] = 2021
    medido = pd.concat([medido, pd.DataFrame([{"anio": 2022, "origen": None, "destino": "QCP", "producto": "diesel", "t": 600.0, "fuente": "eess"},
                                              {"anio": 2022, "origen": None, "destino": "SRO", "producto": "diesel", "t": 100.0, "fuente": "eess"}])], ignore_index=True)
    drivers = pd.DataFrame({"gasoil": {2018: 1.0, 2021: 1.5, 2022: 2.0}, "soja": {2018: 1.0, 2021: 1.0, 2022: 1.0}})
    m, estado = graduate(_matrices(), 2022, medido, drivers, clip=None)
    e = estado.set_index(["grupo", "producto"])
    assert e.loc[("combustibles", "diesel"), "tipo"] == "medido destino" and "desde 2021" in e.loc[("combustibles", "diesel"), "fuente"]
    d = m[("combustibles", "diesel")]
    assert abs(d.loc["EGU", "QCP"] - 100 * 1.5 * 2.0) < 1e-9 and abs(d.loc["EGU", "SRO"] - 100 * 1.5 * 1.0) < 1e-9


def test_nombres_de_la_edicion_en_camiones():
    from vlab.graduate import canonical_product

    assert canonical_product("bovinos en pie") == "bovinos" and canonical_product("trit. petreos camion") == "trit. petreos"
    assert canonical_product("alum. elab.") == "aluminio elab." and canonical_product("sulfato de sodio .") == "sulfato de sodio"
    camiones = {("ganado en pie", "bovinos en pie"): _matrices()[("ganado en pie", "bovinos")], ("carnes", "bovinos"): _matrices()[("carnes", "bovinos")],
                ("mineria", "trit. petreos camion"): _matrices()[("granos", "soja")]}
    drivers = pd.DataFrame({"isac": {2018: 1.0, 2022: 2.0}, "soja": {2018: 1.0, 2022: 1.0}, "gasoil": {2018: 1.0, 2022: 1.0}})
    m, estado = graduate(camiones, 2022, _medido(), drivers, clip=None)
    e = estado.set_index(["grupo", "producto"])
    assert e.loc[("ganado en pie", "bovinos en pie"), "tipo"] == "medido ambos"       # la hoja en camiones encuentra su fuente
    assert e.loc[("carnes", "bovinos"), "tipo"] == "plano"
    assert e.loc[("mineria", "trit. petreos camion"), "tipo"] == "escenario driver" and e.loc[("mineria", "trit. petreos camion"), "factor_nacional"] == 2.0


def test_arena_y_resumen():
    drivers = pd.DataFrame({"soja": {2018: 1.0, 2022: 1.0}, "gasoil": {2018: 1.0, 2022: 1.0}})
    m, estado = graduate(_matrices(), 2022, None, drivers, arena_t=3000.0, unidad="camiones")
    assert m[("mineria arena de fractura", "arena de fractura no vista")].loc["EGU", "QCP"] == 100.0
    r = summarize_state(estado).loc[2022]
    assert r["n_medidos"] == 1 and r["n_escenario"] == 2 and r["n_plano"] == 3
    p = published_state(_matrices(), 2016)
    assert (p["tipo"] == "medido ambos").all() and len(p) == 5
