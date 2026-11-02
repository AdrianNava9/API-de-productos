const API_URL = "http://127.0.0.1:8000/productos";

// Selección de Elementos del DOM
const formProducto = document.getElementById("formProducto");
const tablaProductos = document.getElementById("tablaProductos");
const totalProductos = document.getElementById("totalProductos");


// 0. Helper: muestra avisos flotantes sin romper la página
function mostrarAviso(mensaje, tipo = "warning") {
    // Crea el contenedor de avisos si no existe todavía
    let contenedor = document.getElementById("avisosContainer");
    if (!contenedor) {
        contenedor = document.createElement("div");
        contenedor.id = "avisosContainer";
        contenedor.style.cssText =
            "position:fixed;top:20px;right:20px;z-index:9999;" +
            "display:flex;flex-direction:column;gap:8px;max-width:340px;";
        document.body.appendChild(contenedor);
    }

    // Evita apilar avisos idénticos (por ejemplo, en clics rápidos)
    for (const existente of contenedor.children) {
        if (existente.dataset.mensaje === mensaje && existente.dataset.tipo === tipo) {
            return;
        }
    }

    // Limita a 4 avisos visibles simultáneamente
    while (contenedor.children.length >= 4) {
        contenedor.firstChild.remove();
    }

    // Crea el aviso y lo agrega al contenedor
    const aviso = document.createElement("div");
    aviso.className = `alert alert-${tipo} shadow-sm mb-0 d-flex align-items-center`;
    aviso.setAttribute("role", "alert");
    aviso.dataset.mensaje = mensaje;
    aviso.dataset.tipo = tipo;
    aviso.innerHTML = `<i class="bi bi-info-circle me-2"></i><span>${mensaje}</span>`;
    contenedor.appendChild(aviso);

    // Lo desvanece y elimina después de unos segundos
    const duracion = tipo === "success" ? 2500 : 4000;
    setTimeout(() => {
        aviso.style.transition = "opacity 0.4s";
        aviso.style.opacity = "0";
        setTimeout(() => aviso.remove(), 400);
    }, duracion);
}


// 1. Función para Cargar Productos (GET)
async function cargarProductos() {
    try {
        const respuesta = await fetch(API_URL);

        // Si el servidor respondió con error (429, 500, etc.),
        // NO destruimos la tabla: solo mostramos un aviso.
        if (!respuesta.ok) {
            if (respuesta.status === 429) {
                mostrarAviso("Demasiadas peticiones. Espera un momento antes de continuar.", "warning");
            } else {
                mostrarAviso(`Error ${respuesta.status} al cargar productos.`, "danger");
            }

            // Si la tabla está vacía (falló la primera carga), ofrecemos reintentar
            if (tablaProductos.children.length === 0) {
                tablaProductos.innerHTML = `
                    <tr>
                        <td colspan="5" class="text-center py-4">
                            <span class="text-muted">No se pudieron cargar los productos.</span><br>
                            <button class="btn btn-outline-primary btn-sm mt-2" onclick="cargarProductos()">
                                <i class="bi bi-arrow-clockwise"></i> Reintentar
                            </button>
                        </td>
                    </tr>`;
            }
            return false;
        }

        const productos = await respuesta.json();

        tablaProductos.innerHTML = "";
        totalProductos.textContent = `${productos.length} productos`;

        if (productos.length === 0) {
            tablaProductos.innerHTML = `
                <tr>
                    <td colspan="5" class="text-center text-muted py-4">
                        No hay productos registrados en la tiendita.
                    </td>
                </tr>`;
            return true;
        }

        productos.forEach(p => {
            const fila = document.createElement("tr");
            fila.innerHTML = `
                <td class="fw-bold text-secondary">#${p.id}</td>
                <td>${p.nombre}</td>
                <td class="text-success fw-bold">$${Number(p.precio).toFixed(2)}</td>
                <td>
                    <span class="badge ${p.cantidad < 10 ? 'bg-danger' : 'bg-success'}">
                        ${p.cantidad} unidades
                    </span>
                </td>
                <td class="text-end">
                    <button class="btn btn-outline-success btn-sm me-1" onclick="comprarProducto(${p.id})">
                        <i class="bi bi-cart"></i> Comprar
                    </button>
                    <button class="btn btn-outline-danger btn-sm" onclick="eliminarProducto(${p.id})">
                        <i class="bi bi-trash"></i> Eliminar
                    </button>
                </td>
            `;
            tablaProductos.appendChild(fila);
        });

        return true;

    } catch (error) {
        // Error de red real (servidor caído, sin conexión, etc.)
        console.error("Error al cargar productos:", error);
        mostrarAviso("No se pudo conectar con la API.", "danger");

        // Solo mostramos reintento si la tabla quedó vacía (carga inicial fallida)
        if (tablaProductos.children.length === 0) {
            tablaProductos.innerHTML = `
                <tr>
                    <td colspan="5" class="text-center py-4">
                        <span class="text-danger">No se pudo conectar con la API.</span><br>
                        <button class="btn btn-outline-primary btn-sm mt-2" onclick="cargarProductos()">
                            <i class="bi bi-arrow-clockwise"></i> Reintentar
                        </button>
                    </td>
                </tr>`;
        }
        return false;
    }
}


