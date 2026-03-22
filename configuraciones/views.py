from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.models import User, Group
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Sum, Q, Count, F
from configuraciones.models import (
    Cliente, Prenda, Categoria, Venta, DetalleVenta,
    CarritoDeCompras, ItemCarrito, Pago, Pedido, CuponDescuento, VariacionPrenda
)
from django.http import HttpResponseForbidden, HttpResponse, JsonResponse
import json
from django.views.decorators.csrf import csrf_exempt
from django.core.mail import EmailMessage
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from configuraciones.utils import generate_invoice_pdf, numero_a_letras
from django.conf import settings
from django.utils import timezone
import datetime
import logging
from django.core.paginator import Paginator

logger = logging.getLogger(__name__)

# =====================================================
#        HELPERS
# =====================================================

def es_admin(user):
    return user.username == "admin_master" or user.is_superuser

def es_cliente(user):
    return user.groups.filter(name="Cliente").exists() or user.is_superuser

# =====================================================
#        HOME
# =====================================================

def home(request):
    productos = Prenda.objects.filter(is_archived=False)[:10]
    return render(request, "home.html", {"productos": productos})

# =====================================================
#        REGISTRO / LOGIN
# =====================================================

def registro(request):
    if request.method == "POST":
        username = request.POST.get("nombre")
        email = request.POST.get("email")
        password1 = request.POST.get("password1")
        password2 = request.POST.get("password2")
        direccion = request.POST.get("direccion")
        telefono = request.POST.get("telefono")

        if password1 != password2:
            messages.error(request, "Las contraseñas no coinciden")
            return redirect("registro")
            
        if User.objects.filter(username=username).exists():
            messages.error(request, "El nombre de usuario ya existe")
            return redirect("registro")

        user = User.objects.create_user(username=username, email=email, password=password1)

        grupo, _ = Group.objects.get_or_create(name="Cliente")
        user.groups.add(grupo)

        Cliente.objects.create(
            user=user,
            direccion=direccion,
            telefono=telefono
        )

        messages.success(request, "Usuario creado correctamente. Ahora puedes iniciar sesión.")
        return redirect("login")

    return render(request, "registro.html")


def inicio_sesion(request):
    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")
        
        user = authenticate(request, username=username, password=password)

        if user:
            login(request, user)
            messages.success(request, f"Bienvenido de nuevo, {user.username}")
            return redirect("home")

        messages.error(request, "Nombre de usuario o contraseña incorrectos")
        return redirect("login")

    return render(request, "login.html")


@login_required
def cerrar_sesion(request):
    logout(request)
    return redirect("home")

# =====================================================
#        TIENDA
# =====================================================

def tienda(request):
    productos = Prenda.objects.filter(is_archived=False)
    return render(request, "tienda.html", {"productos": productos})


def detalle_producto(request, slug):
    producto = get_object_or_404(Prenda, slug=slug, is_archived=False)
    return render(request, "detalle_producto.html", {"producto": producto})

# =====================================================
#        CARRITO
# =====================================================

@login_required
@user_passes_test(es_cliente)
def agregar_al_carrito(request, prenda_id):
    cliente = get_object_or_404(Cliente, user=request.user)
    carrito, _ = CarritoDeCompras.objects.get_or_create(cliente=cliente)
    producto = get_object_or_404(Prenda, id=prenda_id)
    item, created = ItemCarrito.objects.get_or_create(carrito=carrito, prenda=producto)
    if not created:
        item.cantidad += 1
    item.save()
    return redirect("carrito")

@login_required
@user_passes_test(es_cliente)
def restar_del_carrito(request, item_id):
    item = get_object_or_404(ItemCarrito, id=item_id)
    if item.cantidad > 1:
        item.cantidad -= 1
        item.save()
    else:
        item.delete()
    return redirect("carrito")

@login_required
@user_passes_test(es_cliente)
def eliminar_item_carrito(request, item_id):
    item = get_object_or_404(ItemCarrito, id=item_id)
    item.delete()
    return redirect("carrito")

