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
import time
from django.core.paginator import Paginator

logger = logging.getLogger(__name__)


# =====================================================
#        HELPERS (ROLES)
# =====================================================

def es_admin(user):
    return user.username == "admin_master" or user.is_superuser

def es_cliente(user):
    return user.groups.filter(name="Cliente").exists() or user.is_superuser


# =====================================================
#        PANEL CLIENTE
# =====================================================

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


@csrf_exempt
@login_required
def api_crear_venta_preliminar(request):
    """Crea una venta en estado pendiente"""
    if request.method != "POST":
        return JsonResponse({"status": "error", "message": "Método no permitido"}, status=405)
        
    try:
        data = json.loads(request.body)
        cliente = get_object_or_404(Cliente, user=request.user)
        carrito = get_object_or_404(CarritoDeCompras, cliente=cliente)
        items = [i for i in carrito.items.select_related("prenda", "variacion").all() if i.prenda]
        
        if not items:
            return JsonResponse({"status": "error", "message": "Carrito vacío"}, status=400)
            
        subtotal = sum(i.subtotal for i in items)
        descuento = 0 
        costo_envio = 15000
        total = subtotal - descuento + costo_envio
        
        # Crear Pedido preliminar
        pedido = Pedido.objects.create(
            cliente=cliente,
            estado="Pendiente",
            departamento=data.get("departamento", "N/A"),
            ciudad=data.get("ciudad", "N/A"),
            direccion_envio=data.get("direccion", "N/A"),
            costo_envio=costo_envio
        )
        
        # Crear Pago preliminar
        pago = Pago.objects.create(
            pedido=pedido,
            metodo="Pendiente",
            estado="Pendiente",
        )
        
        # Crear Venta preliminar
        venta = Venta.objects.create(
            cliente=cliente,
            subtotal=subtotal,
            descuento=descuento,
            total=total,
            pago=pago
        )
        
        # Registrar detalles
        for item in items:
            precio = item.prenda.precio_descuento if item.prenda.precio_descuento else item.prenda.precio
            DetalleVenta.objects.create(
                venta=venta,
                prenda=item.prenda,
                variacion=item.variacion,
                cantidad=item.cantidad,
                precio_unitario=precio
            )
        
        return JsonResponse({
            "status": "success",
            "venta_id": venta.id,
        })
        
    except Exception as e:
        logger.error(f"Error venta preliminar: {str(e)}")
        return JsonResponse({"status": "error", "message": str(e)}, status=500)


def catalogo(request):
    """Vista para ver el catálogo general de productos"""
    productos = Prenda.objects.filter(disponible=True).order_by("-id")
    return render(request, "tienda.html", {"productos": productos})


# =====================================================
#        AUTENTICACIÓN
# =====================================================

def registro(request):
    if request.method == "POST":
        username = request.POST.get("nombre", "").strip()
        email = request.POST.get("email", "").strip().lower()
        password1 = request.POST.get("password1")
        password2 = request.POST.get("password2")
        direccion = request.POST.get("direccion", "").strip()
        telefono = request.POST.get("telefono", "").strip()

        if not username:
            messages.error(request, "Debes ingresar un nombre de usuario.")
            return redirect("registro")

        if password1 != password2:
            messages.error(request, "Las contraseñas no coinciden.")
            return redirect("registro")

        if len(password1) < 8:
            messages.error(request, "La contraseña debe tener al menos 8 caracteres.")
            return redirect("registro")

        if User.objects.filter(username=username).exists():
            messages.error(request, "Ese nombre de usuario ya existe.")
            return redirect("registro")

        if email and User.objects.filter(email=email).exists():
            messages.error(request, "Ese correo ya está en uso.")
            return redirect("registro")

        user = User.objects.create_user(
            username=username,
            email=email,
            password=password1
        )
        user.first_name = username
        user.save()

        grupo_cliente, _ = Group.objects.get_or_create(name="Cliente")
        user.groups.add(grupo_cliente)

        Cliente.objects.create(
            user=user,
            direccion=direccion,
            telefono=telefono
        )

        messages.success(request, "Cuenta creada correctamente. Ahora puedes iniciar sesión.")
        return redirect("login")

    return render(request, "registro.html")


def inicio_sesion(request):
    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")

        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            if es_admin(user):
                return redirect("panel_admin")
            elif es_cliente(user):
                return redirect("panel_cliente")
            return redirect("home")

        messages.error(request, "Usuario o contraseña incorrectos.")
        return redirect("login")

    return render(request, "login.html")


