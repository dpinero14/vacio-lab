import pandas as pd

from vlab.sources import PESO_KG, annualize, cattle_movements, cement_by_zone, fuel_by_zone, grains_by_zone, parse_afcp_html, read_eess


def _zonas():
    return pd.DataFrame({"id": [1, 2, 3], "codigo": ["BCP", "BBB", "LSR"], "provincia": ["BUENOS AIRES", "BUENOS AIRES", "LA PAMPA"],
                         "centroide": ["CABA", "BAHIA BLANCA", "SANTA ROSA"], "lon": [-58.37, -62.27, -64.29], "lat": [-34.60, -38.72, -36.62]})


def _dz():
    return pd.DataFrame({"departamento_id": ["06056", "06427", "42133"], "departamento": ["Bahía Blanca", "La Matanza", "Toay"],
                         "provincia": ["BUENOS AIRES", "BUENOS AIRES", "LA PAMPA"], "codigo": ["BBB", "BBB", "LSR"]})


SENASA = """fecha,salido_de,ingresado_a,provincia_origen,provincia_origen_id,departamento_origen,departamento_origen_id,provincia_destino,provincia_destino_id,departamento_destino,departamento_destino_id,vaca,vaquillona,novillo,novillito,ternero,ternera,torito,toro,bueyes
2018-01,Establecimiento,Frigorífico,La Pampa,42,Toay,42133,Buenos Aires,06,Bahía Blanca,06056,10,0,0,0,0,0,0,0,0
2018-02,Establecimiento,Establecimiento,La Pampa,42,Toay,42133,Buenos Aires,06,La Matanza,06427,0,0,0,0,100,0,0,0,0
2018-03,Establecimiento,Establecimiento,Buenos Aires,06,Bahía Blanca,06056,Buenos Aires,06,Bahía Blanca,06056,500,500,500,500,500,500,500,500,500
2018-04,Establecimiento,Establecimiento,Buenos Aires,06,Bahía Blanca,06056,Ciudad Autónoma de Buenos Aires,02,Ciudad Autónoma de Buenos Aires,02000,0,0,0,0,0,0,0,1,0
2018-05,Establecimiento,Establecimiento,Buenos Aires,06,Bahía Blanca,06056,Buenos Aires,06,La Matanza,06427,0,0,0,0,0,0,0,0,0
2018-06,Establecimiento,Establecimiento,Buenos Aires,06,Bahía Blanca,06056,Buenos Aires,06,La Matanza,06427,0,0,0,0,0,0,0,0,0
"""


def test_senasa_cabezas_a_toneladas(tmp_path):
    p = tmp_path / "senasa.csv"
    p.write_text(SENASA, encoding="latin-1")
    t = cattle_movements(2018, zonas=_zonas(), dz=_dz(), path=p)
    assert list(t.columns) == ["anio", "origen", "destino", "producto", "t", "fuente"]
    assert set(t["producto"]) == {"bovinos"}
    por_par = t.set_index(["origen", "destino"])["t"]
    # seis meses de datos: se anualiza por 12/6 = 2; el movimiento dentro de Bahía Blanca no cuenta
    assert abs(por_par[("LSR", "BBB")] - (10 * PESO_KG["vaca"] / 1000 + 100 * PESO_KG["ternero"] / 1000) * 2) < 1e-9
    assert abs(por_par[("BBB", "BCP")] - PESO_KG["toro"] / 1000 * 2) < 1e-9        # la Ciudad va a BCP por su id de provincia
    assert ("BBB", "BBB") not in por_par.index


def test_anualizar_descarta_anios_cortos():
    df = pd.DataFrame({"anio": [2026], "origen": [None], "destino": ["BBB"], "producto": ["diesel"], "t": [10.0], "fuente": ["x"]})
    assert annualize(df, 8)["t"].iloc[0] == 15.0
    assert annualize(df, 12)["t"].iloc[0] == 10.0
    assert annualize(df, 3).empty


