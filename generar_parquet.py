"""
Script de generación masiva de datos para el Proyecto 4.
Genera entre 1 y 2 millones de transacciones simuladas con NumPy y las
exporta a ventas.parquet (formato columnar comprimido con ZSTD).

Uso:
    python generar_parquet.py
    python generar_parquet.py --registros 2000000

Debe ejecutarse ANTES de arrancar uvicorn la primera vez.
"""
import argparse
import csv
import os
from datetime import datetime

import numpy as np
import polars as pl


CSV_PRODUCTOS = "productos.csv"
PARQUET_VENTAS = "ventas.parquet"

# ─── Esquema idéntico a ventas.csv según especificación Proyecto 4 ──
COLUMNS = ["id_venta", "fecha", "producto", "precio", "cantidad", "monto_total"]

REGISTROS_DEFAULT = 2_000_000  # Entre 1M y 2M


def leer_catalogo(ruta=CSV_PRODUCTOS):
    """Lee productos.csv y devuelve nombres + precios como arrays numpy."""
    if not os.path.exists(ruta):
        raise FileNotFoundError(f"No existe {ruta}. Ejecuta este script desde la raíz del proyecto.")
    nombres, precios = [], []
    with open(ruta, encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            try:
                nombres.append(str(row["nombre"]).strip())
                precios.append(float(row["precio"]))
            except (KeyError, ValueError, TypeError):
                continue
    if not nombres:
        raise ValueError("El catálogo productos.csv está vacío o mal formado")
    return nombres, np.array(precios, dtype=np.float64)


def generar_dataframe(nombres, precios, n_registros):
    """Genera un DataFrame de Polars con n_registros filas usando NumPy."""
    rng = np.random.default_rng(seed=42)
    n_prod = len(nombres)

    # 1) Selección aleatoria de producto por transacción
    idx = rng.integers(0, n_prod, size=n_registros, dtype=np.int64)

    # 2) Cantidad entre 1 y 5 unidades
    cantidades = rng.integers(1, 6, size=n_registros, dtype=np.int64)

    # 3) Precios unitarios y montos totales
    precios_unit = precios[idx]
    montos = np.round(precios_unit * cantidades, 2).astype(np.float64)

    # 4) IDs incrementales
    ids = np.arange(1, n_registros + 1, dtype=np.int64)

    # 5) Fechas distribuidas en los últimos 365 días (vectorizado)
    base_ts = np.datetime64("2025-01-01T00:00:00")
    offsets = rng.integers(0, 365 * 24 * 3600, size=n_registros).astype("timedelta64[s]")
    fechas_dt = base_ts + offsets
    # Convertir a string "YYYY-MM-DD HH:MM:SS" (mismo formato que ventas.csv)
    fechas_str = np.datetime_as_string(fechas_dt, unit="s")
    fechas_str = np.char.replace(fechas_str, "T", " ")

    # 6) Nombres de producto (vectorizado con índices)
    nombres_np = np.array(nombres, dtype=object)
    productos = nombres_np[idx]

    # 7) Construir DataFrame de Polars
    return pl.DataFrame({
        "id_venta": ids,
        "fecha": fechas_str,
        "producto": productos.astype(str),
        "precio": precios_unit.astype(np.float64),
        "cantidad": cantidades,
        "monto_total": montos,
    })


def main():
    parser = argparse.ArgumentParser(description="Genera ventas.parquet masivo para Proyecto 4")
    parser.add_argument(
        "--registros", type=int, default=REGISTROS_DEFAULT,
        help=f"Cantidad de registros a generar (default: {REGISTROS_DEFAULT:,})"
    )
    args = parser.parse_args()

    print(f"[1/3] Leyendo catálogo desde {CSV_PRODUCTOS}...")
    nombres, precios = leer_catalogo()
    print(f"      Productos encontrados: {len(nombres)}")

    print(f"[2/3] Generando {args.registros:,} registros con NumPy...")
    df = generar_dataframe(nombres, precios, args.registros)
    print(f"      DataFrame: {df.height:,} filas x {df.width} columnas")
    print(f"      Esquema: {df.schema}")

    print(f"[3/3] Exportando a {PARQUET_VENTAS} (columnar, compresión ZSTD)...")
    df.write_parquet(PARQUET_VENTAS, compression="zstd")
    tamano_mb = os.path.getsize(PARQUET_VENTAS) / (1024 * 1024)
    print(f"      ✓ {PARQUET_VENTAS} generado ({tamano_mb:.2f} MB)")
    print("\nListo. Ahora puedes levantar el backend con:")
    print("  uvicorn main:app --reload --port 8000")

# Se necesita llamar a main.py
if __name__ == "__main__":
    main()