@login_required
@user_passes_test(es_cliente)
def actualizar_cantidad(request, item_id):
    item = get_object_or_404(ItemCarrito, id=item_id)
    if request.method == "POST":
        cantidad = int(request.POST.get("cantidad", 1))
        if cantidad > 0:
            item.cantidad = cantidad
            item.save()
        else:
            item.delete()
    return redirect("carrito")

# =====================================================
#        CHECKOUT
# =====================================================

@login_required
@user_passes_test(es_cliente)
def carrito(request):
    cliente = get_object_or_404(Cliente, user=request.user)
    carrito, _ = CarritoDeCompras.objects.get_or_create(cliente=cliente)
    items = carrito.items.all()
    total = sum(i.subtotal for i in items)
    return render(request, "cliente/carrito.html", {
        "items": items,
        "total": total
    })

@login_required
@user_passes_test(es_cliente)
def checkout(request):
    cliente = get_object_or_404(Cliente, user=request.user)
    carrito = get_object_or_404(CarritoDeCompras, cliente=cliente)
    items = carrito.items.all()
    
    if not items:
        messages.warning(request, "Tu carrito está vacío.")
        return redirect("tienda")
        
    total = sum(i.subtotal for i in items)
    envio = 15000
    total_con_envio = total + envio
    
    return render(request, "cliente/checkout.html", {
        "carrito_items": items,
        "total": total,
        "total_con_envio": total_con_envio
    })


@login_required
def confirmar_compra(request):
    if request.method == "POST":
        cliente = get_object_or_404(Cliente, user=request.user)
        carrito = get_object_or_404(CarritoDeCompras, cliente=cliente)
        items = carrito.items.all()

        if not items:
            messages.error(request, "No hay productos en el carrito.")
            return redirect("carrito")

        # 1. Crear el Pedido
        pedido = Pedido.objects.create(
            cliente=cliente,
            departamento=request.POST.get("departamento"),
            ciudad=request.POST.get("ciudad"),
            direccion_envio=request.POST.get("direccion"),
            costo_envio=15000,
            estado="Pagado"  # En simulación lo marcamos como pagado de una vez
        )

        # 2. Crear el Pago
        pago = Pago.objects.create(
            pedido=pedido,
            metodo=request.POST.get("card_number", "Tarjeta (Simulación)"),
            estado="Completado",
            fecha=timezone.now().date()
        )

        # 3. Crear la Venta y sus Detalles
        subtotal = sum(i.subtotal for i in items)
        total = subtotal + 15000
        
        venta = Venta.objects.create(
            cliente=cliente,
            subtotal=subtotal,
            total=total,
            pago=pago,
            fecha_venta=timezone.now()
        )

        for item in items:
            DetalleVenta.objects.create(
                venta=venta,
                prenda=item.prenda,
                variacion=item.variacion,
                cantidad=item.cantidad,
                precio_unitario=item.prenda.precio_descuento if item.prenda.precio_descuento else item.prenda.precio
            )
            
            # 4. Reducir Stock
            if item.variacion:
                item.variacion.stock -= item.cantidad
                item.variacion.save()
            elif item.prenda:
                item.prenda.stock -= item.cantidad
                item.prenda.save()

        # 5. Limpiar Carrito
        items.delete()

        messages.success(request, "¡Gracias por tu compra! Tu pedido ha sido procesado.")
        return render(request, "confirmar_compra.html", {"venta": venta})
        
    return redirect("checkout")

