import json

import pandas as pd

from vlab.zoning import department_zones, locality_zones, normalize, province_to_zones


def _zonas():
    # dos zonas en Buenos Aires (la Ciudad y Bahía Blanca), una en La Pampa
    return pd.DataFrame({"id": [1, 2, 3], "codigo": ["BCP", "BBB", "LSR"], "provincia": ["BUENOS AIRES", "BUENOS AIRES", "LA PAMPA"],
                         "centroide": ["CABA", "BAHIA BLANCA", "SANTA ROSA"], "lon": [-58.37, -62.27, -64.29], "lat": [-34.60, -38.72, -36.62]})


def _georef(tmp_path):
    deps = {"departamentos": [
        {"id": "06056", "nombre": "Bahía Blanca", "centroide": {"lat": -38.7, "lon": -62.3}, "provincia": {"id": "06", "nombre": "Buenos Aires"}},
        {"id": "06427", "nombre": "La Matanza", "centroide": {"lat": -34.8, "lon": -58.6}, "provincia": {"id": "06", "nombre": "Buenos Aires"}},
        {"id": "02007", "nombre": "Comuna 1", "centroide": {"lat": -34.6, "lon": -58.37}, "provincia": {"id": "02", "nombre": "Ciudad Autónoma de Buenos Aires"}},
        {"id": "42133", "nombre": "Toay", "centroide": {"lat": -36.7, "lon": -64.4}, "provincia": {"id": "42", "nombre": "La Pampa"}},
    ]}
    p = tmp_path / "georef_departamentos.json"
    p.write_text(json.dumps(deps, ensure_ascii=False), encoding="utf-8")
    return p


def test_normalize():
    assert normalize("Ciudad Autónoma de Buenos Aires") == "CIUDAD AUTONOMA DE BUENOS AIRES"
    assert normalize("  CAPITAL  FEDERAL ") == "CAPITAL FEDERAL"


def test_departamentos_a_zonas_dentro_de_la_provincia(tmp_path):
    dz = department_zones(_zonas(), _georef(tmp_path)).set_index("departamento_id")["codigo"]
    assert dz["06056"] == "BBB" and dz["06427"] == "BBB"       # La Matanza queda en Buenos Aires, no en la Ciudad
    assert dz["02007"] == "BCP"                                # las comunas van a la Ciudad
    assert dz["42133"] == "LSR"                                # y Toay no cruza a Buenos Aires aunque estuviera más cerca


def test_provincia_a_zonas_con_gran_buenos_aires():
    pz = province_to_zones(_zonas())
    assert pz["GRAN BUENOS AIRES"] == ["BCP"] and pz["CAPITAL FEDERAL"] == ["BCP"]
    assert pz["BUENOS AIRES"] == ["BBB"] and pz["LA PAMPA"] == ["LSR"]
    assert "SGO. DEL ESTERO" not in pz                        # el alias solo existe si la provincia tiene zonas


def test_localidades_con_cache_y_sin_red(tmp_path):
    georef = _georef(tmp_path)
    cache = tmp_path / "georef_localidades.json"
    cache.write_text(json.dumps({"06|INGENIERO WHITE": {"lon": -62.27, "lat": -38.78, "departamento_id": "06056"},
                                 "06|SIN DEPARTAMENTO": {"lon": -58.6, "lat": -34.8, "departamento_id": None},
                                 "42|PUEBLO INVENTADO": None}), encoding="utf-8")
    pares = [("Ingeniero White", "Buenos Aires"), ("sin departamento", "BUENOS AIRES"), ("Pueblo Inventado", "La Pampa"), ("Cualquiera", "CAPITAL FEDERAL")]
    r = locality_zones(pares, cache_path=cache, zonas=_zonas(), georef_path=georef, fetch=False).set_index("localidad")
    assert r.loc["INGENIERO WHITE", "codigo"] == "BBB" and r.loc["INGENIERO WHITE", "metodo"] == "departamento"
    assert r.loc["SIN DEPARTAMENTO", "codigo"] == "BBB" and r.loc["SIN DEPARTAMENTO", "metodo"] == "centroide"
    assert r.loc["PUEBLO INVENTADO", "codigo"] == "LSR" and r.loc["PUEBLO INVENTADO", "metodo"] == "provincia"   # no está: al centro de la provincia
    assert r.loc["CUALQUIERA", "codigo"] == "BCP"
    assert (r["metodo"] == "provincia").sum() == 1
