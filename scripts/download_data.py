"""Baja a data/raw todo lo que usa el repo: las matrices origen-destino 2012 a 2018, las zonas, la red vial con flujos por sentido, los drivers y las fuentes del observatorio.

Fuente principal: Secretaría de Transporte, dataset "Matriz Origen-Destino vial de Transporte de Cargas"
(datos.transporte.gob.ar/dataset/matriz-od-vial-cargas) y su IDE (ide.transporte.gob.ar/geoserver, WFS).
Para el observatorio: SENASA (movimientos de bovinos), Secretaría de Energía (volúmenes por estación,
Res. 1104/04), Vialidad Nacional vía IDE Transporte (TMDA, conteos, peajes), georef (departamentos)
y la AFCP (consumo de cemento por provincia, páginas mensuales). Cerca de 1,5 GB en total.
Se puede correr varias veces: lo que ya está, no se vuelve a bajar; la AFCP solo pide los meses que faltan.

El geoserver de IDE Transporte no envía su certificado intermedio; `ca_bundle()` arma un paquete con
certifi más la intermedia pública de Let's Encrypt (scripts/certs) y lo pasa como `verify`.
"""

import sys
import time
from datetime import date
from pathlib import Path
from urllib.parse import quote

import pandas as pd
import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from vlab import DATA_RAW  # noqa: E402
from vlab.sources import parse_afcp_html  # noqa: E402

CKAN = "https://datos.transporte.gob.ar/dataset/3869ea48-0c3f-4f17-b46b-5919e1815f30/resource"
WFS = "https://ide.transporte.gob.ar/geoserver/idera/ows"
WFS_OBSERV = "https://ide.transporte.gob.ar/geoserver/observ/ows"
UA = {"User-Agent": "vacio-lab/0.1 (+https://github.com/dpinero14)"}
CERT_INTERMEDIA = Path(__file__).resolve().parent / "certs" / "lets-encrypt-yr2.pem"

ARCHIVOS = {
    "mtx-2018.zip": f"{CKAN}/202252ea-8741-4e0d-9981-3026ab611a99/download/mtx-2018.zip",
    "mtx-2016.zip": f"{CKAN}/e8089792-b609-4c7b-9fd4-d6c9fda8ead2/download/2016.zip",
    "mtx-2014.zip": f"{CKAN}/9cc2160e-55e1-441f-a000-c5a0ce3b06f0/download/2014.zip",
    "mtx-2012.zip": f"{CKAN}/6d0052f6-c1a9-4076-9608-9dd8605bde49/download/2012.zip",
    "codigos_zonas.xls": f"{CKAN}/1d2cf181-89fc-4ba1-9803-2508b47ec1a3/download/03.-codigos-de-zonas.xls",
    "zonificacion.jpg": f"{CKAN}/e30513f7-65b0-453c-b42c-d431063f3153/download/02.-zonificacion.jpg",
    "metodologia_od_2018.pdf": f"{CKAN}/6457df85-bf46-40dc-8fea-c8904608fb5e/download/informe_metodologico_matrices_origen_y_destino_de_cargas_2018_final.pdf",
    # drivers para proyectar la matriz: producción agrícola por campaña y el registro de fractura (arena)
    "magyp_estimaciones_agricolas.csv": "https://datos.magyp.gob.ar/dataset/9e1e77ba-267e-4eaa-a59f-3296e86b5f36/resource/95d066e6-8a0f-4a80-b59d-6f28f88eacd5/download/estimaciones-agricolas-2026-03.csv",
    "fractura_adjunto_iv.csv": "http://datos.energia.gob.ar/dataset/71fa2e84-0316-4a1b-af68-7f35e41f58d7/resource/2280ad92-6ed3-403e-a095-50139863ab0d/download/datos-de-fractura-de-pozos-de-hidrocarburos-adjunto-iv-actualizacin-diaria.csv",
    # departamentos con centroide (georef), para llevar cada fuente a las zonas
    "georef_departamentos.json": "https://apis.datos.gob.ar/georef/api/departamentos?max=600&campos=id,nombre,centroide,provincia.nombre,provincia.id",
}
# capas de la red vial simplificada con la asignación de camiones 2018, una por grupo y el total
CAPAS = {
    "red_total_2018.geojson": "idera:Carga transportada total 2018",
    "red_grupo_carnes_2018.geojson": "idera:Carga transportada grupo carnes 2018",
    "red_grupo_ganado_en_pie_2018.geojson": "idera:Carga transportada grupo  ganado en pie2018",
    "red_grupo_combustibles_2018.geojson": "idera:Carga transportada grupo combustibles 2018",
    "red_grupo_granos_2018.geojson": "idera:Carga transportada grupo granos 2018",
    "red_grupo_industrializados_2018.geojson": "idera:Carga transportada grupo industrializados 2018",
    "red_grupo_mineria_2018.geojson": "idera:Carga transportada grupo mineria 2018",
    "red_grupo_regionales_2018.geojson": "idera:Carga transportada grupo regionales 2018",
    "red_semiterminados_2018.geojson": "idera:Carga transportada semiterminados 2018",
}
# movimientos de bovinos entre departamentos (SENASA, publicado por MAGyP), un csv por año en latin-1
SENASA = "https://datos.magyp.gob.ar/dataset/aa0600b2-13f7-45be-8fdf-656262d73005/resource/{id}/download/movimiento-bovinos-{anio}.csv"
SENASA_IDS = {2018: "81330b51-8dd9-420d-842e-aefe56151d3a", 2017: "9cd595bd-c2f4-46a5-993f-3b84f75f1b3f", 2016: "9e1e089c-668d-4614-8289-40aaba1efbfc",
              2015: "463f8b0f-b14c-4bfe-ad7c-6420d0f22a7c", 2014: "d633a49e-4911-4cad-935e-292a3bca4736", 2013: "101241a2-eb59-4d31-aca4-21dc4a0b5c35"}