@login_required
def cerrar_sesion(request):
    logout(request)
    return redirect("home")


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

    try:
        import shutil
        mapeo_productos = {
            "Vestido floral verano": "vestido_floral.jpg",
            "Vestido noche elegante": "vestido_noche.jpg",
            "Vestido casual": "vestido_casual.jpg",
            "Bolso mano": "bolso_mano.jpg",
            "Bolso cruzado": "bolso_cruzado.jpg",
            "Cinturón clásico": "cinturon.jpg",
            "Pañoleta": "panoleta.jpg",
        }
        
        media_productos = Path(settings.MEDIA_ROOT) / "productos"
        media_productos.mkdir(parents=True, exist_ok=True)
        
        for nombre_prod, nombre_img in mapeo_productos.items():
            productos = Prenda.objects.filter(nombre__icontains=nombre_prod)
            ruta_img_static = Path(settings.BASE_DIR) / "static" / "img" / nombre_img
            
            if ruta_img_static.exists():
                nombre_db = f"productos/{nombre_img}"
                ruta_destino_media = Path(settings.MEDIA_ROOT) / nombre_db
                shutil.copy2(ruta_img_static, ruta_destino_media)
                
                for p in productos:
                    p.imagen = nombre_db
                    p.save()
                output.append(f"✅ Imagen REAL forzada para: {nombre_prod}")
            else:
                output.append(f"⚠️ No se encontró {nombre_img} en static/img/.")
                
    except Exception as e:
        output.append(f"❌ Error al asignar imágenes: {str(e)}")

    if not User.objects.filter(username="admin").exists():
        try:
            User.objects.create_superuser("admin", "andreajimenezctg@gmail.com", "admin123456")
            output.append("✅ Superusuario 'admin' creado (Clave: admin123456).")
        except Exception as e:
            output.append(f"❌ Error al crear superusuario: {str(e)}")
    else:
        output.append("ℹ️ El superusuario 'admin' ya existe.")

    return HttpResponse("<br>".join(output))


# =====================================================
#        VISTAS PÚBLICAS
# =====================================================

def home(request):
    productos_carrusel = Prenda.objects.filter(is_archived=False).order_by("-id")[:12]
    es_cliente_user = request.user.is_authenticated and es_cliente(request.user)
    return render(request, "home.html", {
        "productos_carrusel": productos_carrusel,
        "es_cliente": es_cliente_user,
    })

def tienda(request):
    search_query = request.GET.get('q', '')
    category_id = request.GET.get('categoria', '')
    min_price = request.GET.get('min_price')
    max_price = request.GET.get('max_price')

    productos_qs = Prenda.objects.filter(is_archived=False).order_by("-id")

    if search_query:
        productos_qs = productos_qs.filter(nombre__icontains=search_query)
    
    if category_id:
        productos_qs = productos_qs.filter(categoria_id=category_id)
    
    if min_price:
        productos_qs = productos_qs.filter(precio__gte=min_price)
    
    if max_price:
        productos_qs = productos_qs.filter(precio__lte=max_price)

    paginator = Paginator(productos_qs, 9)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)
    
    categorias = Categoria.objects.all().order_by("nombre")
    es_cliente_user = request.user.is_authenticated and es_cliente(request.user)
    
    return render(request, "tienda.html", {
        "productos": page_obj,
        "page_obj": page_obj,
        "categorias": categorias,
        "es_cliente": es_cliente_user,
        "search_query": search_query,
        "selected_category": category_id,
    })

def oferta(request):
    productos_qs = Prenda.objects.filter(is_archived=False).order_by("-id")
    paginator = Paginator(productos_qs, 9)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)
    es_cliente_user = request.user.is_authenticated and es_cliente(request.user)
    return render(request, "oferta.html", {
        "productos": page_obj,
        "page_obj": page_obj,
        "es_cliente": es_cliente_user,
    })

def atencion(request):
    if request.method == "POST":
        nombre = request.POST.get("nombre")
        email_cliente = request.POST.get("email")
        telefono = request.POST.get("telefono")
        mensaje = request.POST.get("mensaje")
        
        try:
            email = EmailMessage(
                f"Nuevo Mensaje de Contacto: {nombre}",
                f"Nombre: {nombre}\nEmail: {email_cliente}\nTeléfono: {telefono}\n\nMensaje:\n{mensaje}",
                settings.EMAIL_HOST_USER,
                [settings.EMAIL_HOST_USER]
            )
            email.send(fail_silently=False)
            logger.info(f"Mensaje de contacto enviado correctamente de {nombre} ({email_cliente})")
            messages.success(request, "Tu mensaje ha sido enviado correctamente. Te contactaremos pronto.")
        except Exception as e:
            logger.error(f"Error al enviar mensaje de contacto: {str(e)}")
            messages.error(request, "Hubo un error al enviar el mensaje. Por favor intenta de nuevo.")
            
        return redirect("atencion")
        
    return render(request, "atencion.html")

def distribuidores(request):
    return render(request, "distribuidores.html")

def detalle_producto(request, slug):
    producto = get_object_or_404(Prenda, slug=slug, is_archived=False)
    es_cliente_user = request.user.is_authenticated and es_cliente(request.user)
    
    precio_base = producto.precio_descuento if producto.precio_descuento else producto.precio
    cuotas_12 = round(precio_base / 12, 2)
    
    relacionados = Prenda.objects.filter(
        categoria=producto.categoria, 
        is_archived=False
    ).exclude(id=producto.id)[:4]
    
    return render(request, "detalle_producto.html", {
        "producto": producto,
        "es_cliente": es_cliente_user,
        "relacionados": relacionados,
        "cuotas_12": cuotas_12,
    })