// 2. Función para Agregar Producto (POST)
async function agregarProducto(event){
    event.preventDefault();

    var nombre = document.getElementById("nombre").value;
    var precio = document.getElementById("precio").value;
    var cantidad = document.getElementById("cantidad").value;

    const nuevoContenido = {nombre, precio, cantidad};

    try {
        const respuesta = await fetch(API_URL, {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify(nuevoContenido)
        });

        if(respuesta.ok){
            formProducto.reset();
            const refrescoOk = await cargarProductos();
            if (refrescoOk) {
                mostrarAviso("Producto guardado correctamente.", "success");
            } else {
                mostrarAviso("Producto guardado, pero no se pudo actualizar la lista.", "info");
            }
        } else {
            const data = await respuesta.json().catch(() => ({}));
            if (respuesta.status === 429) {
                mostrarAviso("Demasiadas peticiones. Espera un momento antes de continuar.", "warning");
            } else {
                mostrarAviso("No se pudo guardar: " + (data.detail || "error desconocido"), "danger");
            }
        }
    } catch (error) {
        console.log(error);
        mostrarAviso("No se pudo conectar con la API.", "danger");
    }
}


// 3. Función para Eliminar Producto (DELETE)
async function eliminarProducto(id_producto){
    try {
        const respuesta = await fetch(API_URL + "/" + id_producto, {
            method: "DELETE",
            headers: {"Content-Type": "application/json"}
        });

        if(respuesta.ok){
            const refrescoOk = await cargarProductos();
            if (refrescoOk) {
                mostrarAviso("Producto eliminado.", "success");
            } else {
                mostrarAviso("Producto eliminado, pero no se pudo actualizar la lista.", "info");
            }
        } else {
            const data = await respuesta.json().catch(() => ({}));
            if (respuesta.status === 429) {
                mostrarAviso("Demasiadas peticiones. Espera un momento antes de continuar.", "warning");
            } else {
                mostrarAviso("No se pudo eliminar: " + (data.detail || "error desconocido"), "danger");
            }
        }
    } catch (error) {
        console.log(error);
        mostrarAviso("No se pudo conectar con la API.", "danger");
    }
}


// 4. Función para Comprar Producto (POST)
async function comprarProducto(id_producto){
    try {
        const respuesta = await fetch(API_URL + "/" + id_producto, {
            method: "POST",
            headers: {"Content-Type": "application/json"}
        });

        if(respuesta.ok){
            const refrescoOk = await cargarProductos();
            if (refrescoOk) {
                mostrarAviso("Producto comprado correctamente.", "success");
            } else {
                mostrarAviso("Compra realizada, pero no se pudo actualizar la lista. Reintenta en un momento.", "info");
            }
        } else {
            // Muestra el motivo del rechazo (sin stock, id inexistente o 429)
            const data = await respuesta.json().catch(() => ({}));
            if (respuesta.status === 429) {
                mostrarAviso("Demasiadas peticiones. Espera un momento antes de continuar.", "warning");
            } else {
                mostrarAviso("No se pudo comprar: " + (data.detail || "error desconocido"), "danger");
            }
        }
    } catch (error) {
        console.log(error);
        mostrarAviso("No se pudo conectar con la API.", "danger");
    }
}


// Cargar catálogo al abrir la página
document.addEventListener("DOMContentLoaded", cargarProductos);


// Agregamos el evento para que se ejecute la función al dar clic en guardar producto
formProducto.addEventListener("submit", agregarProducto);