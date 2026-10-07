from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


app = FastAPI()


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)


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

@app.get("/")
def home():
    return {"Message": "Hola bienvenido"}

@app.get("/productos")
def getProductos():
    return inventario

@app.post("/productos")
def addProducto(producto: dict):

    # Se calcula el id más alto existente y se le suma 1 para evitar ids duplicados cuando se eliminan productos
    nuevo_id = max((p["id"] for p in inventario), default=0) + 1
    nuevo_producto = {
        "id": nuevo_id,
        "nombre": producto["nombre"],
        "precio": producto["precio"],
        "cantidad": producto["cantidad"]
    }

    inventario.append(nuevo_producto)

    return inventario

@app.delete("/productos/{producto_id}")
def deleteProducto(producto_id: int):
    for producto in inventario:
        if producto["id"] == producto_id:
            inventario.remove(producto)
            return {"Message": "El producto fue eliminado"}
    return {"Message": "No fue encontrado el producto"}


