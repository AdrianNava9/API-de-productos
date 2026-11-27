# ☕ Café Aroma 

Sistema web de tiendita Full Stack con **FastAPI**, persistencia en **archivos CSV**, análisis con **Pandas**, dashboard interactivo con **Chart.js** y backend validado bajo **pruebas de concurrencia con Locust**.


🔗 **Repositorio:** [github.com/AdrianNava9/API-de-productos](https://github.com/AdrianNava9/API-de-productos)

---

## 🎯 ¿Qué hace el sistema?

- **Catálogo de cafetería personalizado** ("Café Aroma") con productos reales, precios y stock inicial definidos en `productos.csv`.
- **CRUD completo del inventario**: crear, listar, eliminar y comprar productos, todo persistido en disco.
- **Registro transaccional en tiempo real** en `ventas.csv`: cada compra guarda fecha, producto, precio, cantidad y monto total.
- **Big Data con Polars y Parquet**: histórico masivo de **1.5 millones de transacciones** procesado en paralelo (multi-núcleo) desde `ventas.parquet`.
- **Concatenación virtual en consulta**: `ventas.parquet` (histórico) + `ventas.csv` (turno actual) se unen en RAM con `pl.concat()` sin duplicar datos y sin reescribir el parquet durante las compras.
- **Corte de caja automático 24/7**: APScheduler archiva periódicamente el CSV del turno en el parquet y limpia `ventas.csv`, sin detener el servicio.
- **Dashboard analítico** con 4 KPIs y 2 gráficas (barras + doughnut Top 3 + Otros) que se actualizan **en vivo** sin recargar la página.
- **API segura contra concurrencia**: las compras pasan por un `asyncio.Lock` que evita vender más unidades de las disponibles bajo carga alta.
- **Pruebas de carga** con Locust para validar el comportamiento bajo decenas de usuarios simultáneos.
- **Persistencia robusta**: escritura atómica de CSV y sanitización de NaN.
- **Identidad visual propia**: paleta café y UI responsiva con Bootstrap 
---

## 🛠️ Stack tecnológico

| Herramienta | Rol en el proyecto |
|---|---|
| **FastAPI** | Framework del backend REST. Define todos los endpoints del inventario y del dashboard. |
| **Uvicorn** | Servidor ASGI que corre la aplicación FastAPI. |
| **Pydantic v2** | Validación de esquemas en el body de los POST (por ejemplo, al crear un producto). |
| **asyncio.Lock** | Cerrojo asíncrono que serializa las compras y evita race conditions sobre el stock. |
| **Pandas** | Lectura de `ventas.csv`/`productos.csv`, agrupaciones, KPIs y limpieza de datos. |
| **NumPy** | Sanitización de tipos (`np.nan`, `np.inf`) para garantizar JSON válido. |
| **CSV (stdlib)** | Persistencia plana: lectura y escritura de los archivos de datos. |
| **Chart.js 4** | Renderizado de las gráficas del dashboard (barras y doughnut). |
| **Bootstrap 5 + Icons** | Estilos base del frontend, tarjetas, tablas, badges e iconografía. |
| **Locust** | Pruebas de estrés con usuarios concurrentes simulando compras. |
| **Python `http.server`** | Servir el frontend estático localmente. |

---

## 📁 Estructura del repositorio

```text
API-de-productos/
API-de-productos/
│
├── main.py                  # Backend FastAPI: CRUD + dashboard + lock + Polars + APScheduler
├── generar_parquet.py       # Generador masivo de 2M transacciones con NumPy → ventas.parquet
├── index.html               # Frontend: estructura HTML y estilos (Café Aroma)
├── app.js                   # Frontend: fetch, tabla, KPIs y Chart.js
├── productos.csv            # Catálogo persistente (id, nombre, precio, cantidad)
├── ventas.csv               # Turno actual (solo compras recientes, se vacía tras el corte)
├── ventas.parquet           # Histórico masivo columnar (NO versionado, se regenera localmente)
├── locustfile.py            # Pruebas de carga con Locust
├── requirements.txt         # Dependencias con versiones fijas
├── README.md                # Este archivo
└── .gitignore               # Excluye parquet, temporales, __pycache__, backups
```

### 📄 Descripción de cada archivo

- **`main.py`** — Núcleo del backend. Define los endpoints REST (`/productos` y `/api/analisis/*`), la persistencia con escritura atómica (`.tmp` + `os.replace`), el `asyncio.Lock` que serializa compras y corte de caja, los endpoints analíticos con **Polars** (multi-núcleo sobre parquet + csv) y el **scheduler de APScheduler** registrado en el `lifespan` de FastAPI para ejecutar el corte de caja automático cada 5 minutos.

- **`generar_parquet.py`** — Script independiente que genera **2,000,000 transacciones simuladas** con NumPy usando los productos y precios reales de `productos.csv`, y las exporta a `ventas.parquet` con compresión ZSTD. Debe ejecutarse **una sola vez** antes de levantar el backend por primera vez. Incluye `if __name__ == "__main__": main()` para disparar la ejecución al correrlo directamente.

- **`index.html`** — Estructura del frontend con la identidad visual "Café Aroma": header con gradiente café, 4 tarjetas KPI, dos `<canvas>` para Chart.js (barras + doughnut), formulario de registro y tabla del catálogo. Todo responsivo con Bootstrap 5 y las librerías cargadas por CDN.

- **`app.js`** — Interactividad del cliente: consume la API con `fetch()` (endpoints `/api/analisis/*` del Proyecto 4), dibuja la tabla del inventario, actualiza los KPIs y renderiza las gráficas de Chart.js destruyendo la instancia previa antes de redibujar (evita fugas de memoria y gráficas superpuestas). Incluye formato con comas (`toLocaleString("en-US")`) para números grandes en KPIs, tooltips y eje X.

- **`productos.csv`** — Inventario persistente. Columnas: `id, nombre, precio, cantidad`. Se reescribe completo al crear o eliminar productos. Contiene los 9 productos del catálogo "Café Aroma".

- **`ventas.csv`** — Historial del **turno actual**. Columnas: `id_venta, fecha, producto, precio, cantidad, monto_total`. Solo se anexan filas (nunca se eliminan manualmente); el **corte de caja automático** lo vacía periódicamente dejando solo el encabezado listo para el siguiente turno.

- **`ventas.parquet`** — Histórico masivo columnar (2M+ transacciones). **NO se versiona en Git** (supera el límite de GitHub); se regenera localmente con `python generar_parquet.py`. Crece físicamente con cada corte de caja. Es la fuente principal que consulta Polars para el dashboard.

- **`locustfile.py`** — Script de pruebas de estrés con Locust. Simula usuarios concurrentes con tareas ponderadas: comprar (peso 10), consultar raíz (peso 3), listar productos (peso 2) y crear producto (peso 1). Incluye `catch_response=True` para separar `200 OK` de `400 Bad Request` en las estadísticas.

- **`requirements.txt`** — Dependencias de Python con versiones fijas: FastAPI, Uvicorn, Pydantic, Pandas, NumPy, **Polars**, **PyArrow**, **APScheduler** y Locust. Instalación con `pip install -r requirements.txt`.

- **`README.md`** — Este archivo. Documenta el proyecto completo: stack, estructura, endpoints, concurrencia, pruebas de carga, Big Data con Polars, corte de caja, guía de ejecución paso a paso y cobertura de las 4 unidades.

- **`.gitignore`** — Excluye del versionado: `__pycache__/`, `*.parquet` (incluyendo `ventas.parquet`), archivos temporales de escritura atómica (`*.tmp`) y backups de CSV.

## 🧾 Historial de commits

El repositorio tiene un historial de commits descriptivos que documenta la evolución del sistema en tres proyectos o unidades.

### Proyecto/Unidad 1 · API de productos con FastAPI

- **`40065fc` · Initial commit** — Creación del repositorio.
- **`4e15932` · Agrego archivos iniciales** — Primer `main.py`, `index.html` y `app.js` con endpoints `GET /productos` y `POST /productos` sobre un inventario en memoria.
- **`97177d5` · Actualización de app.js, index.html, main.py y se agrega .gitignore** — Primer formulario de registro, tabla de inventario dinámica y exclusión de archivos temporales.

### Proyecto/Unidad 2 · Concurrencia, resolución de condiciones de carrera y pruebas de estrés con Locust

- **`452a648` · T2.2: Refactorización asíncrona, endpoints como funciones async con await** — Conversión de endpoints a `async def`, uso de `asyncio.sleep(0)` para ceder el control al event loop.
- **`43cf796` · T2.1 Extra: Agregar un middleware que limite a 5 peticiones por segundo usando asyncio** — Implementación del rate limiter con `asyncio.Lock` y `collections.deque` (queda comentado en la versión final para no interferir con Locust).
- **`4271694` · T2.2EXTRA: Implementación de Locust** — Primer `locustfile.py` con tareas ponderadas de compra y consulta.
- **`2d99178` · Se agrega opción de compra y manejo de excepciones** — Endpoint `POST /productos/{id}` con validación de stock y `HTTPException` 400.
- **`f006b78` · Preparar entorno para pruebas de concurrencia** — Ajustes de stock, producto crítico (ID 3) y parámetros de Locust.
- **`89e3105` · Actualización locustfile.py** — Pesos definitivos de tareas, `catch_response=True` y separación de 200 vs 400 en estadísticas.
- **`b66003a` · Experimento A: API vulnerable con lock comentado** — Evidencia del race condition (stock negativo) al retirar `async with lock_stock`.
- **`02cc549` · Restaurar versión API blindada - Versión final del proyecto 2** — Reactivación de `asyncio.Lock` para proteger el stock y dejar la API estable ante concurrencia.

### Proyecto/Unidad 3 · Persistencia CSV y dashboard analítico

- **`b4b8f2f` · Proyecto 3: Implementación de endpoints analíticos con pandas, dashboard con chart.js, persistencia con CSV y actualización del diseño y paleta de colores** — Migración a persistencia en archivos `productos.csv` y `ventas.csv`; endpoints analíticos con Pandas (`/dashboard/kpis`, `/dashboard/ventas-por-producto`, `/dashboard/ventas-por-fecha`); dashboard con KPIs y gráficas Chart.js (barras + doughnut Top 3 + Otros); escritura atómica y reparación automática de CSV; rediseño visual "Café Aroma".

- **`9977290` · Actualizar .gitignore; agregar requirements.txt y documentación con README.md** — 

### Proyecto/Unidad 4 · Big Data con Polars, Parquet y Corte de Caja 24/7

- **`9315b94` · Proyecto 4: Escalar el backend para soportar millones de transacciones históricas con Polars, Parquet y Corte de Caja con APScheduler** — Generación de 2M registros con NumPy en `generar_parquet.py`; migración de los endpoints analíticos a **Polars** (`pl.scan_parquet` + `pl.scan_csv` + `pl.concat`); nuevos endpoints `/api/analisis/*`; `APScheduler` para corte de caja automático con `AsyncIOScheduler` en el `lifespan` de FastAPI; `asyncio.Lock` extendido para proteger la fusión de CSV → Parquet; contador global de `id_venta` persistente entre cortes; frontend actualizado a los nuevos endpoints con formato de comas para números grandes.



## 🚀 Requisitos y ejecución

### 📋 Requisitos previos

- **Python 3.13** 
- **pip** actualizado (`python -m pip install --upgrade pip`)
- Navegador (Chrome, Firefox, Edge, Safari)
- Puertos libres: **8000** (backend) y **5500** (frontend)


---

### 🐍 Dependencias de Python

El proyecto declara sus dependencias en `requirements.txt`:

| Librería | Versión | Uso |
|---|---|---|
| `fastapi` | 0.141.1 | Framework del backend |
| `uvicorn[standard]` | 0.52.4 | Servidor ASGI |
| `pydantic` | 2.12.4 | Validación de esquemas |
| `pandas` | 2.3.3 | Inventario (`productos.csv`) y limpieza de CSV |
| `numpy` | 2.3.5 | Generación masiva de 2M registros y sanitización de NaN/Inf |
| `polars` | 2.2.0 | Procesamiento multi-núcleo de `ventas.parquet` + `ventas.csv` |
| `pyarrow` |21.0.0 | Backend del formato Parquet |
| `apscheduler` | 3.11.3 | Corte de caja automático 24/7 |
| `locust` | 2.46.7 | Pruebas de carga con usuarios concurrentes |

Además se usan módulos de la **biblioteca estándar** de Python (`asyncio`, `os`, `csv`, `datetime`, `collections`, `contextlib`), que **no requieren instalación**.

---

## 🚀 Cómo levantar el proyecto

El sistema tiene **un paso previo** y **tres servicios independientes**. Cada uno corre en su propia terminal, y los comandos se ejecutan desde la raiz del proyecto:

| Paso/Servicio | Puerto | Comando | ¿Cuándo se ejecuta? |
|---|---|---|---|
| **Generador** (NumPy → Parquet) | — | `python generar_parquet.py` | **Solo la primera vez** |
| **Backend** (FastAPI) | 8000 | `uvicorn main:app --reload --port 8000` | **Siempre** |
| **Frontend** (HTML/JS) | 5500 | `python -m http.server 5500` | **Siempre** |
| **Locust** (pruebas) | 8089 | `locust -f locustfile.py --host=http://127.0.0.1:8000` | **Opcional** |

> Los servicios 2 y 3 son los únicos necesarios para usar la tienda. Locust es opcional y se levanta únicamente para pruebas de estrés. Finalmente, abre `http://localhost:5500/index.html` en tu navegador 



---