def buscar_producto_api(request):
    barcode = request.GET.get('barcode')
    query = request.GET.get('q')
    
    if barcode:
        # Buscar por código de barras exacto
        producto = Prenda.objects.filter(codigo_barras=barcode, is_archived=False).first()
        if producto:
            return JsonResponse({
                'id': producto.id,
                'nombre': producto.nombre,
                'precio': float(producto.precio_descuento if producto.precio_descuento else producto.precio),
                'stock': producto.stock,
                'codigo': producto.codigo_barras
            })
        return JsonResponse({'error': 'Producto no encontrado'}, status=404)
        
    if query:
        # Buscar por nombre (parcial)
        productos = Prenda.objects.filter(
            Q(nombre__icontains=query) | Q(codigo_barras__icontains=query),
            is_archived=False
        )[:10]
        
        data = [{
            'id': p.id,
            'nombre': p.nombre,
            'precio': float(p.precio_descuento if p.precio_descuento else p.precio),
            'stock': p.stock,
            'codigo': p.codigo_barras
        } for p in productos]
        
        return JsonResponse(data, safe=False)
        
    return JsonResponse({'error': 'No se proporcionó parámetro de búsqueda'}, status=400)

@login_required
def simular_pago(request):
    # Esta vista puede ser un paso intermedio si se desea
    total = request.GET.get('total', 0)
    metodo = request.GET.get('metodo', 'Tarjeta')
    return render(request, "cliente/simular_pago.html", {
        "total": total,
        "metodo": metodo
    })

@user_passes_test(es_admin)
def actualizar_estado_pedido(request, pedido_id):
    if request.method == "POST":
        pedido = get_object_or_404(Pedido, id=pedido_id)
        nuevo_estado = request.POST.get("estado")
        if nuevo_estado in dict(Pedido.ESTADOS):
            pedido.estado = nuevo_estado
            pedido.save()
            messages.success(request, f"Pedido #{pedido.id} actualizado a {nuevo_estado}")
    return redirect("gestion_ventas")

@user_passes_test(es_admin)
def actualizar_envio_pedido(request, pedido_id):
    if request.method == "POST":
        pedido = get_object_or_404(Pedido, id=pedido_id)
        pedido.transportadora = request.POST.get("transportadora")
        pedido.guia_rastreo = request.POST.get("guia")
        pedido.estado = "Enviado"
        pedido.save()
        messages.success(request, f"Guía de envío actualizada para Pedido #{pedido.id}")
    return redirect("gestion_ventas")


def oferta(request):
    productos = Prenda.objects.filter(is_archived=False, precio_descuento__isnull=False)
    return render(request, "oferta.html", {"productos": productos})

def atencion(request):
    return render(request, "atencion.html")

def distribuidores(request):
    return render(request, "distribuidores.html")

def catalogo(request):
    productos = Prenda.objects.filter(is_archived=False)
    return render(request, "tienda.html", {"productos": productos})

@login_required
def factura_imprimir(request, venta_id):
    venta = get_object_or_404(Venta, id=venta_id)
    return render(request, "cliente/factura_imprimir.html", {"venta": venta})