AFCP = """<html><body><table>
<tr><td colspan="13">Consumo de Cemento por Provincias y según Envases</td></tr>
<tr><td colspan="13">Período: Agosto  de 2025</td></tr>
<tr><td rowspan="3">Provincias</td><td colspan="12">2025</td></tr>
<tr><td colspan="4">Bolsa</td><td colspan="4">Granel</td><td colspan="4">Totales</td></tr>
<tr><td>Del Mes</td><td>% / Total</td><td>Acum.</td><td>% / Total</td><td>Del Mes</td><td>% / Total</td><td>Acum.</td><td>% / Total</td><td>Del Mes</td><td>% / Total</td><td>Acum.</td><td>% / Total</td></tr>
<tr><td>CAPITAL  FEDERAL</td><td>11.417</td><td>2,3%</td><td>105.897</td><td>2,8%</td><td>8.879</td><td>2,3%</td><td>87.015</td><td>3,2%</td><td>20.296</td><td>2,3%</td><td>192.912</td><td>2,9%</td></tr>
<tr><td>LA PAMPA</td><td>3.000</td><td>0,6%</td><td>30.000</td><td>0,8%</td><td>1.655</td><td>0,4%</td><td>16.000</td><td>0,6%</td><td>4.655</td><td>0,5%</td><td>46.000</td><td>0,7%</td></tr>
<tr><td>SGO. DEL  ESTERO</td><td>15.000</td><td>3,0%</td><td>120.000</td><td>3,2%</td><td>4.639</td><td>1,2%</td><td>40.000</td><td>1,5%</td><td>19.639</td><td>2,2%</td><td>160.000</td><td>2,4%</td></tr>
<tr><td>TOTALES</td><td>29.417</td><td>100,0%</td><td>255.897</td><td>100,0%</td><td>15.173</td><td>100,0%</td><td>143.015</td><td>100,0%</td><td>44.590</td><td>100,0%</td><td>398.912</td><td>100,0%</td></tr>
<tr><td colspan="13">Período: Agosto  de 2024</td></tr>
<tr><td rowspan="3">Provincias</td><td colspan="12">2024</td></tr>
<tr><td colspan="4">Bolsa</td><td colspan="4">Granel</td><td colspan="4">Totales</td></tr>
<tr><td>Del Mes</td><td>% / Total</td><td>Acum.</td><td>% / Total</td><td>Del Mes</td><td>% / Total</td><td>Acum.</td><td>% / Total</td><td>Del Mes</td><td>% / Total</td><td>Acum.</td><td>% / Total</td></tr>
<tr><td>LA PAMPA</td><td>2.000</td><td>0,6%</td><td>20.000</td><td>0,8%</td><td>1.000</td><td>0,4%</td><td>10.000</td><td>0,6%</td><td>3.000</td><td>0,5%</td><td>30.000</td><td>0,7%</td></tr>
<tr><td>TOTALES</td><td>2.000</td><td>100,0%</td><td>20.000</td><td>100,0%</td><td>1.000</td><td>100,0%</td><td>10.000</td><td>100,0%</td><td>3.000</td><td>100,0%</td><td>30.000</td><td>100,0%</td></tr>
</table></body></html>"""


def test_afcp_lee_tres_provincias_y_el_anio_anterior():
    t = parse_afcp_html(AFCP)
    assert len(t) == 4 and set(t["anio"]) == {2024, 2025} and set(t["mes"]) == {8}
    v = t.set_index(["anio", "provincia"])["t"]
    assert v[(2025, "CAPITAL FEDERAL")] == 20296 and v[(2025, "LA PAMPA")] == 4655 and v[(2025, "SGO. DEL ESTERO")] == 19639
    assert v[(2024, "LA PAMPA")] == 3000
    assert "TOTALES" not in set(t["provincia"])


