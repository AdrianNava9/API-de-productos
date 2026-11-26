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
# ─── NUEVAS IMPORTACIONES Proyecto 4: Polars + APScheduler ──────────
import polars as pl
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from contextlib import asynccontextmanager


# ─── Constantes para la persistencia en archivos CSV ────────────────
CSV_PRODUCTOS = "productos.csv"
CSV_VENTAS = "ventas.csv"
PARQUET_VENTAS = "ventas.parquet"   # NUEVO: histórico masivo columnar
COLS_PRODUCTOS = ["id", "nombre", "precio", "cantidad"]
# ─── NUEVO: esquema unificado CSV + Parquet (Proyecto 4) ────────────
COLS_VENTAS = ["id_venta", "fecha", "producto", "precio", "cantidad", "monto_total"]

# ─── NUEVO: intervalo del corte de caja automático (minutos) ────────
CORTE_CAJA_INTERVALO_MIN = 5


# ─── Lock para operaciones de compra (evita condición de carrera en el stock) ─
lock_stock = asyncio.Lock()

# ─── NUEVO: Scheduler de APScheduler para corte de caja 24/7 ────────
scheduler = AsyncIOScheduler()

# ─── NUEVO: contador global de id_venta (continúa tras el corte) ────
_id_venta_counter = {"value": 0}


# ─── NUEVO: Helpers de Polars + Corte de Caja ───────────────────────
def _init_id_venta_counter():
    """Inicializa el contador global al máximo id_venta visto en
    parquet + csv. Evita que los IDs se reinicien tras cada corte."""
    max_parquet = 0
    max_csv = 0
    if os.path.exists(PARQUET_VENTAS) and os.path.getsize(PARQUET_VENTAS) > 0:
        try:
            df = pl.read_parquet(PARQUET_VENTAS, columns=["id_venta"])
            if df.height > 0:
                v = df["id_venta"].max()
                max_parquet = int(v) if v is not None else 0
        except Exception as e:
            print(f"[INIT] Error leyendo parquet: {e}")
    if os.path.exists(CSV_VENTAS) and os.path.getsize(CSV_VENTAS) > 60:
        try:
            df = pl.read_csv(CSV_VENTAS, infer_schema_length=100)
            if df.height > 0 and "id_venta" in df.columns:
                v = df["id_venta"].cast(pl.Int64, strict=False).max()
                max_csv = int(v) if v is not None else 0
        except Exception as e:
            print(f"[INIT] Error leyendo csv: {e}")
    _id_venta_counter["value"] = max(max_parquet, max_csv)
    print(f"[INIT] Contador id_venta inicializado en {_id_venta_counter['value']}")