# volúmenes por estación de servicio (Secretaría de Energía, Res. 1104/04): los recursos se buscan por nombre en el paquete CKAN
EESS_PAQUETE = "http://datos.energia.gob.ar/api/3/action/package_show?id=precios-eess---resolucion-1104-04"
EESS_ANIOS = range(2012, 2026)
# capas de Vialidad Nacional en IDE Transporte: TMDA por tramo, estaciones de conteo y peajes
VIALIDAD = {
    "tmda_2017.geojson": "observ:_3.4.1.4.1.tmda_17_18_view",
    "tmda_2016.geojson": "observ:_3.4.1.4.1.tmda_2016_view",
    "conteo_transito_dnv_2019.geojson": "observ:conteotransito_dnv_19_view",
    "peajes_dnv_2017.geojson": "observ:_3.4.1.6.peajes_dnv_2017.view",
}
# consumo de cemento por provincia (AFCP), una página por mes; el servidor pide un navegador como cliente
AFCP = "http://afcp.info/ESTADISTICAS/DATOS-DEFINITIVOS/{ym}-Provincias/estadistica04.html"
AFCP_UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Safari/537.36", "Accept": "text/html"}
AFCP_DESDE = (2018, 1)


def ca_bundle(destino: Path = DATA_RAW / "ca_bundle.pem") -> Path:
    """Paquete de certificados: los de certifi más los eslabones que el geoserver no manda.

    La cadena del servidor es hoja → Let's Encrypt YR2 → ISRG Root YR (firmada en cruz por ISRG Root X1)
    → ISRG Root X1, que sí está en certifi. Los dos eslabones intermedios están en scripts/certs; no se
    agrega ninguna raíz nueva.
    """
    import certifi

    base = Path(certifi.where()).read_bytes().rstrip(b"\n")
    extras = b"\n".join(p.read_bytes().rstrip(b"\n") for p in sorted(CERT_INTERMEDIA.parent.glob("*.pem")))
    contenido = base + b"\n" + extras + b"\n"
    destino.parent.mkdir(parents=True, exist_ok=True)
    if not destino.exists() or destino.read_bytes() != contenido:
        destino.write_bytes(contenido)
    return destino


def bajar(url: str, destino: Path, timeout: int = 600, verify=True, headers: dict | None = None) -> None:
    if destino.exists() and destino.stat().st_size > 0:
        print(f"  ya está: {destino.name}")
        return
    r = requests.get(url, timeout=timeout, headers=headers or UA, verify=verify)
    r.raise_for_status()
    destino.write_bytes(r.content)
    print(f"  {destino.name}: {len(r.content) / 1e6:.1f} MB")


