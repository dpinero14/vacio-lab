# Datos

Nada de esta carpeta se versiona. `python scripts/download_data.py` baja todo a
`data/raw/` (cerca de 1,5 GB con las fuentes del observatorio) y los notebooks y
`scripts/observatorio.py` dejan intermedios en `data/processed/`.

| Archivo | Fuente | Licencia | Qué es |
|---|---|---|---|
| `mtx-2018.zip`, `mtx-2016.zip`, `mtx-2014.zip`, `mtx-2012.zip` | Secretaría de Transporte, dataset `matriz-od-vial-cargas` | datos.gob.ar | Matrices origen-destino entre 123 zonas de tráfico, en toneladas y en camiones, un xlsx por grupo de producto y una hoja por producto (113 productos en 8 grupos en 2018) |
| `codigos_zonas.xls` | ídem | datos.gob.ar | Código, nombre y provincia de las 123 zonas |
| `zonificacion.jpg` | ídem | datos.gob.ar | Mapa de las zonas, solo como referencia visual |
| `metodologia_od_2018.pdf` | ídem | datos.gob.ar | Informe metodológico de la edición 2018: fuentes por grupo, zonificación y asignación a la red |
| `red_total_2018.geojson` y `red_grupo_*_2018.geojson` | IDE Transporte, capas `idera:Carga transportada ... 2018` por WFS | datos.gob.ar | Red vial simplificada de 1.731 tramos con el flujo de camiones asignado por sentido (`ab_flow`, `ba_flow`), el total y una capa por grupo, más el estado del pavimento |
| `magyp_estimaciones_agricolas.csv` | Ministerio de Agricultura, estimaciones agrícolas | datos.gob.ar | Superficie y producción por cultivo, campaña y departamento; driver de granos y, por departamento, origen medido de cada grano |
| `fractura_adjunto_iv.csv` | Secretaría de Energía, registro de fractura (Adjunto IV) | datos.gob.ar | Arena bombeada por pozo y fecha; la arena de fractura que la matriz no ve |
| `senasa_movimientos_bovinos_<año>.csv` (2013 a 2018) | SENASA, publicado por MAGyP (`movimiento-bovinos`) | datos.gob.ar | Cabezas movidas por mes entre departamento de origen y de destino, por categoría (vaca, novillo, ternero...); latin-1. Mide las dos puntas del ganado en pie |
| `eess_<año>.csv` (2012 a 2025) | Secretaría de Energía, Res. 1104/04 (`precios-eess---resolucion-1104-04`) | datos.gob.ar | Precio y volumen vendido por estación de servicio, producto y mes; el archivo 2025 cubre desde diciembre de 2024. Mide el destino de gasoil y nafta; 45 a 130 MB por año |
| `afcp_provincias.csv` | AFCP, estadísticas mensuales de consumo por provincia (páginas HTML) | uso público, sin licencia explícita | Toneladas de cemento consumidas por provincia y mes (total del mes), armado por el script página por página desde 2021 (los meses anteriores no están publicados). Mide el destino del cemento |
| `georef_departamentos.json` | API georef (datos.gob.ar) | datos.gob.ar | Los 529 departamentos con centroide y provincia, para llevar cada fuente a las zonas |
| `georef_localidades.json` | API georef, consultas por lote | datos.gob.ar | Caché de la geocodificación de las localidades de las estaciones de servicio (centroide y departamento) |
| `tmda_2017.geojson`, `tmda_2016.geojson` | Vialidad Nacional vía IDE Transporte (`observ:_3.4.1.4.1.tmda_17_18_view`, `..._2016_view`) | datos.gob.ar | Tránsito medio diario anual por tramo de ruta nacional, todos los vehículos, los dos sentidos; para validar la asignación |
| `conteo_transito_dnv_2019.geojson` | Vialidad Nacional vía IDE Transporte (`observ:conteotransito_dnv_19_view`) | datos.gob.ar | Las 603 estaciones de conteo de 2019, con ruta y progresiva |
| `peajes_dnv_2017.geojson` | Vialidad Nacional vía IDE Transporte (`observ:_3.4.1.6.peajes_dnv_2017.view`) | datos.gob.ar | Las 78 plazas de peaje de 2017 |
| `ca_bundle.pem` | certifi más `scripts/certs/lets-encrypt-yr2.pem` | MPL 2.0 / público | Paquete de certificados para el geoserver de IDE Transporte, que no envía su intermedio |
| `series_api.json` | API de series de tiempo (datos.gob.ar) | datos.gob.ar | Caché de los drivers nacionales (ventas de combustibles, cemento, IPI, ISAC, automotriz) |

Descarga verificada el 23 de septiembre de 2026. La zonificación son grupos de
departamentos o partidos; los flujos de la red son camiones por año por sentido,
según el informe metodológico. Las fuentes del observatorio se llevan a las
zonas con `vlab.zoning`: el departamento a la zona más cercana dentro de su
provincia, la localidad a través de su departamento, la provincia repartida
entre sus zonas.
