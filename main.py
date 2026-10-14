from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import asyncio  # Se usa para el await asyncio.sleep(0)

# Creación de la aplicación FastAPI
app = FastAPI()

# Permite peticiones desde cualquier origen (útil para pruebas)
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