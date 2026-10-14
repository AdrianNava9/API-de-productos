from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
import asyncio  # Se usa para el await asyncio.sleep(0)
from fastapi.responses import JSONResponse
from collections import deque
import time


# Creación de la aplicación FastAPI
app = FastAPI()

# Máximo 5 peticiones por segundo con MIDDLEWARE ASYNCIO
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


# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

# Datos de ejemplo (inventario en memoria) 
inventario = [
    {"id": 1,  "nombre": "Coca-Cola",   "precio": 20, "cantidad": 25},
    {"id": 2,  "nombre": "Papas",       "precio": 15, "cantidad": 40},
    {"id": 3,  "nombre": "Café",        "precio": 18, "cantidad": 15},
    {"id": 4,  "nombre": "Galletas",    "precio": 12, "cantidad": 30},
    {"id": 5,  "nombre": "Agua 1L",     "precio": 10, "cantidad": 50},
    {"id": 6,  "nombre": "Chocolate",   "precio": 22, "cantidad": 20},
    {"id": 7,  "nombre": "Jugo de naranja", "precio": 25, "cantidad": 8},
    {"id": 8,  "nombre": "Pan blanco",  "precio": 35, "cantidad": 12},
    {"id": 9,  "nombre": "Yogurt",      "precio": 14, "cantidad": 6},
    {"id": 10, "nombre": "Monster",    "precio": 40, "cantidad": 45}
]

# Endpoint raíz
@app.get("/")
def home():
    return {"Message": "Hola bienvenido"}

# Endpoint GET /productos 
@app.get("/productos")
async def getProductos():
    # Cede el control al event loop 
    await asyncio.sleep(0)
    # Devuelve la lista completa del inventario
    return inventario

# Endpoint POST /productos 
@app.post("/productos")
async def addProducto(producto: dict):
    # Cede el control al event loop 
    await asyncio.sleep(0)

    # Calcula el nuevo ID como el máximo existente + 1
    nuevo_id = max((p["id"] for p in inventario), default=0) + 1

    # Construye el nuevo producto
    nuevo_producto = {
        "id": nuevo_id,
        "nombre": producto["nombre"],
        "precio": producto["precio"],
        "cantidad": producto["cantidad"]
    }

    # Agrega el producto al inventario
    inventario.append(nuevo_producto)

    # Devuelve el inventario actualizado
    return inventario

# Endpoint DELETE /productos/{producto_id} 
@app.delete("/productos/{producto_id}")
async def deleteProducto(producto_id: int):
    # Cede el control al event loop (simbólico)
    await asyncio.sleep(0)

    # Busca el producto por ID
    for producto in inventario:
        if producto["id"] == producto_id:
            # Si lo encuentra, lo elimina y responde
            inventario.remove(producto)
            return {"Message": "El producto fue eliminado"}

    # Si no lo encuentra, responde con mensaje de error
    return {"Message": "No fue encontrado el producto"}