def test_cemento_reparte_la_provincia_entre_sus_zonas(tmp_path):
    p = tmp_path / "afcp_provincias.csv"
    pd.DataFrame({"anio": [2025] * 6, "mes": [1, 2, 3, 4, 5, 6], "provincia": ["LA PAMPA"] * 6, "t": [100.0] * 6}).to_csv(p, index=False)
    t = cement_by_zone(2025, zonas=_zonas(), path=p)
    assert t["destino"].tolist() == ["LSR"] and t["t"].iloc[0] == 1200.0 and t["origen"].isna().all()    # seis meses: por 12/6


EESS = """anio,mes,operador,localidad,provincia,producto,canal_de_comercializacion,volumen
2018,01,X,TOAY,LA PAMPA,Gas Oil Grado 2,Al público,100
2018,01,X,TOAY,LA PAMPA,Gas Oil Grado 3,Transporte de cargas,50
2018,01,X,TOAY,LA PAMPA,GNC,Al público,99999
2018,01,X,TOAY,LA PAMPA,Nafta (súper) entre 92 y 95 Ron,Al público,10
2018,01,X,TOAY,LA PAMPA,Gas Oil Grado 2,Reventa a otras estaciones de servicio,1000
2018,02,X,TOAY,LA PAMPA,Gas Oil Grado 2,Al público,50000
2018,02,X,TOAY,LA PAMPA,Nafta (súper) entre 92 y 95 Ron,Al público,10
"""


def test_eess_reduce_y_descarta_errores(tmp_path):
    p = tmp_path / "eess_2018.csv"
    p.write_text("﻿" + EESS, encoding="utf-8")
    g = read_eess(p)
    assert set(g["producto"]) == {"diesel", "nafta"}
    assert g[g["producto"] == "diesel"]["m3"].sum() == 150.0     # sin GNC, sin reventa, sin los 50.000 m³ de un mes


MAGYP = """cultivo,anio,campania,provincia,provincia_id,departamento,departamento_id,produccion_tm
Soja total,2024,2024/2025,La Pampa,42,Toay,42133,1000
Soja total,2024,2024/2025,Buenos Aires,06,Bahía Blanca,06056,500
Maíz,2024,2024/2025,Buenos Aires,06,Bahía Blanca,99999,200
Trigo total,2023,2023/2024,Buenos Aires,06,Bahía Blanca,06056,300
"""


def test_granos_por_zona_de_origen(tmp_path):
    p = tmp_path / "magyp.csv"
    p.write_text(MAGYP, encoding="utf-8")
    t = grains_by_zone(2025, zonas=_zonas(), dz=_dz(), path=p).set_index(["origen", "producto"])["t"]
    assert t[("LSR", "soja")] == 1000 and t[("BBB", "soja")] == 500
    assert t[("BBB", "maiz")] == 200        # id desconocido: por nombre dentro de la provincia
    assert ("BBB", "trigo") not in t.index  # campaña 2023/2024 es 2024, no 2025


def test_fuel_by_zone_usa_el_mapa_de_localidades(tmp_path):
    (tmp_path / "eess_2018.csv").write_text("﻿" + EESS, encoding="utf-8")
    loc = pd.DataFrame({"localidad": ["TOAY"], "provincia": ["LA PAMPA"], "codigo": ["LSR"], "metodo": ["departamento"]})
    t = fuel_by_zone(2018, raw=tmp_path, zonas=_zonas(), cache_dir=None, localidades=loc, fetch=False)
    assert t.empty                                   # dos meses no alcanzan para un año
    csv = EESS + "".join(f"2018,{m:02d},X,TOAY,LA PAMPA,Gas Oil Grado 2,Al público,100\n" for m in range(3, 9))
    (tmp_path / "eess_2018.csv").write_text("﻿" + csv, encoding="utf-8")
    t = fuel_by_zone(2018, raw=tmp_path, zonas=_zonas(), cache_dir=None, localidades=loc, fetch=False).set_index("producto")
    assert t.loc["diesel", "destino"] == "LSR" and abs(t.loc["diesel", "t"] - (150 + 600) * 0.84 * 12 / 8) < 1e-9
