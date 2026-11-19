# ☕ Café Aroma 

Sistema web de tiendita Full Stack con **FastAPI**, persistencia en **archivos CSV**, análisis con **Pandas**, dashboard interactivo con **Chart.js** y backend validado bajo **pruebas de concurrencia con Locust**.


🔗 **Repositorio:** [github.com/AdrianNava9/API-de-productos](https://github.com/AdrianNava9/API-de-productos)

---

## 🎯 ¿Qué hace el sistema?

- **Catálogo de cafetería personalizado** ("Café Aroma") con productos reales, precios y stock inicial definidos en `productos.csv`.
- **CRUD completo del inventario**: crear, listar, eliminar y comprar productos, todo persistido en disco.
- **Registro histórico de ventas** en `ventas.csv`: cada compra guarda fecha, producto, precio, cantidad y monto.
- **Dashboard analítico** con 4 KPIs y 2 gráficas (barras + doughnut) que se actualizan **en vivo** sin recargar la página.
- **API segura contra concurrencia**: las compras pasan por un `asyncio.Lock` que evita vender más unidades de las disponibles bajo carga alta.
- **Pruebas de carga** con Locust para validar el comportamiento del backend con decenas de usuarios simultáneos.
- **Persistencia**: escritura atómica de CSV
- **Identidad visual propia**: paleta café y UI responsiva con Bootstrap 5.

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
│
├── main.py                 # Backend FastAPI: CRUD + dashboard + lock de concurrencia
├── index.html              # Frontend: estructura HTML y estilos (Café Aroma)
├── app.js                  # Frontend: fetch, tabla, KPIs y Chart.js
├── productos.csv           # Catálogo persistente (id, nombre, precio, cantidad)
├── ventas.csv              # Historial persistente de ventas
├── locustfile.py           # Pruebas de carga con Locust
├── README.md               # Este archivo
│
└── .git/                   # Control de versiones (ignorado por GitHub)
```

### 📄 Descripción de cada archivo

- **`main.py`** — Núcleo del backend. Define los endpoints REST, la lógica de persistencia con escritura atómica, la reparación automática de CSV, el `asyncio.Lock` que protege las compras concurrentes, y los endpoints analíticos que devuelven KPIs y series listas para graficar.

- **`index.html`** — Estructura del frontend con la identidad visual "Café Aroma": header con gradiente café, 4 tarjetas KPI, dos `<canvas>` para Chart.js, formulario de registro y tabla del catálogo. Todo responsivo con Bootstrap 5.

- **`app.js`** — Toda la interactividad del cliente: consume la API con `fetch()`, dibuja la tabla del inventario, actualiza los KPIs y renderiza las gráficas de Chart.js destruyendo la instancia previa antes de redibujar (evita fugas de memoria y gráficas superpuestas).

- **`productos.csv`** — Inventario persistente. Columnas: `id, nombre, precio, cantidad`. Se reescribe completo al crear o eliminar productos.

- **`ventas.csv`** — Historial de ventas. Columnas: `id_venta, fecha, id_producto, producto, precio, cantidad, monto`. Solo se anexan filas (nunca se eliminan), y se reescribe con escritura atómica para evitar corrupción.

- **`locustfile.py`** — Script de pruebas de estrés. Simula usuarios concurrentes con diferentes pesos de tarea (comprar, listar, crear) para validar la robustez del backend.

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

### Documentación

- **`docs: README`** — Documentación completa del sistema: stack, endpoints, concurrencia, Locust, estructura y guía de ejecución.


## 🚀 Requisitos y ejecución

### 📋 Requisitos previos

- **Python 3.13** 
- **pip** actualizado (`python -m pip install --upgrade pip`)
- Navegador (Chrome, Firefox, Edge, Safari)
- Puertos libres: **8000** (backend) y **5500** (frontend)


---

### 🐍 Dependencias de Python

El proyecto usa 6 librerías externas, todas declaradas en `requirements.txt`:

| Librería | Versión | Uso |
|---|---|---|
| `fastapi` | 0.141.1 | Framework del backend |
| `uvicorn[standard]` | 0.52.4 | Servidor ASGI |
| `pydantic` | 2.12.4 | Validación de esquemas |
| `pandas` | 2.3.3 | Análisis de CSV y KPIs |
| `numpy` | 2.3.5 | Sanitización de NaN/Inf |
| `locust` | 2.46.7 | Pruebas de carga |

Además se usan módulos de la **biblioteca estándar** de Python (`asyncio`, `os`, `csv`, `datetime`, `collections`), que no requieren instalación.

---

## 🚀 Cómo levantar el proyecto

El sistema tiene **tres servicios independientes**. Cada uno corre en su propia terminal, y los comandos se ejecutan desde la raíz del proyecto:

| Servicio | Puerto | Comando | ¿Cuándo se levanta? |
|---|---|---|---|
| **Backend** (FastAPI) | 8000 | `uvicorn main:app --reload --port 8000` | **Siempre** (obligatorio) |
| **Frontend** (HTML/JS) | 5500 | `python -m http.server 5500` | **Siempre** (obligatorio) |
| **Locust** (pruebas) | 8089 | `locust -f locustfile.py --host=http://127.0.0.1:8000` | **Solo** para pruebas de carga |

> Los servicios 1 y 2 son los únicos necesarios para usar la tienda. Locust es opcional y se levanta únicamente para pruebas de estrés y concurrencia. Finalmente, abre `http://localhost:5500/index.html` en tu navegador 



---