def leer_ventas_polars():
    """Concatena virtualmente ventas.parquet + ventas.csv usando Polars.
    Aplica pl.scan_parquet() + pl.scan_csv() + pl.concat() en modo lazy.
    Retorna un LazyFrame con el esquema normalizado COLS_VENTAS."""
    _asegurar_archivo(CSV_VENTAS, COLS_VENTAS)
    schema_vacio = {
        "id_venta": pl.Int64,
        "fecha": pl.Utf8,
        "producto": pl.Utf8,
        "precio": pl.Float64,
        "cantidad": pl.Int64,
        "monto_total": pl.Float64,
    }

    lf_parquet = None
    lf_csv = None

    # ─── 1) Parquet histórico (columnar, multi-núcleo) ───
    if os.path.exists(PARQUET_VENTAS) and os.path.getsize(PARQUET_VENTAS) > 0:
        try:
            lf_parquet = pl.scan_parquet(PARQUET_VENTAS)
            cols = lf_parquet.collect_schema().names()
            # Normalizar por si el parquet viene con esquema antiguo
            if "monto" in cols and "monto_total" not in cols:
                lf_parquet = lf_parquet.rename({"monto": "monto_total"})
            if "id_producto" in cols:
                lf_parquet = lf_parquet.drop("id_producto")
            cols = lf_parquet.collect_schema().names()
            for c in COLS_VENTAS:
                if c not in cols:
                    lf_parquet = lf_parquet.with_columns(pl.lit(None).alias(c))
            lf_parquet = lf_parquet.select([
                pl.col("id_venta").cast(pl.Int64, strict=False),
                pl.col("fecha").cast(pl.Utf8, strict=False),
                pl.col("producto").cast(pl.Utf8, strict=False),
                pl.col("precio").cast(pl.Float64, strict=False),
                pl.col("cantidad").cast(pl.Int64, strict=False),
                pl.col("monto_total").cast(pl.Float64, strict=False),
            ])
        except Exception as e:
            print(f"[POLARS] Error scan_parquet: {e}")
            lf_parquet = None

    # ─── 2) CSV del turno actual (append-only) ───
    if os.path.exists(CSV_VENTAS) and os.path.getsize(CSV_VENTAS) > 60:
        try:
            lf_csv = pl.scan_csv(CSV_VENTAS, infer_schema_length=1000)
            cols = lf_csv.collect_schema().names()
            if "monto" in cols and "monto_total" not in cols:
                lf_csv = lf_csv.rename({"monto": "monto_total"})
            if "id_producto" in cols:
                lf_csv = lf_csv.drop("id_producto")
            cols = lf_csv.collect_schema().names()
            for c in COLS_VENTAS:
                if c not in cols:
                    lf_csv = lf_csv.with_columns(pl.lit(None).alias(c))
            lf_csv = lf_csv.select([
                pl.col("id_venta").cast(pl.Int64, strict=False),
                pl.col("fecha").cast(pl.Utf8, strict=False),
                pl.col("producto").cast(pl.Utf8, strict=False),
                pl.col("precio").cast(pl.Float64, strict=False),
                pl.col("cantidad").cast(pl.Int64, strict=False),
                pl.col("monto_total").cast(pl.Float64, strict=False),
            ])
        except Exception as e:
            print(f"[POLARS] Error scan_csv: {e}")
            lf_csv = None

    # ─── 3) Unión virtual: CERO duplicados, todo en RAM ───
    if lf_parquet is not None and lf_csv is not None:
        return pl.concat([lf_parquet, lf_csv], how="vertical_relaxed")
    if lf_parquet is not None:
        return lf_parquet
    if lf_csv is not None:
        return lf_csv
    return pl.LazyFrame(schema=schema_vacio)


async def corte_caja_auto():
    """Tarea automática 24/7:
       1. Lee ventas.csv del turno actual (bajo lock).
       2. Fusiona físicamente con ventas.parquet en disco.
       3. Vacía ventas.csv dejando solo la fila de encabezados.
    """
    async with lock_stock:
        try:
            if not os.path.exists(CSV_VENTAS):
                return
            if os.path.getsize(CSV_VENTAS) <= 60:
                print("[CORTE] ventas.csv vacío, nada que archivar")
                return
            df_csv = pl.read_csv(CSV_VENTAS, infer_schema_length=1000)
            if df_csv.height == 0:
                print("[CORTE] CSV sin filas")
                return

            # Normalizar esquema del CSV
            if "monto" in df_csv.columns and "monto_total" not in df_csv.columns:
                df_csv = df_csv.rename({"monto": "monto_total"})
            if "id_producto" in df_csv.columns:
                df_csv = df_csv.drop("id_producto")
            for c in COLS_VENTAS:
                if c not in df_csv.columns:
                    df_csv = df_csv.with_columns(pl.lit(None).alias(c))
            df_csv = df_csv.select(COLS_VENTAS)

            # Leer parquet existente (si lo hay)
            df_parquet = None
            if os.path.exists(PARQUET_VENTAS) and os.path.getsize(PARQUET_VENTAS) > 0:
                try:
                    df_parquet = pl.read_parquet(PARQUET_VENTAS)
                    if "monto" in df_parquet.columns and "monto_total" not in df_parquet.columns:
                        df_parquet = df_parquet.rename({"monto": "monto_total"})
                    if "id_producto" in df_parquet.columns:
                        df_parquet = df_parquet.drop("id_producto")
                    for c in COLS_VENTAS:
                        if c not in df_parquet.columns:
                            df_parquet = df_parquet.with_columns(pl.lit(None).alias(c))
                    df_parquet = df_parquet.select(COLS_VENTAS)
                except Exception as e:
                    print(f"[CORTE] Error leyendo parquet existente: {e}")

            # Fusión física
            df_total = pl.concat([df_parquet, df_csv], how="vertical_relaxed") if df_parquet is not None else df_csv

            # Escritura atómica del parquet (.tmp + os.replace)
            tmp = PARQUET_VENTAS + ".tmp"
            df_total.write_parquet(tmp, compression="zstd")
            os.replace(tmp, PARQUET_VENTAS)
            print(f"[CORTE] {df_csv.height} ventas archivadas, total parquet: {df_total.height}")

            # Vaciar CSV (solo encabezados, listo para el siguiente turno)
            with open(CSV_VENTAS, "w", encoding="utf-8", newline="") as f:
                f.write(",".join(COLS_VENTAS) + "\n")
            print("[CORTE] ventas.csv limpiado")
        except Exception as e:
            print(f"[CORTE] Error: {e}")
            import traceback
            traceback.print_exc()


