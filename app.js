// ─── Base de la API ────────────────────────────────────────────────
// Se centraliza la URL base para reutilizarla en los endpoints analíticos
const API_BASE = "http://127.0.0.1:8000";
const API_URL = API_BASE + "/productos";

// Selección de Elementos del DOM
const formProducto = document.getElementById("formProducto");
const tablaProductos = document.getElementById("tablaProductos");
const totalProductos = document.getElementById("totalProductos");

// Variables globales para las instancias de Chart.js (se destruyen antes de re-renderizar)
let chartProductos = null;
let chartDistribucion = null;

// Helper de formato monetario con separador de miles (comas)
const fmtMoney = (n) => "$" + (Number.isFinite(Number(n)) ? Number(n) : 0).toLocaleString("en-US", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
});

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


// ─── Funciones del Dashboard (KPIs + Chart.js) ─────────────────────
// 1a. Carga y pinta las tarjetas KPI
async function cargarKPIs() {
    try {
        // ─── NUEVO endpoint Polars (Proyecto 4) ───
        // Reemplaza a /dashboard/kpis; ahora procesa parquet + csv en paralelo
        const r = await fetch(API_BASE + "/api/analisis/kpis");
        if (!r.ok) return;
        const d = await r.json();
        // Fallbacks ante NaN / null
        const prod = (d && d.producto_mas_comprado) ? d.producto_mas_comprado : "Sin ventas";
        const unid = Number(d && d.unidades_mas_comprado) || 0;
        const ing = Number(d && d.ingresos_totales) || 0;
        const trans = Number(d && d.total_transacciones) || 0;
        const ticket = Number(d && d.ticket_promedio) || 0;

        document.getElementById("kpiProducto").textContent = prod;
        document.getElementById("kpiProductoUnidades").textContent = unid.toLocaleString("en-US") + " unidades";
        document.getElementById("kpiIngresos").textContent = fmtMoney(ing);
        document.getElementById("kpiTransacciones").textContent = trans.toLocaleString("en-US");
        document.getElementById("kpiTicket").textContent = fmtMoney(ticket);
    } catch (e) {
        console.error("Error al cargar KPIs:", e);
    }
}

// 1b. Carga y redibuja las dos gráficas Chart.js
//    La segunda gráfica es un doughnut con Top 3 + "Otros" en lugar de la de fechas.
async function cargarGraficas() {
    let productos = [];

    try {
        // ─── NUEVO endpoint Polars (Proyecto 4) ───
        // Reemplaza a /dashboard/ventas-por-producto; lee parquet + csv con Polars
        const rp = await fetch(API_BASE + "/api/analisis/mas-vendidos");
        if (rp.ok) productos = await rp.json();
    } catch (e) {
        console.error("Error al cargar gráficas:", e);
    }

    // Saneamiento: garantizar arreglo aunque el backend devuelva algo inesperado
    productos = Array.isArray(productos) ? productos : [];

    // ─── Gráfica 1: barras horizontales de ingresos por producto ───
    const canvasProd = document.getElementById("chartProductos");
    if (canvasProd) {
        if (chartProductos) chartProductos.destroy();   // evita fugas y duplicados
        const labelsP = productos.map(x => x.producto || "Desconocido");
        const dataP = productos.map(x => Number.isFinite(Number(x.ingresos)) ? Number(x.ingresos) : 0);
        chartProductos = new Chart(canvasProd.getContext("2d"), {
            type: "bar",
            data: {
                labels: labelsP.length ? labelsP : ["Sin datos"],
                datasets: [{
                    label: "Ingresos ($)",
                    data: dataP.length ? dataP : [0],
                    backgroundColor: "#c98b5b",
                    borderRadius: 6,
                }]
            },
            options: {
                indexAxis: "y",
                responsive: true,
                plugins: { legend: { display: false } },
                scales: { x: { beginAtZero: true } }
            }
        });
    }

    // ─── Gráfica 2: doughnut Top 3 + "Otros" por % de ingresos ───
    const canvasDist = document.getElementById("chartDistribucion");
    if (canvasDist) {
        if (chartDistribucion) chartDistribucion.destroy();

        // 1) Normalizar y quedarse solo con productos que aportan ingresos > 0
        //    (robusto ante NaN, ceros o productos eliminados con ventas históricas)
        const conIngresos = productos
            .map(x => ({
                producto: x.producto || "Desconocido",
                ingresos: Number.isFinite(Number(x.ingresos)) ? Number(x.ingresos) : 0,
            }))
            .filter(x => x.ingresos > 0);

        // 2) Top 3 individuales; el resto se agrupa como "Otros"
        const top3 = conIngresos.slice(0, 3);
        const restoIngresos = conIngresos.slice(3).reduce((s, x) => s + x.ingresos, 0);

        let labelsD = top3.map(x => x.producto);
        let dataD = top3.map(x => x.ingresos);

        // Solo agregamos "Otros" si de verdad hay productos fuera del top 3
        if (restoIngresos > 0) {
            labelsD.push("Otros");
            dataD.push(restoIngresos);
        }

        // 3) Estado vacío: dibujar un placeholder gris legible
        let colores = ["#6b4226", "#c98b5b", "#a8763e", "#d9b08c"];
        let esPlaceholder = false;
        if (labelsD.length === 0) {
            labelsD = ["Sin ventas"];
            dataD = [1];              // slice simbólica para que la dona se dibuje
            colores = ["#e0d6c8"];
            esPlaceholder = true;
        }

        const totalDist = dataD.reduce((a, b) => a + b, 0) || 1;

        // 4) Renderizar el doughnut (instancia previa ya destruida arriba)
        chartDistribucion = new Chart(canvasDist.getContext("2d"), {
            type: "doughnut",
            data: {
                labels: labelsD,
                datasets: [{
                    data: dataD,
                    backgroundColor: colores.slice(0, labelsD.length),
                    borderColor: "#fdf6ec",
                    borderWidth: 2,
                    hoverOffset: 6,
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: true,
                cutout: "60%",
                plugins: {
                    legend: {
                        position: "bottom",
                        labels: { boxWidth: 12, padding: 10, font: { size: 11 } }
                    },
                    tooltip: {
                        callbacks: {
                            // Muestra "$X.XX (YY.Y%)" por slice; texto especial en placeholder
                            label: (ctx) => {
                                if (esPlaceholder || ctx.label === "Sin ventas") {
                                    return "Sin ventas registradas";
                                }
                                const val = Number(ctx.parsed) || 0;
                                const pct = (val / totalDist * 100).toFixed(1);
                                const valFmt = val.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
                                return `${ctx.label}: $${valFmt} (${pct}%)`;
                            }
                        }
                    }
                }
            }
        });
    }
}

// 1c. Orquestador: refresca KPIs + gráficas
async function cargarDashboard() {
    await Promise.all([cargarKPIs(), cargarGraficas()]);
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
            await cargarDashboard();   // refresca KPIs y gráficas
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
            await cargarDashboard();   // refresca KPIs y gráficas
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
            await cargarDashboard();   // refresca KPIs y gráficas
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


// ─── Arranque: carga inventario y dashboard al abrir la página ─────
document.addEventListener("DOMContentLoaded", () => {
    cargarProductos();
    cargarDashboard();
});


// Agregamos el evento para que se ejecute la función al dar clic en guardar producto
formProducto.addEventListener("submit", agregarProducto);