# =====================================================
#        CARRITO
# =====================================================

@login_required
@user_passes_test(es_cliente)
def agregar_al_carrito(request, prenda_id):
    cliente, created = Cliente.objects.get_or_create(
        user=request.user,
        defaults={'telefono': 'N/A', 'direccion': 'N/A'}
    )
    
    carrito, created = CarritoDeCompras.objects.get_or_create(cliente=cliente)

    producto = get_object_or_404(Prenda, id=prenda_id)
    variacion_id = request.POST.get("variacion_id")
    variacion = None
    
    if variacion_id:
        variacion = get_object_or_404(VariacionPrenda, id=variacion_id, prenda=producto)

    if producto.stock < 1:
        messages.error(request, f"El producto '{producto.nombre}' está agotado.")
        return redirect("carrito")

    item = ItemCarrito.objects.filter(
        carrito=carrito,
        prenda=producto,
        variacion=variacion
    ).first()

    if item:
        if item.cantidad + 1 > producto.stock:
            messages.error(request, f"Solo hay {producto.stock} unidades disponibles de '{producto.nombre}'.")
            return redirect("carrito")
        item.cantidad += 1
        item.save()
    else:
        ItemCarrito.objects.create(
            carrito=carrito,
            prenda=producto,
            variacion=variacion,
            cantidad=1
        )

    messages.success(request, f"'{producto.nombre}' agregado al carrito.")
    return redirect("carrito")


@login_required
@user_passes_test(es_cliente)
def carrito(request):
    cliente, created = Cliente.objects.get_or_create(
        user=request.user,
        defaults={'telefono': 'N/A', 'direccion': 'N/A'}
    )
    carrito, created = CarritoDeCompras.objects.get_or_create(cliente=cliente)

    items = [i for i in carrito.items.select_related("prenda").all() if i.prenda]
    total = sum(item.subtotal for item in items)
    total_con_envio = total + 15000

    return render(request, "cliente/carrito.html", {
        "carrito_items": items,
        "total": total,
        "total_con_envio": total_con_envio
    })


@login_required
@user_passes_test(es_cliente)
def actualizar_cantidad(request, item_id):
    item = get_object_or_404(ItemCarrito, id=item_id)

    if request.method == "POST":
        cantidad = int(request.POST.get("cantidad", 1))

        if cantidad > 0:
            if cantidad > item.prenda.stock:
                messages.error(request, f"Solo hay {item.prenda.stock} unidades disponibles de '{item.prenda.nombre}'.")
                item.cantidad = item.prenda.stock
            else:
                item.cantidad = cantidad
            item.save()
        else:
            item.delete()

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


# =====================================================
#        CHECKOUT Y PEDIDO
# =====================================================

@login_required
@user_passes_test(es_cliente)
def checkout(request):
    cliente, created = Cliente.objects.get_or_create(
        user=request.user,
        defaults={'telefono': 'N/A', 'direccion': 'N/A'}
    )
    carrito, created = CarritoDeCompras.objects.get_or_create(cliente=cliente)
    items = [i for i in carrito.items.select_related("prenda").all() if i.prenda]

    if not items:
        messages.error(request, "Tu carrito está vacío.")
        return redirect("carrito")

    # ✅ CORRECCIÓN: convertir a int para evitar errores de formato en JavaScript
    subtotal = int(sum(i.subtotal for i in items))
    costo_envio = 15000
    total_con_envio = subtotal + costo_envio
    
    return render(request, "cliente/checkout.html", {
        "carrito_items": items,
        "total": subtotal,
        "total_con_envio": total_con_envio,
        "whatsapp_number": settings.WHATSAPP_NUMBER,
        "site_url": settings.SITE_URL,
    })


# =====================================================
#        CONFIRMAR COMPRA
# =====================================================

