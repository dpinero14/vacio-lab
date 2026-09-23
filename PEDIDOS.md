# Pedidos de datos

Tres pedidos para completar lo que el observatorio no puede bajar solo: la
matriz origen-destino posterior a 2018, los viajes de granos de la Carta de
Porte Electrónica y los microdatos de las encuestas en ruta. Los textos están
listos para copiar; hay que completar los datos del remitente.

## 1. CESPA (UBA): matriz origen-destino 2022

Destinatario: dircespa@economicas.uba.ar
Asunto: Matriz origen-destino de cargas 2022 (DT-64)

> Estimados:
>
> Soy [nombre], autor de vacio-lab (https://github.com/dpinero14/vacio-lab), un
> repositorio abierto que mide cuánto del transporte automotor de cargas
> circula sin carga de vuelta, tramo por tramo, a partir de las matrices
> origen-destino publicadas por la Secretaría de Transporte para 2012, 2014,
> 2016 y 2018.
>
> El Documento de Trabajo 64 del CESPA (diciembre de 2024) presenta una matriz
> origen-destino de cargas para 2022 y menciona que está disponible a pedido.
> Les escribo para solicitarla, en el formato en que la tengan (zonas,
> productos, toneladas y viajes), junto con la nota metodológica que describa
> la zonificación y las fuentes.
>
> El uso es de investigación abierta y sin fines comerciales: la matriz se
> compararía con la de 2018 y con la proyección del repositorio, y los
> resultados se publicarían con la cita correspondiente al CESPA. No se
> redistribuiría el archivo original sin su autorización.
>
> Muchas gracias por el trabajo y por la disponibilidad.
>
> [nombre, afiliación si corresponde, correo]

## 2. ARCA: viajes de granos por Carta de Porte Electrónica

Destinatario: SRI@arca.gob.ar (mesa de pedidos de datos de la Subdirección de
Recaudación e Información, según la página de la CPE)
Asunto: Solicitud de datos agregados de Carta de Porte Electrónica de granos

> Estimados:
>
> Solicito, en el marco de la Ley 27.275 de Acceso a la Información Pública,
> un paquete de datos agregados de la Carta de Porte Electrónica de granos
> (RG 5017/2021) con la siguiente estructura, para los años 2022 a 2025:
>
> - período (mes),
> - departamento o partido de origen (código INDEC) y de destino,
> - tipo de grano,
> - medio de transporte (automotor o ferroviario),
> - cantidad de cartas de porte emitidas y toneladas totales.
>
> No se piden datos de personas ni de empresas: solo totales por par de
> departamentos, mes y grano, lo que no permite identificar a ningún emisor.
> Si un par de departamentos tuviera menos de tres emisores, puede
> suprimirse o agregarse al nivel provincial.
>
> El uso es de investigación abierta: el repositorio vacio-lab
> (https://github.com/dpinero14/vacio-lab) mide el vacío del transporte de
> cargas con datos públicos y publica el método y los resultados. Los datos
> reemplazarían la estimación actual de los flujos de granos, que hoy escala
> la matriz origen-destino de 2018 con la producción por departamento.
>
> Formato preferido: CSV. Quedo a disposición para ajustar la estructura del
> pedido a lo que sea posible entregar.
>
> [nombre, DNI, correo, domicilio para notificaciones]

## 3. Secretaría de Transporte: matrices posteriores a 2018 y microdatos

Canal: formulario de acceso a la información pública en
https://www.argentina.gob.ar/aaip/accesoalainformacion/solicitar (Ley 27.275),
dirigido a la Secretaría de Transporte (Dirección de Observatorio, Estudios y
Sistemas, o el área que hoy elabore las matrices origen-destino de cargas).

> Solicito, en el marco de la Ley 27.275:
>
> 1. Las matrices origen-destino de cargas por modo automotor elaboradas o
>    contratadas por la Secretaría con posterioridad a la edición 2018
>    publicada en datos.gob.ar (por ejemplo, ediciones 2020 o 2022), en el
>    mismo formato que las publicadas: zonas de tráfico, productos,
>    toneladas y camiones por año.
> 2. Los microdatos anonimizados de las encuestas origen-destino en ruta
>    que alimentaron la edición 2018 (y las posteriores, si existen): punto
>    de encuesta, fecha, origen y destino declarados a nivel de departamento,
>    producto, tonelaje y si el vehículo circulaba cargado o vacío.
> 3. La asignación de las matrices a la red vial por sentido para las
>    ediciones posteriores a 2018, como la que publica la IDE de Transporte
>    para 2018 (capas "Carga transportada ... 2018").
> 4. Los conteos de tránsito por estación de la Dirección Nacional de
>    Vialidad desde 2017, con la composición por categoría de vehículo, que
>    respaldan los TMDA publicados.
>
> Los datos se usarían en vacio-lab (https://github.com/dpinero14/vacio-lab),
> un repositorio abierto que mide el vacío del transporte de cargas con la
> información pública de la Secretaría y publica el método. Formato
> preferido: los archivos originales (xlsx, csv, shapefile o geojson).
>
> [nombre, DNI, correo]

## Qué hacer cuando lleguen

- CESPA 2022: entra en `scripts/observatorio.py` como matriz publicada de
  2022, al lado de las de 2012 a 2018.
- CPE: reemplaza la graduación de granos por una medición de ambos lados
  (origen y destino) por departamento.
- Encuestas en ruta: son la única fuente directa de camiones vacíos; sirven
  para calibrar la lectura del vacío estructural con viajes reales.
- Conteos de Vialidad por categoría: reemplazan la cuota de pesados supuesta
  en la validación por tramo.
