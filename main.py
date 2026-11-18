from fastapi import FastAPI, Request, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
import asyncio  # Se usa para el await asyncio.sleep(0)
from fastapi.responses import JSONResponse
from collections import deque
import time
from pydantic import BaseModel, Field
import os
import csv
import numpy as np
import pandas as pd
from datetime import datetime


# ─── Creación de la aplicación FastAPI ──────────────────────────────
app = FastAPI(title="API Proyecto Tiendita", version="1.0.0")


# ─── Constantes para la persistencia en archivos CSV ────────────────
CSV_PRODUCTOS = "productos.csv"
CSV_VENTAS = "ventas.csv"
COLS_PRODUCTOS = ["id", "nombre", "precio", "cantidad"]
COLS_VENTAS = ["id_venta", "fecha", "id_producto", "producto", "precio", "cantidad", "monto"]


# ─── Máximo 5 peticiones por segundo con MIDDLEWARE ASYNCIO ─────────
# NOTA: Middleware comentado temporalmente para permitir las pruebas de concurrencia (Locust) sin interferencia del rate limit.
"""
MAX_PETICIONES = 5
VENTANA = 1.0                     # segundos
peticiones = deque()              # timestamps de las últimas peticiones
lock = asyncio.Lock()             # evita condiciones de carrera

@app.middleware("http")
async def rate_limit(request: Request, call_next):
    async with lock:
        ahora = time.monotonic()
        # Descartamos los timestamps fuera de la ventana de 1 segundo
        while peticiones and ahora - peticiones[0] > VENTANA:
            peticiones.popleft()
        # Si ya hay 5 en el último segundo, rechazamos
        if len(peticiones) >= MAX_PETICIONES:
            return JSONResponse(
                status_code=429,
                content={"detail": "Demasiadas peticiones. Máximo 5 por segundo."}
            )
        peticiones.append(ahora)
    # Si pasa el filtro, seguimos con la petición normal
    return await call_next(request)
"""


# ─── CORS ───────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)


# ─── Lock para operaciones de compra (evita condición de carrera en el stock) ─
lock_stock = asyncio.Lock()


# ─── Modelos Pydantic ───────────────────────────────────────────────
# Estructura obligatoria del cuerpo al crear un producto
class crearProducto(BaseModel):
    nombre: str = Field(..., min_length=1, description="Nombre del producto")
    precio: float = Field(..., gt=0, description="Precio del producto")
    cantidad: int = Field(..., ge=0, description="stock del producto")


# Estructura de la respuesta que devuelve la API al consultar/crear un producto
class respuestaProducto(BaseModel):
    id: int
    nombre: str
    precio: float
    cantidad: int