@login_required
@user_passes_test(es_cliente)
def confirmar_compra(request):
    cliente = get_object_or_404(Cliente, user=request.user)
    carrito = get_object_or_404(CarritoDeCompras, cliente=cliente)
    items = [i for i in carrito.items.select_related("prenda", "variacion").all() if i.prenda]

    if not items:
        messages.error(request, "Tu carrito está vacío.")
        return redirect("carrito")

    if request.method == "POST":
        departamento = request.POST.get("departamento")
        ciudad = request.POST.get("ciudad")
        direccion = request.POST.get("direccion")
        codigo_cupon = request.POST.get("cupon")
        
        subtotal = sum(i.subtotal for i in items)
        descuento = 0
        cupon_obj = None
        
        if codigo_cupon:
            try:
                cupon_obj = CuponDescuento.objects.get(codigo=codigo_cupon)
                if cupon_obj.es_valido():
                    descuento = (subtotal * cupon_obj.porcentaje) / 100
                else:
                    messages.warning(request, "El cupón no es válido o ha expirado.")
            except CuponDescuento.DoesNotExist:
                messages.warning(request, "El cupón ingresado no existe.")

        costo_envio = 15000
        total = subtotal - descuento + costo_envio

        # 1. Crear Pedido
        pedido = Pedido.objects.create(
            cliente=cliente,
            estado="Pagado", # Se marca como pagado ya que es una simulación exitosa
            departamento=departamento,
            ciudad=ciudad,
            direccion_envio=direccion,
            costo_envio=costo_envio
        )

        # 2. Crear Pago
        pago = Pago.objects.create(
            pedido=pedido,
            metodo="Simulación Tarjeta",
            estado="Aprobado"
        )

        # 3. Crear Venta
        venta = Venta.objects.create(
            cliente=cliente,
            subtotal=subtotal,
            descuento=descuento,
            total=total,
            cupon=cupon_obj,
            pago=pago
        )

        # 4. Registrar detalles y actualizar stock
        for item in items:
            precio = item.prenda.precio_descuento if item.prenda.precio_descuento else item.prenda.precio
            DetalleVenta.objects.create(
                venta=venta,
                prenda=item.prenda,
                variacion=item.variacion,
                cantidad=item.cantidad,
                precio_unitario=precio
            )
            
            # Descontar stock
            if item.variacion:
                item.variacion.stock -= item.cantidad
                item.variacion.save()
                
            item.prenda.stock -= item.cantidad
            item.prenda.save()

        # 5. Limpiar carrito
        carrito.items.all().delete()

        if cliente.user.email:
            try:
                logger.info(f"--- INICIO PROCESO CORREO VENTA #{venta.id} ---")
                logger.info(f"Cliente: {cliente.user.username}, Email: {cliente.user.email}")
                
                pdf_buffer = generate_invoice_pdf(venta)
                pdf_content = pdf_buffer.getvalue()
                logger.info(f"PDF generado. Tamaño: {len(pdf_content)} bytes")
                
                context = {
                    'cliente': cliente,
                    'venta': venta,
                    'total': total,
                    'metodo_pago': pago.metodo,
                    'site_url': settings.SITE_URL,
                    'current_year': timezone.now().year,
                }
                
                html_content = render_to_string('email/email_factura.html', context)
                logger.info("Plantilla HTML renderizada correctamente")
                
                email = EmailMessage(
                    f"Factura de Compra #{venta.id} - Andrea Jiménez",
                    html_content,
                    settings.EMAIL_HOST_USER,
                    [cliente.user.email]
                )
                email.content_subtype = "html"
                
                if len(pdf_content) > 0:
                    email.attach(f"Factura_{venta.id}.pdf", pdf_content, "application/pdf")
                    logger.info("PDF adjuntado al objeto EmailMessage")
                    logger.info("Llamando a email.send()...")
                    sent_count = email.send(fail_silently=False)
                    logger.info(f"Resultado email.send(): {sent_count}")
                    
                    if sent_count > 0:
                        logger.info(f"¡ÉXITO CONFIRMADO! Correo enviado a {cliente.user.email}")
                    else:
                        logger.error(f"ADVERTENCIA: email.send() retornó 0 para {cliente.user.email}")
                else:
                    logger.error(f"ERROR: PDF vacío para venta #{venta.id}")

            except Exception as e:
                import traceback
                logger.error(f"EXCEPCIÓN CRÍTICA en envío de correo: {str(e)}")
                logger.error(traceback.format_exc())
            finally:
                logger.info(f"--- FIN PROCESO CORREO VENTA #{venta.id} ---")
        else:
            logger.warning(f"No se pudo enviar correo: El cliente {cliente.user.username} no tiene email registrado.")

        messages.success(request, f"¡Pago simulado con éxito! Pedido #{venta.id} registrado.")
        return redirect("factura_imprimir", venta_id=venta.id)

    return redirect("checkout")


@login_required
def factura_imprimir(request, venta_id):
    venta = get_object_or_404(Venta, id=venta_id)
    if venta.cliente and venta.cliente.user_id != request.user.id and not es_admin(request.user):
        return HttpResponseForbidden("No puedes ver esta factura.")

    items = list(venta.detalles.select_related("prenda").all())
    items_detalle = [
        {
            "id": d.id,
            "producto": d.prenda.nombre if d.prenda else "—",
            "cantidad": d.cantidad,
            "precio_unitario": d.precio_unitario,
            "subtotal": d.cantidad * d.precio_unitario,
            "barcode_url": d.prenda.barcode_image.url if d.prenda and d.prenda.barcode_image else None,
            "codigo_barras": d.prenda.codigo_barras if d.prenda else f"AJ-{d.id:04d}"
        }
        for d in items
    ]
    total = venta.total or 0
    valor_letras = numero_a_letras(total)

    return render(request, "cliente/factura_imprimir.html", {
        "venta": venta,
        "items_detalle": items_detalle,
        "total": total,
        "valor_letras": valor_letras,
        "site_url": settings.SITE_URL,
    })