@login_required
def descargar_factura_pdf(request, venta_id):
    venta = get_object_or_404(Venta, id=venta_id)
    pdf_buffer = generate_invoice_pdf(venta)
    response = HttpResponse(pdf_buffer.read(), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="Factura_{venta.id}.pdf"'
    return response

@user_passes_test(es_admin)
def panel_admin(request):
    total_productos = Prenda.objects.count()
    total_ventas = Venta.objects.count()
    return render(request, "admin/panel_admin.html", {
        "total_productos": total_productos,
        "total_ventas": total_ventas
    })

@user_passes_test(es_admin)
def gestion_productos(request):
    productos = Prenda.objects.all()
    return render(request, "admin/gestion_productos.html", {"productos": productos})

@user_passes_test(es_admin)
def crear_producto(request):
    if request.method == "POST":
        # Lógica básica de creación
        pass
    categorias = Categoria.objects.all()
    return render(request, "admin/crear_producto.html", {"categorias": categorias})

@user_passes_test(es_admin)
def editar_producto(request, prenda_id):
    producto = get_object_or_404(Prenda, id=prenda_id)
    return render(request, "admin/editar_producto.html", {"producto": producto})

@user_passes_test(es_admin)
def eliminar_producto(request, prenda_id):
    producto = get_object_or_404(Prenda, id=prenda_id)
    producto.delete()
    return redirect("gestion_productos")

@user_passes_test(es_admin)
def gestion_clientes(request):
    clientes = Cliente.objects.all()
    return render(request, "admin/gestion_clientes.html", {"clientes": clientes})

@user_passes_test(es_admin)
def detalle_cliente_ajax(request, cliente_id):
    cliente = get_object_or_404(Cliente, id=cliente_id)
    return render(request, "admin/detalle_cliente_modal.html", {"cliente": cliente})

@user_passes_test(es_admin)
def gestion_ventas(request):
    ventas = Venta.objects.all()
    return render(request, "admin/gestion_ventas.html", {"ventas": ventas})

@user_passes_test(es_admin)
def gestion_categorias(request):
    categorias = Categoria.objects.all()
    return render(request, "admin/gestion_categorias.html", {"categorias": categorias})

@user_passes_test(es_admin)
def crear_categoria(request):
    return render(request, "admin/crear_categoria.html")

@user_passes_test(es_admin)
def editar_categoria(request, categoria_id):
    categoria = get_object_or_404(Categoria, id=categoria_id)
    return render(request, "admin/editar_categoria.html", {"categoria": categoria})

@user_passes_test(es_admin)
def eliminar_categoria(request, categoria_id):
    categoria = get_object_or_404(Categoria, id=categoria_id)
    categoria.delete()
    return redirect("gestion_categorias")

@user_passes_test(es_admin)
def escanear_venta(request):
    return render(request, "admin/escanear_venta.html")


@login_required
@user_passes_test(es_cliente)
def panel_cliente(request):
    cliente, created = Cliente.objects.get_or_create(
        user=request.user,
        defaults={'telefono': 'N/A', 'direccion': 'N/A'}
    )
    return render(request, "cliente/panel_cliente.html", {"cliente": cliente})


@login_required
@user_passes_test(es_cliente)
def perfil_cliente(request):
    cliente = get_object_or_404(Cliente, user=request.user)
    return render(request, "cliente/perfil.html", {"cliente": cliente})


@login_required
@user_passes_test(es_cliente)
def editar_perfil(request):
    cliente = get_object_or_404(Cliente, user=request.user)
    if request.method == "POST":
        user = request.user
        user.first_name = request.POST.get("first_name")
        user.last_name = request.POST.get("last_name")
        user.email = request.POST.get("email")
        user.save()
        
        cliente.telefono = request.POST.get("telefono")
        cliente.direccion = request.POST.get("direccion")
        cliente.save()
        
        messages.success(request, "Perfil actualizado con éxito.")
        return redirect("perfil_cliente")
    
    return render(request, "cliente/editar_perfil.html", {"cliente": cliente})


@login_required
@user_passes_test(es_cliente)
def mis_ventas(request):
    cliente = get_object_or_404(Cliente, user=request.user)
    ventas = Venta.objects.filter(cliente=cliente).order_by("-fecha_venta")
    return render(request, "cliente/mis_ventas.html", {"ventas": ventas})


from django.core.management import call_command
from django.core.files import File
from pathlib import Path

def migrar_datos_produccion(request):
    output = []
    
    try:
        call_command('crear_productos_tienda')
        output.append("✅ Productos y categorías base creados.")
    except Exception as e:
        output.append(f"❌ Error en crear_productos_tienda: {str(e)}")

    if not User.objects.filter(username="admin").exists():
        try:
            User.objects.create_superuser("admin", "andreajimenezctg@gmail.com", "admin123456")
            output.append("✅ Superusuario 'admin' creado (Clave: admin123456).")
        except Exception as e:
            output.append(f"❌ Error al crear superusuario: {str(e)}")
    else:
        output.append("ℹ️ El superusuario 'admin' ya existe.")

    return HttpResponse("<br>".join(output))


def health_check(request):
    """Endpoint for Railway health checks and database connectivity verification."""
    from django.db import connection
    try:
        connection.ensure_connection()
        return HttpResponse("OK")
    except Exception:
        return HttpResponse("Database connection failed", status=500)