# ─── Helpers de persistencia CSV  ────────────────────────────
def _asegurar_archivo(ruta, columnas):
    """Crea el archivo CSV con sus encabezados si no existe o está vacío."""
    if (not os.path.exists(ruta)) or os.path.getsize(ruta) == 0:
        with open(ruta, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(columnas)


def _sanitizar_registros(registros):
    """Convierte tipos numpy y valores NaN/Inf a tipos JSON válidos.
    Esto evita que el dashboard desaparezca por culpa de NaN derivados
    de productos eliminados o filas corruptas."""
    def _s(v):
        if v is None:
            return None
        if isinstance(v, (bool, np.bool_)):
            return bool(v)
        if isinstance(v, (int, np.integer)):
            return int(v)
        if isinstance(v, (float, np.floating)):
            fv = float(v)
            return 0.0 if (np.isnan(fv) or np.isinf(fv)) else fv
        if isinstance(v, str):
            return v
        try:
            if pd.isna(v):
                return None
        except Exception:
            pass
        return v
    return [{k: _s(v) for k, v in rec.items()} for rec in registros]


def leer_productos():
    """Lee productos.csv y devuelve una lista de diccionarios limpia."""
    _asegurar_archivo(CSV_PRODUCTOS, COLS_PRODUCTOS)
    try:
        df = pd.read_csv(CSV_PRODUCTOS)
    except pd.errors.EmptyDataError:
        return []
    if df.empty:
        return []
    # Limpieza robusta: descarta filas sin id o sin nombre
    df = df.dropna(subset=["id", "nombre"])
    df["id"] = pd.to_numeric(df["id"], errors="coerce").fillna(0).astype(int)
    df["nombre"] = df["nombre"].astype(str)
    df["precio"] = pd.to_numeric(df["precio"], errors="coerce").fillna(0.0)
    df["cantidad"] = pd.to_numeric(df["cantidad"], errors="coerce").fillna(0).astype(int)
    df = df[df["id"] > 0]
    return _sanitizar_registros(df.to_dict(orient="records"))


def escribir_productos(productos):
    """Reescribe productos.csv completo (para alta/baja de productos)."""
    with open(CSV_PRODUCTOS, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLS_PRODUCTOS)
        w.writeheader()
        for p in productos:
            w.writerow({k: p.get(k, "") for k in COLS_PRODUCTOS})


def agregar_venta(producto, cantidad=1):
    """Registra una venta en ventas.csv calculando el siguiente id_venta."""
    _asegurar_archivo(CSV_VENTAS, COLS_VENTAS)
    try:
        df_v = pd.read_csv(CSV_VENTAS)
        if df_v.empty or "id_venta" not in df_v.columns:
            nuevo_id = 1
        else:
            ids = pd.to_numeric(df_v["id_venta"], errors="coerce").dropna()
            nuevo_id = int(ids.max()) + 1 if not ids.empty else 1
    except Exception:
        nuevo_id = 1
    fila = {
        "id_venta": nuevo_id,
        "fecha": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "id_producto": int(producto["id"]),
        "producto": str(producto["nombre"]),
        "precio": float(producto["precio"]),
        "cantidad": int(cantidad),
        "monto": round(float(producto["precio"]) * int(cantidad), 2),
    }
    with open(CSV_VENTAS, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLS_VENTAS)
        w.writerow(fila)


def leer_ventas_df():
    """Devuelve ventas.csv como DataFrame limpio (o DataFrame vacío)."""
    _asegurar_archivo(CSV_VENTAS, COLS_VENTAS)
    try:
        df = pd.read_csv(CSV_VENTAS)
    except pd.errors.EmptyDataError:
        return pd.DataFrame(columns=COLS_VENTAS)
    if df.empty:
        return pd.DataFrame(columns=COLS_VENTAS)
    # Conversiones numéricas tolerantes a valores corruptos
    for c in ["id_venta", "id_producto", "cantidad"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    for c in ["precio", "monto"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    # Relleno de textos para evitar NaN en agrupaciones
    if "fecha" in df.columns:
        df["fecha"] = df["fecha"].astype(str).replace(
            {"nan": "Desconocida", "None": "Desconocida", "": "Desconocida"}
        )
    if "producto" in df.columns:
        df["producto"] = df["producto"].astype(str).replace(
            {"nan": "Desconocido", "None": "Desconocido", "": "Desconocido"}
        )
    # Descarta filas sin monto válido (no contabilizables)
    df = df.dropna(subset=["monto"])
    return df


# ─── Endpoint raíz ──────────────────────────────────────────────────
@app.get("/")
def home():
    return {"Message": "Hola bienvenido"}


# ─── Endpoint GET /productos (lee productos.csv) ────────────────────
@app.get("/productos")
async def getProductos():
    # Cede el control al event loop
    await asyncio.sleep(0)
    # Devuelve la lista completa leyendo el archivo CSV
    return leer_productos()


# ─── Endpoint POST /productos (crear y persistir en CSV) ────────────
@app.post("/productos", response_model=respuestaProducto, status_code=status.HTTP_201_CREATED)
async def addProducto(producto: crearProducto):
    # Cede el control al event loop
    await asyncio.sleep(0)

    productos = leer_productos()
    # Calcula el nuevo ID como el máximo existente + 1
    nuevo_id = max((p["id"] for p in productos), default=0) + 1

    # Construye el nuevo producto (los campos vienen validados por Pydantic)
    nuevo_producto = {
        "id": nuevo_id,
        "nombre": producto.nombre,
        "precio": float(producto.precio),
        "cantidad": int(producto.cantidad),
    }

    # Agrega el producto y persiste en productos.csv
    productos.append(nuevo_producto)
    escribir_productos(productos)

    # Devuelve el producto recién creado
    return nuevo_producto


# ─── Endpoint DELETE /productos/{producto_id} (persistencia CSV) ────
@app.delete("/productos/{producto_id}")
async def deleteProducto(producto_id: int):
    # Cede el control al event loop (simbólico)
    await asyncio.sleep(0)

    productos = leer_productos()
    # Filtra y reescribe productos.csv sin el registro eliminado
    filtrados = [p for p in productos if int(p["id"]) != producto_id]
    if len(filtrados) == len(productos):
        return {"Message": "No fue encontrado el producto"}

    escribir_productos(filtrados)
    return {"Message": "El producto fue eliminado"}


# ─── Endpoint POST /productos/{producto_id} (comprar) ───────────────
@app.post("/productos/{producto_id}")
async def comprarProducto(producto_id: int):
    # EXPERIMENTO B: Línea restaurada para blindar la API contra condiciones de carrera
    async with lock_stock:
        productos = leer_productos()
        # Busca el producto por ID
        for objeto in productos:
            if int(objeto["id"]) == producto_id:
                # Verifica que haya stock disponible
                if int(objeto["cantidad"]) > 0:
                    await asyncio.sleep(0.05)  # simula el tiempo de procesamiento
                    objeto["cantidad"] = int(objeto["cantidad"]) - 1
                    # Persiste el nuevo stock y registra la venta en ventas.csv
                    escribir_productos(productos)
                    agregar_venta(objeto, 1)
                    return {"Mensaje": "Producto comprado"}
                else:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="No hay stock de ese producto"
                    )

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No existe el ID de ese producto"
        )


# ─── Endpoints analíticos con Pandas (Dashboard) ────────────
@app.get("/dashboard/kpis")
async def dashboard_kpis():
    """KPIs simples del dashboard. Tolera ventas.csv vacío o con NaN."""
    df = leer_ventas_df()
    if df.empty:
        return {
            "producto_mas_comprado": "Sin ventas",
            "unidades_mas_comprado": 0,
            "ingresos_totales": 0.0,
            "total_transacciones": 0,
            "ticket_promedio": 0.0,
        }
    # Producto más comprado por unidades
    try:
        agrupado = df.groupby("producto")["cantidad"].sum().sort_values(ascending=False)
        if agrupado.empty:
            prod_top, unidades_top = "Sin ventas", 0
        else:
            prod_top = str(agrupado.index[0])
            unidades_top = int(agrupado.iloc[0]) if not pd.isna(agrupado.iloc[0]) else 0
    except Exception:
        prod_top, unidades_top = "Sin ventas", 0
    # Ingresos totales y ticket promedio
    ingresos = float(df["monto"].sum(skipna=True))
    if pd.isna(ingresos) or np.isinf(ingresos):
        ingresos = 0.0
    total = int(len(df))
    ticket = (ingresos / total) if total > 0 else 0.0
    return {
        "producto_mas_comprado": prod_top,
        "unidades_mas_comprado": unidades_top,
        "ingresos_totales": round(ingresos, 2),
        "total_transacciones": total,
        "ticket_promedio": round(ticket, 2),
    }


@app.get("/dashboard/ventas-por-producto")
async def dashboard_ventas_por_producto():
    """Serie gráfica #1: ingresos y unidades vendidas agrupadas por producto."""
    df = leer_ventas_df()
    if df.empty:
        return []
    try:
        agg = df.groupby("producto").agg(
            unidades=("cantidad", "sum"),
            ingresos=("monto", "sum"),
        ).reset_index()
    except Exception:
        return []
    # Saneamiento por si aparecen NaN tras agrupaciones
    agg["unidades"] = pd.to_numeric(agg["unidades"], errors="coerce").fillna(0).astype(int)
    agg["ingresos"] = pd.to_numeric(agg["ingresos"], errors="coerce").fillna(0.0)
    agg = agg.sort_values("ingresos", ascending=False)
    return _sanitizar_registros(agg.to_dict(orient="records"))


@app.get("/dashboard/ventas-por-fecha")
async def dashboard_ventas_por_fecha():
    """Serie gráfica #2: evolución diaria de ingresos y transacciones."""
    df = leer_ventas_df()
    if df.empty:
        return []
    df = df.copy()
    df["fecha_dia"] = df["fecha"].astype(str).str.slice(0, 10)
    try:
        agg = df.groupby("fecha_dia").agg(
            ingresos=("monto", "sum"),
            transacciones=("id_venta", "count"),
        ).reset_index()
    except Exception:
        return []
    agg["ingresos"] = pd.to_numeric(agg["ingresos"], errors="coerce").fillna(0.0)
    agg["transacciones"] = pd.to_numeric(agg["transacciones"], errors="coerce").fillna(0).astype(int)
    agg = agg.sort_values("fecha_dia")
    return _sanitizar_registros(agg.to_dict(orient="records"))