@login_required
def descargar_factura_pdf(request, venta_id):
    venta = get_object_or_404(Venta, id=venta_id)
    if venta.cliente and venta.cliente.user_id != request.user.id and not es_admin(request.user):
        return HttpResponseForbidden("No puedes descargar esta factura.")

    pdf_buffer = generate_invoice_pdf(venta)
    response = HttpResponse(pdf_buffer.read(), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="Factura_Andrea_Jiménez_{venta.id}.pdf"'
    return response


# =====================================================
#        ADMIN
# =====================================================

@user_passes_test(es_admin)
def panel_admin(request):
    try:
        total_productos = Prenda.objects.filter(is_archived=False).count()
        total_ventas = Venta.objects.count()
        ingresos_totales = Venta.objects.aggregate(total=Sum('total'))['total'] or 0
        total_clientes = Cliente.objects.count()

        hoy = timezone.now()
        inicio_mes = hoy.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        
        productos_mes = Prenda.objects.filter(created_at__gte=inicio_mes, is_archived=False).count()
        ventas_mes = Venta.objects.filter(fecha_venta__gte=inicio_mes).count()
        clientes_mes = User.objects.filter(date_joined__gte=inicio_mes, groups__name="Cliente").count()

        ventas_mensuales = []
        meses_nombres = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic']
        labels_grafica = []
        
        for i in range(11, -1, -1):
            target_date = hoy - datetime.timedelta(days=i*30)
            mes_idx = target_date.month - 1
            anio_adj = target_date.year
            
            ventas_count = Venta.objects.filter(fecha_venta__month=mes_idx + 1, fecha_venta__year=anio_adj).count()
            ventas_mensuales.append(ventas_count)
            labels_grafica.append(meses_nombres[mes_idx])

        categorias_qs = Categoria.objects.annotate(
            num_ventas=Sum('prendas__detalleventa__cantidad')
        ).filter(num_ventas__gt=0)
        
        categorias_labels = [cat.nombre for cat in categorias_qs]
        total_unidades = sum(cat.num_ventas or 0 for cat in categorias_qs)
        
        if total_unidades > 0:
            categorias_data = [round((cat.num_ventas or 0) * 100 / total_unidades, 1) for cat in categorias_qs]
        else:
            categorias_labels = []
            categorias_data = []

        ventas_recientes = Venta.objects.select_related('cliente__user').order_by('-fecha_venta')[:5]
        productos_bajo_stock = Prenda.objects.filter(stock__lt=5, is_archived=False).order_by('stock')[:5]

        productos_en_stock = Prenda.objects.filter(stock__gt=0, is_archived=False).count()
        stock_porcentaje = round(productos_en_stock * 100 / total_productos, 1) if total_productos > 0 else 0
        stock_offset = 251.2 * (1 - (stock_porcentaje / 100))

        meta_ventas = 100
        ventas_actuales = ventas_mes
        porcentaje_meta = min(round(ventas_actuales * 100 / meta_ventas, 1), 100) if meta_ventas > 0 else 0
        meta_ventas_offset = 251.2 * (1 - (porcentaje_meta / 100))

        productos_oferta = Prenda.objects.filter(precio_descuento__isnull=False, is_archived=False).count()
        ofertas_porcentaje = round(productos_oferta * 100 / total_productos, 1) if total_productos > 0 else 0
        ofertas_offset = 251.2 * (1 - (ofertas_porcentaje / 100))

        context = {
            "total_productos": total_productos,
            "productos_mes": productos_mes,
            "total_ventas": total_ventas,
            "ventas_mes": ventas_mes,
            "ingresos_totales": f"${int(ingresos_totales):,}",
            "total_clientes": total_clientes,
            "clientes_mes": clientes_mes,
            "ventas_mensuales": ventas_mensuales,
            "labels_grafica": labels_grafica,
            "categorias_labels": categorias_labels,
            "categorias_data": categorias_data,
            "ventas_recientes": ventas_recientes,
            "productos_bajo_stock": productos_bajo_stock,
            "meta_ventas": meta_ventas,
            "ventas_actuales": ventas_actuales,
            "meta_ventas_porcentaje": porcentaje_meta,
            "meta_ventas_offset": meta_ventas_offset,
            "productos_en_stock": productos_en_stock,
            "stock_porcentaje": stock_porcentaje,
            "stock_offset": stock_offset,
            "productos_oferta": productos_oferta,
            "ofertas_porcentaje": ofertas_porcentaje,
            "ofertas_offset": ofertas_offset,
        }
        return render(request, "admin/panel_admin.html", context)
    except Exception as e:
        logger.error(f"Error en panel_admin: {str(e)}")
        return render(request, "admin/panel_admin.html", {"error": True})


@login_required
@user_passes_test(es_admin)
def gestion_productos(request):
    search_query = request.GET.get('search', '')
    category_id = request.GET.get('categoria', '')
    stock_status = request.GET.get('stock', '')
    sort_by = request.GET.get('sort', '-id')
    order = request.GET.get('order', 'desc')
    
    sort_mapping = {
        'nombre': 'nombre',
        'categoria': 'categoria__nombre',
        'precio': 'precio',
        'stock': 'stock',
        '-id': '-id'
    }
    
    order_prefix = '-' if order == 'desc' else ''
    order_field = sort_mapping.get(sort_by, '-id')
    
    if order_field != '-id':
        order_field = f"{order_prefix}{order_field}"
    
    productos_qs = Prenda.objects.all().order_by(order_field)
    
    if search_query:
        productos_qs = productos_qs.filter(
            Q(nombre__icontains=search_query) | 
            Q(codigo_barras__icontains=search_query)
        )
    
    if category_id:
        try:
            category_id = int(category_id)
            productos_qs = productos_qs.filter(categoria_id=category_id)
        except (ValueError, TypeError):
            category_id = ''
        
    if stock_status == 'disponible':
        productos_qs = productos_qs.filter(stock__gt=0, is_archived=False)
    elif stock_status == 'bajo':
        productos_qs = productos_qs.filter(stock__lte=5, stock__gt=0, is_archived=False)
    elif stock_status == 'agotado':
        productos_qs = productos_qs.filter(stock=0)

    total_productos = Prenda.objects.count()
    activos = Prenda.objects.filter(is_archived=False, stock__gt=0).count()
    bajo_stock = Prenda.objects.filter(stock__lte=5, is_archived=False, stock__gt=0).count()
    en_oferta = Prenda.objects.filter(precio_descuento__isnull=False, is_archived=False).count()

    paginator = Paginator(productos_qs, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    categorias = Categoria.objects.all().order_by("nombre")

    context = {
        "productos": page_obj,
        "page_obj": page_obj,
        "total_productos": total_productos,
        "activos": activos,
        "bajo_stock": bajo_stock,
        "en_oferta": en_oferta,
        "categorias": categorias,
        "search_query": search_query,
        "selected_category": category_id,
        "selected_stock": stock_status
    }
    return render(request, "admin/gestion_productos.html", context)


@login_required
@user_passes_test(es_admin)
def crear_producto(request):
    categorias = Categoria.objects.all().order_by("nombre")

    if request.method == "POST":
        nombre = request.POST.get("nombre", "").strip()
        descripcion = request.POST.get("descripcion", "").strip()
        precio = float(request.POST.get("precio", 0))
        precio_descuento = request.POST.get("precio_descuento")
        stock = int(request.POST.get("stock", 0))
        categoria_id = request.POST.get("categoria")
        imagen = request.FILES.get("imagen")

        categoria = get_object_or_404(Categoria, id=categoria_id)

        Prenda.objects.create(
            nombre=nombre,
            descripcion=descripcion,
            precio=precio,
            precio_descuento=float(precio_descuento) if precio_descuento else None,
            stock=stock,
            categoria=categoria,
            imagen=imagen
        )

        messages.success(request, f"Producto '{nombre}' creado correctamente.")
        return redirect("gestion_productos")

    return render(request, "admin/crear_producto.html", {"categorias": categorias})


@login_required
@user_passes_test(es_admin)
def editar_producto(request, prenda_id):
    producto = get_object_or_404(Prenda, id=prenda_id)
    categorias = Categoria.objects.all().order_by("nombre")

    if request.method == "POST":
        producto.nombre = request.POST.get("nombre", "")
        producto.descripcion = request.POST.get("descripcion", "")
        producto.precio = float(request.POST.get("precio", 0))
        precio_descuento = request.POST.get("precio_descuento")
        producto.precio_descuento = float(precio_descuento) if precio_descuento else None
        producto.stock = int(request.POST.get("stock", 0))
        categoria_id = request.POST.get("categoria")

        if categoria_id:
            producto.categoria = get_object_or_404(Categoria, id=categoria_id)

        imagen = request.FILES.get("imagen")
        if imagen:
            producto.imagen = imagen

        producto.save()

        messages.success(request, f"Producto '{producto.nombre}' actualizado correctamente.")
        return redirect("gestion_productos")

    return render(request, "admin/editar_producto.html", {
        "producto": producto,
        "categorias": categorias
    })


@login_required
@user_passes_test(es_admin)
def eliminar_producto(request, prenda_id):
    prenda = get_object_or_404(Prenda, id=prenda_id)
    prenda.delete()
    messages.success(request, f"Producto '{prenda.nombre}' eliminado correctamente.")
    return redirect("gestion_productos")


# =====================================================
#        CLIENTES Y CATEGORÍAS
# =====================================================

@login_required
@user_passes_test(es_admin)
def gestion_clientes(request):
    search_query = request.GET.get('search', '')
    status = request.GET.get('status', '')
    sort = request.GET.get('sort', 'reciente')
    
    clientes_qs = Cliente.objects.annotate(
        total_compras=Count('ventas'),
        total_gastado=Sum('ventas__total'),
        fecha_registro=F('user__date_joined')
    ).all()
    
    if search_query:
        clientes_qs = clientes_qs.filter(
            Q(user__username__icontains=search_query) |
            Q(user__first_name__icontains=search_query) |
            Q(user__last_name__icontains=search_query) |
            Q(user__email__icontains=search_query) |
            Q(telefono__icontains=search_query)
        )
    
    if status == 'con_compras':
        clientes_qs = clientes_qs.filter(total_compras__gt=0)
    elif status == 'sin_compras':
        clientes_qs = clientes_qs.filter(total_compras=0)
        
    if sort == 'nombre':
        clientes_qs = clientes_qs.order_by('user__first_name')
    elif sort == 'compras':
        clientes_qs = clientes_qs.order_by('-total_compras')
    else:
        clientes_qs = clientes_qs.order_by('-user__date_joined')
        
    total_clientes = Cliente.objects.count()
    clientes_mes = Cliente.objects.filter(user__date_joined__month=datetime.datetime.now().month).count()
    clientes_con_compras = Cliente.objects.annotate(num_compras=Count('ventas')).filter(num_compras__gt=0).count()
    
    cliente_top_obj = Cliente.objects.annotate(gastado=Sum('ventas__total')).order_by('-gastado').first()
    cliente_top = {
        'nombre': cliente_top_obj.user.first_name or cliente_top_obj.user.username if cliente_top_obj else "-"
    }

    paginator = Paginator(clientes_qs, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        "clientes": page_obj,
        "page_obj": page_obj,
        "total_clientes": total_clientes,
        "clientes_mes": clientes_mes,
        "clientes_con_compras": clientes_con_compras,
        "cliente_top": cliente_top,
        "search_query": search_query,
        "selected_status": status,
        "selected_sort": sort
    }
    return render(request, "admin/gestion_clientes.html", context)


@login_required
@user_passes_test(es_admin)
def detalle_cliente_ajax(request, cliente_id):
    cliente = get_object_or_404(Cliente, id=cliente_id)
    ventas = Venta.objects.filter(cliente=cliente).order_by("-fecha_venta")
    
    return render(request, "admin/detalle_cliente_modal.html", {
        "cliente": cliente,
        "ventas": ventas
    })


@login_required
@user_passes_test(es_admin)
def gestion_ventas(request):
    hoy = datetime.datetime.now()
    inicio_mes = hoy.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    
    search_query = request.GET.get('search', '')
    from_date = request.GET.get('from', '')
    to_date = request.GET.get('to', '')
    status = request.GET.get('status', '')
    
    ventas_qs = Venta.objects.all().order_by("-fecha_venta")
    
    if search_query:
        ventas_qs = ventas_qs.filter(
            Q(id__icontains=search_query) | 
            Q(cliente__user__username__icontains=search_query) |
            Q(cliente__user__first_name__icontains=search_query)
        )
    
    if from_date:
        ventas_qs = ventas_qs.filter(fecha_venta__date__gte=from_date)
    if to_date:
        ventas_qs = ventas_qs.filter(fecha_venta__date__lte=to_date)
    
    total_ventas = Venta.objects.count()
    ventas_hoy = Venta.objects.filter(fecha_venta__date=hoy.date()).count()
    ingresos_mes = Venta.objects.filter(fecha_venta__gte=inicio_mes).aggregate(total=Sum('total'))['total'] or 0
    promedio_venta = ingresos_mes / total_ventas if total_ventas > 0 else 0
    
    labels = []
    data = []
    dias_semana = ['Lun', 'Mar', 'Mie', 'Jue', 'Vie', 'Sab', 'Dom']
    
    for i in range(6, -1, -1):
        dia = hoy - datetime.timedelta(days=i)
        count = Venta.objects.filter(fecha_venta__date=dia.date()).count()
        labels.append(dias_semana[dia.weekday()])
        data.append(count)
    
    paginator = Paginator(ventas_qs, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context= {
        "ventas": page_obj,
        "page_obj": page_obj,
        "total_ventas": total_ventas,
        "ventas_hoy": ventas_hoy,
        "ingresos_mes": ingresos_mes,
        "promedio_venta": promedio_venta,
        "labels": labels,
        "data": data,
        "search_query": search_query,
        "from_date": from_date,
        "to_date": to_date,
        "selected_status": status
    }
    return render(request, "admin/gestion_ventas.html", context)


# =====================================================
#        CATEGORÍAS
# =====================================================

@login_required
@user_passes_test(es_admin)
def gestion_categorias(request):
    categorias = Categoria.objects.all().order_by("nombre")
    return render(request, "admin/gestion_categorias.html", {"categorias": categorias})


@login_required
@user_passes_test(es_admin)
def crear_categoria(request):
    if request.method == "POST":
        nombre = request.POST.get("nombre", "").strip()
        if nombre:
            Categoria.objects.create(nombre=nombre)
            messages.success(request, f"Categoría '{nombre}' creada correctamente.")
        else:
            messages.error(request, "El nombre de la categoría no puede estar vacío.")
        return redirect("gestion_categorias")
    return render(request, "admin/crear_categoria.html")


@login_required
@user_passes_test(es_admin)
def editar_categoria(request, categoria_id):
    categoria = get_object_or_404(Categoria, id=categoria_id)
    if request.method == "POST":
        nombre = request.POST.get("nombre", "").strip()
        if nombre:
            categoria.nombre = nombre
            categoria.save()
            messages.success(request, f"Categoría '{nombre}' actualizada correctamente.")
        else:
            messages.error(request, "El nombre de la categoría no puede estar vacío.")
        return redirect("gestion_categorias")
    return render(request, "admin/editar_categoria.html", {"categoria": categoria})


@login_required
@user_passes_test(es_admin)
def eliminar_categoria(request, categoria_id):
    categoria = get_object_or_404(Categoria, id=categoria_id)
    nombre = categoria.nombre
    categoria.delete()
    messages.success(request, f"Categoría '{nombre}' eliminada correctamente.")
    return redirect("gestion_categorias")


# =====================================================
#        ESCANEO Y API
# =====================================================

@login_required
@user_passes_test(es_admin)
def escanear_venta(request):
    return render(request, "admin/escanear_venta.html")


@login_required
@user_passes_test(es_admin)
def buscar_producto_api(request):
    codigo = request.GET.get("codigo", "").strip()
    if not codigo:
        return JsonResponse({"found": False, "error": "Código no proporcionado"})
    try:
        prenda = Prenda.objects.get(codigo_barras=codigo)
        return JsonResponse({
            "found": True,
            "id": prenda.id,
            "nombre": prenda.nombre,
            "precio": float(prenda.precio_descuento if prenda.precio_descuento else prenda.precio),
            "stock": prenda.stock,
            "imagen": prenda.imagen.url if prenda.imagen else None,
        })
    except Prenda.DoesNotExist:
        return JsonResponse({"found": False, "error": "Producto no encontrado"})


@login_required
@user_passes_test(es_cliente)
def simular_pago(request):
    if request.method == "POST":
        cliente = get_object_or_404(Cliente, user=request.user)
        carrito = get_object_or_404(CarritoDeCompras, cliente=cliente)
        items = [i for i in carrito.items.select_related("prenda", "variacion").all() if i.prenda]

        if not items:
            messages.error(request, "Tu carrito está vacío.")
            return redirect("carrito")

        subtotal = sum(i.subtotal for i in items)
        costo_envio = 15000
        total = subtotal + costo_envio

        pedido = Pedido.objects.create(
            cliente=cliente,
            estado="Pagado",
            departamento=request.POST.get("departamento", "N/A"),
            ciudad=request.POST.get("ciudad", "N/A"),
            direccion_envio=request.POST.get("direccion", "N/A"),
            costo_envio=costo_envio
        )

        pago = Pago.objects.create(
            pedido=pedido,
            metodo="Simulación",
            estado="Aprobado"
        )

        venta = Venta.objects.create(
            cliente=cliente,
            subtotal=subtotal,
            descuento=0,
            total=total,
            pago=pago
        )

        for item in items:
            precio = item.prenda.precio_descuento if item.prenda.precio_descuento else item.prenda.precio
            DetalleVenta.objects.create(
                venta=venta,
                prenda=item.prenda,
                variacion=item.variacion,
                cantidad=item.cantidad,
                precio_unitario=precio
            )
            if item.variacion:
                item.variacion.stock -= item.cantidad
                item.variacion.save()
            item.prenda.stock -= item.cantidad
            item.prenda.save()

        carrito.items.all().delete()
        messages.success(request, f"¡Pago simulado con éxito! Pedido #{venta.id} registrado.")
        return redirect("factura_imprimir", venta_id=venta.id)

    return redirect("checkout")


# =====================================================
#        GESTIÓN DE PEDIDOS (ADMIN)
# =====================================================

@login_required
@user_passes_test(es_admin)
def actualizar_estado_pedido(request, pedido_id):
    pedido = get_object_or_404(Pedido, id=pedido_id)
    if request.method == "POST":
        nuevo_estado = request.POST.get("estado")
        estados_validos = [e[0] for e in Pedido.ESTADOS]
        if nuevo_estado in estados_validos:
            pedido.estado = nuevo_estado
            pedido.save()
            messages.success(request, f"Estado del pedido #{pedido_id} actualizado a '{nuevo_estado}'.")
        else:
            messages.error(request, "Estado no válido.")
    return redirect("gestion_ventas")


@login_required
@user_passes_test(es_admin)
def actualizar_envio_pedido(request, pedido_id):
    pedido = get_object_or_404(Pedido, id=pedido_id)
    if request.method == "POST":
        pedido.transportadora = request.POST.get("transportadora", "").strip()
        pedido.guia_rastreo = request.POST.get("guia_rastreo", "").strip()
        pedido.save()
        messages.success(request, f"Información de envío del pedido #{pedido_id} actualizada.")
    return redirect("gestion_ventas")