@asynccontextmanager
async def lifespan(app):
    """Ciclo de vida FastAPI: arranca y detiene APScheduler."""
    _init_id_venta_counter()
    scheduler.add_job(
        corte_caja_auto,
        trigger="interval",
        minutes=CORTE_CAJA_INTERVALO_MIN,
        id="corte_caja_automatico",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    scheduler.start()
    print(f"[SCHEDULER] Corte de caja cada {CORTE_CAJA_INTERVALO_MIN} min")
    try:
        yield
    finally:
        scheduler.shutdown(wait=False)
        print("[SCHEDULER] Detenido")


# ─── Creación de la aplicación FastAPI con lifespan ─────────────────
app = FastAPI(title="API Proyecto Tiendita", version="2.0.0", lifespan=lifespan)


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


# ─── Modelos Pydantic ───────────────────────────────────────────────
class crearProducto(BaseModel):
    nombre: str = Field(..., min_length=1, description="Nombre del producto")
    precio: float = Field(..., gt=0, description="Precio del producto")
    cantidad: int = Field(..., ge=0, description="stock del producto")


class respuestaProducto(BaseModel):
    id: int
    nombre: str
    precio: float
    cantidad: int


# ─── Helpers de persistencia CSV ────────────────────────────────────
def _asegurar_archivo(ruta, columnas):
    """Crea el archivo CSV con sus encabezados si no existe o está vacío."""
    if (not os.path.exists(ruta)) or os.path.getsize(ruta) == 0:
        with open(ruta, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f, lineterminator="\n")
            w.writerow(columnas)


def _asegurar_newline_final(ruta):
    """Asegura que el archivo termine en \\n antes de hacer append.
    Evita que la nueva fila quede pegada al último valor del archivo."""
    if not os.path.exists(ruta) or os.path.getsize(ruta) == 0:
        return
    with open(ruta, "rb") as f:
        f.seek(-1, 2)
        ultimo = f.read(1)
    if ultimo not in (b"\n", b"\r"):
        with open(ruta, "ab") as f:
            f.write(b"\n")


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
    """Registra una venta en ventas.csv.
    MODIFICADA en Proyecto 4: usa contador global para id_venta y
    nuevo esquema (monto_total, sin id_producto)."""
    _asegurar_archivo(CSV_VENTAS, COLS_VENTAS)
    _asegurar_newline_final(CSV_VENTAS)

    # ─── Uso del contador global (evita relecturas de CSV) ───
    _id_venta_counter["value"] += 1
    nuevo_id = _id_venta_counter["value"]

    fila = {
        "id_venta": nuevo_id,
        "fecha": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "producto": str(producto["nombre"]),
        "precio": float(producto["precio"]),
        "cantidad": int(cantidad),
        "monto_total": round(float(producto["precio"]) * int(cantidad), 2),
    }
    with open(CSV_VENTAS, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLS_VENTAS, lineterminator="\n")
        w.writerow(fila)


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


# ─── NUEVOS endpoints analíticos con Polars (Proyecto 4) ────────────
@app.get("/api/analisis/kpis")
async def api_analisis_kpis():
    """KPIs del dashboard procesados con Polars (parquet + csv concatenados
    virtualmente). Sin duplicados y con multi-núcleo."""
    vacio = {
        "producto_mas_comprado": "Sin ventas",
        "unidades_mas_comprado": 0,
        "ingresos_totales": 0.0,
        "total_transacciones": 0,
        "ticket_promedio": 0.0,
    }
    try:
        df = leer_ventas_polars().collect()
    except Exception as e:
        print(f"[KPIS] Error collect: {e}")
        return vacio
    if df.height == 0:
        return vacio
    try:
        agg = (
            df.group_by("producto")
            .agg([
                pl.col("cantidad").sum().alias("unidades"),
                pl.col("monto_total").sum().alias("ingresos"),
            ])
            .sort("unidades", descending=True)
        )
        if agg.height > 0:
            top = agg.row(0, named=True)
            prod_top = str(top.get("producto") or "Sin ventas")
            u = top.get("unidades")
            unidades_top = int(u) if u is not None else 0
        else:
            prod_top, unidades_top = "Sin ventas", 0

        ing_val = df["monto_total"].sum()
        ingresos = float(ing_val) if ing_val is not None else 0.0
        if ingresos != ingresos or ingresos in (float("inf"), float("-inf")):
            ingresos = 0.0
        total = int(df.height)
        ticket = (ingresos / total) if total > 0 else 0.0

        return {
            "producto_mas_comprado": prod_top,
            "unidades_mas_comprado": unidades_top,
            "ingresos_totales": round(ingresos, 2),
            "total_transacciones": total,
            "ticket_promedio": round(ticket, 2),
        }
    except Exception as e:
        print(f"[KPIS] Error agregando: {e}")
        import traceback; traceback.print_exc()
        return vacio


@app.get("/api/analisis/mas-vendidos")
async def api_analisis_mas_vendidos():
    """Serie: ingresos y unidades por producto con Polars."""
    try:
        df = leer_ventas_polars().collect()
    except Exception as e:
        print(f"[MAS-VENDIDOS] Error collect: {e}")
        return []
    if df.height == 0:
        return []
    try:
        agg = (
            df.group_by("producto")
            .agg([
                pl.col("cantidad").sum().alias("unidades"),
                pl.col("monto_total").sum().alias("ingresos"),
            ])
            .sort("ingresos", descending=True)
        )
        resultado = []
        for r in agg.to_dicts():
            u = r.get("unidades")
            i = r.get("ingresos")
            resultado.append({
                "producto": str(r.get("producto") or "Desconocido"),
                "unidades": int(u) if u is not None else 0,
                "ingresos": round(float(i) if i is not None else 0.0, 2),
            })
        return resultado
    except Exception as e:
        print(f"[MAS-VENDIDOS] Error agregando: {e}")
        import traceback; traceback.print_exc()
        return []


@app.get("/api/analisis/ventas-por-fecha")
async def api_analisis_ventas_por_fecha():
    """Serie por fecha (mantenida por compatibilidad, no usada por frontend)."""
    try:
        df = leer_ventas_polars().collect()
    except Exception:
        return []
    if df.height == 0:
        return []
    try:
        agg = (
            df.with_columns(pl.col("fecha").str.slice(0, 10).alias("fecha_dia"))
            .group_by("fecha_dia")
            .agg([
                pl.col("monto_total").sum().alias("ingresos"),
                pl.col("id_venta").count().alias("transacciones"),
            ])
            .sort("fecha_dia")
        )
        return [
            {
                "fecha_dia": str(r.get("fecha_dia") or "Desconocida"),
                "ingresos": round(float(r.get("ingresos") or 0.0), 2),
                "transacciones": int(r.get("transacciones") or 0),
            }
            for r in agg.to_dicts()
        ]
    except Exception:
        return []


# ─── Alias legacy (backwards compatibilidad con clientes viejos) ────
@app.get("/dashboard/kpis")
async def dashboard_kpis_legacy():
    return await api_analisis_kpis()


@app.get("/dashboard/ventas-por-producto")
async def dashboard_ventas_por_producto_legacy():
    return await api_analisis_mas_vendidos()


@app.get("/dashboard/ventas-por-fecha")
async def dashboard_ventas_por_fecha_legacy():
    return await api_analisis_ventas_por_fecha()