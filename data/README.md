# Datos

Nada de esta carpeta se versiona. `python scripts/download_data.py` baja todo a
`data/raw/` (unos 215 MB) y el notebook deja intermedios en `data/processed/`.

| Archivo | Fuente | Licencia | Qué es |
|---|---|---|---|
| `mtx-2018.zip`, `mtx-2016.zip`, `mtx-2014.zip`, `mtx-2012.zip` | Secretaría de Transporte, dataset `matriz-od-vial-cargas` | datos.gob.ar | Matrices origen-destino entre 123 zonas de tráfico, en toneladas y en camiones, un xlsx por grupo de producto y una hoja por producto (113 productos en 8 grupos en 2018) |
| `codigos_zonas.xls` | ídem | datos.gob.ar | Código, nombre y provincia de las 123 zonas |
| `zonificacion.jpg` | ídem | datos.gob.ar | Mapa de las zonas, solo como referencia visual |
| `metodologia_od_2018.pdf` | ídem | datos.gob.ar | Informe metodológico de la edición 2018: fuentes por grupo, zonificación y asignación a la red |
| `red_total_2018.geojson` y `red_grupo_*_2018.geojson` | IDE Transporte, capas `idera:Carga transportada ... 2018` por WFS | datos.gob.ar | Red vial simplificada de 1.731 tramos con el flujo de camiones asignado por sentido (`ab_flow`, `ba_flow`), el total y una capa por grupo, más el estado del pavimento |

Descarga verificada el 22 de septiembre de 2026. La zonificación son grupos de
departamentos o partidos; los flujos de la red son camiones por año por sentido,
según el informe metodológico.
