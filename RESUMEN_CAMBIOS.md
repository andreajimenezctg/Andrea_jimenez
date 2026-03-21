# Resumen de cambios - Andrea Jiménez

## Cambios aplicados en el proyecto

### 1. Ubicación Andrea Jiménez
- **Quitados** los enlaces "Iniciar sesión" y "Registrarse" en el header cuando el usuario está en la página de Ubicación.
- **Añadida** sección de productos destacados con imágenes y precios COP (vestido, accesorios, bolsos).

### 2. Tienda
- **Diseño** igual al de Oferta: tarjetas con sombra, etiqueta "Colección", precios en COP.
- **Productos visibles** para todos (con o sin sesión). Solo para comprar se requiere registro/login.
- **Paginación**: 9 productos por página con enlaces Anterior/Siguiente.
- **Responsive**: se adapta a móviles y tablets.

### 3. Oferta
- **Productos visibles** sin sesión (imagen ampliable con lightbox).
- **Precios en COP**.
- **Paginación**: 9 productos por página.
- **Responsive**: igual que la tienda.

### 4. Inicio (Home)
- **Carrusel** con precios en formato COP.
- **Productos destacados** visibles para todos (los últimos 12).

### 5. Productos con imágenes y precios COP
- Comando `crear_productos_tienda`: crea 7 productos con precios en pesos colombianos (COP).
- Comando `asignar_imagenes_productos`: asigna imágenes. Si no hay en `media/productos/`, usa `static/img/` (vestido.jpeg, accesorios.jpeg, bolsos.jpeg).

**Para crear productos:**
```bash
python manage.py crear_productos_tienda
python manage.py asignar_imagenes_productos
```

### 6. Login
- **Diseño** centrado con tarjeta, logo circular, formulario y enlaces.
- **Colores**: beige #fff9e6, rosa #ff7a9c en botón, bordes #ffe7c5 en logo.

---

## Archivos modificados

- `templates/distribuidores.html`
- `templates/tienda.html`
- `templates/oferta.html`
- `templates/home.html`
- `templates/login.html`
- `static/css/login.css`
- `static/css/oferta.css`
- `static/css/distribuidores.css`
- `configuraciones/views.py`
- `configuraciones/management/commands/crear_productos_tienda.py`
- `configuraciones/management/commands/asignar_imagenes_productos.py`
