from locust import HttpUser, task, between


class UsuarioTienditaCompleto(HttpUser):
    """
    Simula un usuario de la tiendita.
    Locust ejecutará las tareas marcadas con @task de forma aleatoria.
    """
    # Intervalo aleatorio de descanso entre 0.2s y 0.8s por usuario (Según PDF)
    wait_time = between(0.2, 0.8)

    # Host por defecto
    host = "http://127.0.0.1:8000"

    @task(10)
    def comprarProducto(self):
        """
        Tarea prioritaria (peso 10): POST /productos/3
        catch_response=True evita registrar el agotamiento de stock (400)
        como una falla del sistema.
        """
        with self.client.post("/productos/3", catch_response=True, name="POST /productos/3 (Comprar)") as response:
            if response.status_code == 200:
                response.success()
            elif response.status_code == 400:
                # 400 es esperado cuando ya no hay stock
                response.success()
            else:
                response.failure(f"Fallo inesperado: {response.status_code}")

    @task(3)
    def getProducto(self):
        # Tarea GET / (peso 3) según PDF
        self.client.get("/", name="GET /")

    @task(2)
    def ver_productos(self):
        # Tarea GET /productos — (peso 2)
        self.client.get("/productos", name="GET /productos")

    @task(1)
    def agregar_producto(self):
        # Tarea POST /productos — se mantiene para simular tráfico de escritura (peso 1)
        nuevo = {
            "nombre": "Producto Locust",
            "precio": 10,
            "cantidad": 5
        }
        self.client.post("/productos", json=nuevo, name="POST /productos")

    # ─── TAREA ELIMINADA PARA PROTEGER EL INVENTARIO ───
    # Se comenta la tarea de eliminación para evitar que el producto crítico (Café ID 3)
    # o cualquier otro producto sea borrado por azar durante las pruebas de concurrencia.
    
    # @task(1)
    # def eliminar_producto(self):
    #     # Tarea DELETE /productos/{id} — (peso 1)
    #     self.client.delete("/productos/1", name="DELETE /productos/{id}")