def eess_resources() -> dict[int, str]:
    """Año -> url del csv de volúmenes por estación, leyendo los nombres 'Precios EESS <año>' y 'Precios EESS desde Diciembre2024' del paquete."""
    r = requests.get(EESS_PAQUETE, timeout=120, headers=UA)
    r.raise_for_status()
    out = {}
    for res in r.json()["result"]["resources"]:
        nombre = res["name"].strip()
        if nombre.startswith("Precios EESS desde"):
            out[2025] = res["url"]
        elif nombre.startswith("Precios EESS ") and len(nombre) == 17 and nombre[13:17].isdigit():
            out[int(nombre[13:17])] = res["url"]
    return out


def afcp(destino: Path = DATA_RAW / "afcp_provincias.csv", desde: tuple[int, int] = AFCP_DESDE, pausa: float = 0.3) -> pd.DataFrame:
    """Recorre los meses desde `desde` hasta hoy, pide solo los que no están en la caché (los 404 no existen) y guarda anio, mes, provincia, t."""
    cache = pd.read_csv(destino) if destino.exists() else pd.DataFrame(columns=["anio", "mes", "provincia", "t"])
    tengo = set(zip(cache["anio"].astype(int), cache["mes"].astype(int))) if len(cache) else set()
    hoy = date.today()
    meses = [(a, m) for a in range(desde[0], hoy.year + 1) for m in range(1, 13) if desde <= (a, m) <= (hoy.year, hoy.month)]
    nuevos, pedidos, faltan = [], 0, 0
    for a, m in meses:
        if (a, m) in tengo:
            continue
        r = requests.get(AFCP.format(ym=f"{a}{m:02d}"), headers=AFCP_UA, timeout=60)
        pedidos += 1
        time.sleep(pausa)
        if r.status_code == 404:
            faltan += 1
            continue
        r.raise_for_status()
        r.encoding = r.apparent_encoding or "windows-1252"
        t = parse_afcp_html(r.text)
        if not t.empty:
            nuevos.append(t)
            tengo |= set(zip(t["anio"].astype(int), t["mes"].astype(int)))
    if nuevos:
        cache = pd.concat([cache, *nuevos], ignore_index=True).drop_duplicates(["anio", "mes", "provincia"]).sort_values(["anio", "mes", "provincia"])
        destino.parent.mkdir(parents=True, exist_ok=True)
        cache.to_csv(destino, index=False)
    meses_ok = cache.groupby("anio")["mes"].nunique().to_dict() if len(cache) else {}
    print(f"  afcp: {pedidos} páginas pedidas, {faltan} sin publicar; meses por año: {meses_ok}")
    return cache


def main() -> None:
    DATA_RAW.mkdir(parents=True, exist_ok=True)
    bundle = str(ca_bundle())
    print("matrices, zonas y drivers:")
    for nombre, url in ARCHIVOS.items():
        bajar(url, DATA_RAW / nombre)
    print("red vial con flujos por sentido:")
    for nombre, capa in CAPAS.items():
        bajar(f"{WFS}?service=WFS&version=1.0.0&request=GetFeature&typeName={quote(capa)}&outputFormat=application/json", DATA_RAW / nombre, verify=bundle)
    print("movimientos de bovinos (SENASA):")
    for anio, rid in sorted(SENASA_IDS.items()):
        bajar(SENASA.format(id=rid, anio=anio), DATA_RAW / f"senasa_movimientos_bovinos_{anio}.csv")
    print("volúmenes por estación de servicio (Res. 1104/04):")
    try:
        recursos = eess_resources()
    except requests.RequestException as e:
        recursos = {}
        print(f"  no pude leer el paquete CKAN: {e}")
    for anio in EESS_ANIOS:
        if anio in recursos:
            bajar(recursos[anio], DATA_RAW / f"eess_{anio}.csv", timeout=1800)
        elif not (DATA_RAW / f"eess_{anio}.csv").exists():
            print(f"  sin recurso para {anio}")
    print("Vialidad Nacional (TMDA, conteos, peajes):")
    for nombre, capa in VIALIDAD.items():
        bajar(f"{WFS_OBSERV}?service=WFS&version=1.0.0&request=GetFeature&typeName={quote(capa)}&maxFeatures=20000&outputFormat=application%2Fjson",
              DATA_RAW / nombre, timeout=1800, verify=bundle)
    print("consumo de cemento por provincia (AFCP):")
    afcp()
    print("listo")


if __name__ == "__main__":
    main()
