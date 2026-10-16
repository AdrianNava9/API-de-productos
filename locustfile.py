from locust import HttpUser, task, between


class TiendaUser(HttpUser):
    """
    Simula un usuario de la tiendita.
    Locust ejecutará las tareas marcadas con @task de forma aleatoria.
  
    """

    # Espera entre 0.5 y 1.5 segundos entre cada tarea
    wait_time = between(0.5, 1.5)

    # Host 
    host = "http://127.0.0.1:8000"

    @task(3)
    def ver_productos(self):
        #Tarea con GET /productos — la tarea más frecuente (peso 3).
        self.client.get("/productos", name="GET /productos")

    @task(1)
    def agregar_producto(self):
        #Tarea con POST /productos — menos frecuente (peso 1).
        nuevo = {
            "nombre": "Producto Locust",
            "precio": 10,
            "cantidad": 5
        }
        self.client.post("/productos", json=nuevo, name="POST /productos")

    @task(1)
    def eliminar_producto(self):
        #Tarea con DELETE /productos/{id} 
        self.client.delete("/productos/1", name="DELETE /productos/{id}")