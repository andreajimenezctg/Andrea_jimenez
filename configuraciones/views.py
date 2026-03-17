from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.models import User, Group
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Sum, Q, Count, F
from configuraciones.models import (
    Cliente, Prenda, Categoria, Venta, DetalleVenta,
    CarritoDeCompras, ItemCarrito, Pago, Pedido
)
from django.http import HttpResponseForbidden, HttpResponse, JsonResponse
import json
from django.views.decorators.csrf import csrf_exempt
from django.core.mail import EmailMessage
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from configuraciones.utils import generate_invoice_pdf, numero_a_letras
from django.conf import settings
import datetime
import logging
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
from django.conf import settings
from pathlib import Path

def migrar_datos_produccion(request):
    """
    Vista temporal para cargar datos, crear superusuario e imágenes en Render
    """
    output = []
    
    # 1. Ejecutar comando de creación de productos (crear_productos_tienda)
    try:
        call_command('crear_productos_tienda')
        output.append("✅ Productos y categorías base creados.")
    except Exception as e:
        output.append(f"❌ Error en crear_productos_tienda: {str(e)}")

    # 2. Forzar asignación de imágenes desde static/img a los productos creados
    try:
        # Mapeo de categorías a imágenes en static/img/
        mapeo_imagenes = {
            "Vestidos": "vestido.jpeg",
            "Bolsos": "bolsos.jpeg",
            "Accesorios": "accesorios.jpeg",
        }
        
        # Productos específicos por nombre
        mapeo_productos = {
            "Vestido floral verano": "vestido.jpeg",
            "Vestido noche elegante": "vestido.jpeg",
            "Vestido casual": "vestido.jpeg",
            "Bolso mano": "bolsos.jpeg",
            "Bolso cruzado": "bolsos.jpeg",
            "Cinturón clásico": "accesorios.jpeg",
            "Pañoleta": "accesorios.jpeg",
        }
        
        media_productos = Path(settings.MEDIA_ROOT) / "productos"
        media_productos.mkdir(parents=True, exist_ok=True)
        
        # 1. Asignar por nombre de producto
        for nombre_prod, nombre_img in mapeo_productos.items():
            productos = Prenda.objects.filter(nombre=nombre_prod)
            ruta_img_static = Path(settings.BASE_DIR) / "static" / "img" / nombre_img
            if ruta_img_static.exists():
                for p in productos:
                    with open(ruta_img_static, "rb") as f:
                        p.imagen.save(f"{nombre_img}", File(f), save=True)
        
        # 2. Asignar por categoría (respaldo)
        for nombre_cat, nombre_img in mapeo_imagenes.items():
            productos = Prenda.objects.filter(categoria__nombre=nombre_cat, imagen='')
            ruta_img_static = Path(settings.BASE_DIR) / "static" / "img" / nombre_img
            
            if ruta_img_static.exists():
                for p in productos:
                    with open(ruta_img_static, "rb") as f:
                        p.imagen.save(f"{nombre_img}", File(f), save=True)
                output.append(f"✅ Imágenes sincronizadas.")
                
    except Exception as e:
        output.append(f"❌ Error al asignar imágenes: {str(e)}")

    # 3. Crear Superusuario si no existe
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
# ====================================================="}]}

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
                [settings.EMAIL_HOST_USER] # Se envía al admin
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
    
    # Calcular cuotas (ej: 12 cuotas)
    precio_base = producto.precio_descuento if producto.precio_descuento else producto.precio
    cuotas_12 = round(precio_base / 12, 2)
    
    # Productos relacionados (misma categoría)
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
    # Aseguramos que el cliente exista para evitar "No Cliente matches the given query"
    cliente, created = Cliente.objects.get_or_create(
        user=request.user,
        defaults={'telefono': 'N/A', 'direccion': 'N/A'}
    )
    
    carrito, created = CarritoDeCompras.objects.get_or_create(cliente=cliente)

    producto = get_object_or_404(Prenda, id=prenda_id)
    variacion_id = request.POST.get("variacion_id")
    variacion = None
    
    if variacion_id:
        from configuraciones.models import VariacionPrenda
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

    items = carrito.items.all()
    total = sum(item.subtotal for item in items)

    return render(request, "cliente/carrito.html", {
        "carrito_items": items,
        "total": total
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
def eliminar_item_carrito(request, item_id):
    item = get_object_or_404(ItemCarrito, id=item_id)
    if request.method == "POST":
        item.delete()
    return redirect("carrito")


# =====================================================
#        CHECKOUT (PAGO PSE)
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

    total = sum(i.subtotal for i in items)
    return render(request, "cliente/checkout.html", {
        "carrito_items": items,
        "total": total,
        "paypal_client_id": settings.PAYPAL_CLIENT_ID,
        "paypal_currency": settings.PAYPAL_CURRENCY,
    })


# =====================================================
#        CONFIRMAR COMPRA (PROCESO PSE)
# =====================================================

@login_required
@user_passes_test(es_cliente)
def confirmar_compra(request):
    cliente = get_object_or_404(Cliente, user=request.user)
    carrito = get_object_or_404(CarritoDeCompras, cliente=cliente)
    items = [i for i in carrito.items.select_related("prenda", "variacion").all() if i.prenda]

    if not items:
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

        costo_envio = 15000 # Costo fijo de envío para este ejemplo
        total = subtotal - descuento + costo_envio

        # 1. Crear el Pedido con info de envío
        pedido = Pedido.objects.create(
            cliente=cliente,
            estado="Pagado",
            departamento=departamento,
            ciudad=ciudad,
            direccion_envio=direccion,
            costo_envio=costo_envio
        )

        # 2. Crear el Pago (Simulado PSE)
        pago = Pago.objects.create(
            pedido=pedido,
            metodo="PSE",
            estado="Aprobado"
        )

        # 3. Crear la Venta
        venta = Venta.objects.create(
            cliente=cliente,
            subtotal=subtotal,
            descuento=descuento,
            total=total,
            cupon=cupon_obj,
            pago=pago
        )

        # 4. Crear Detalles de Venta y Descontar Stock
        for item in items:
            precio = item.prenda.precio_descuento if item.prenda.precio_descuento else item.prenda.precio
            DetalleVenta.objects.create(
                venta=venta,
                prenda=item.prenda,
                variacion=item.variacion,
                cantidad=item.cantidad,
                precio_unitario=precio
            )

        # 5. Vaciar el carrito
        carrito.items.all().delete()

        # 6. Intentar enviar correo con factura (Opcional según config)
        if cliente.user.email:
            try:
                # DEBUG: Info inicial
                logger.info(f"--- INICIO PROCESO CORREO VENTA #{venta.id} ---")
                logger.info(f"Cliente: {cliente.user.username}, Email: {cliente.user.email}")
                
                pdf_buffer = generate_invoice_pdf(venta)
                pdf_content = pdf_buffer.getvalue()
                logger.info(f"PDF generado. Tamaño: {len(pdf_content)} bytes")
                
                # Contexto para el correo profesional HTML
                context = {
                    'cliente': cliente,
                    'venta': venta,
                    'total': total,
                    'metodo_pago': pago.metodo,
                    'site_url': settings.SITE_URL,
                    'current_year': datetime.datetime.now().year,
                }
                
                # Renderizar el correo usando la plantilla
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
                     
                     # Intentar enviar
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

        messages.success(request, f"¡Pago PSE Exitoso! Venta #{venta.id} generada.")
        return redirect("factura_imprimir", venta_id=venta.id)

    return redirect("checkout")


@csrf_exempt
@login_required
def paypal_capture(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            order_id = data.get("orderID")
            shipping_data = data.get("shippingData", {})
            
            cliente = get_object_or_404(Cliente, user=request.user)
            carrito = get_object_or_404(CarritoDeCompras, cliente=cliente)
            items = [i for i in carrito.items.select_related("prenda", "variacion").all() if i.prenda]
            
            if not items:
                return JsonResponse({"status": "error", "message": "Carrito vacío"}, status=400)
                
            subtotal = sum(i.subtotal for i in items)
            # El descuento se podría manejar aquí si se envió el cupón
            descuento = 0 
            costo_envio = 15000
            total = subtotal - descuento + costo_envio
            
            # 1. Crear Pedido
            pedido = Pedido.objects.create(
                cliente=cliente,
                estado="Pagado",
                departamento=shipping_data.get("departamento", "N/A"),
                ciudad=shipping_data.get("ciudad", "N/A"),
                direccion_envio=shipping_data.get("direccion", "N/A"),
                costo_envio=costo_envio
            )
            
            # 2. Crear Pago
            pago = Pago.objects.create(
                pedido=pedido,
                metodo="PayPal",
                estado="Aprobado",
                # Podrías guardar el order_id de paypal en un campo si existiera
            )
            
            # 3. Crear Venta
            venta = Venta.objects.create(
                cliente=cliente,
                subtotal=subtotal,
                descuento=descuento,
                total=total,
                pago=pago
            )
            
            # 4. Detalles y Stock
            for item in items:
                precio = item.prenda.precio_descuento if item.prenda.precio_descuento else item.prenda.precio
                DetalleVenta.objects.create(
                    venta=venta,
                    prenda=item.prenda,
                    variacion=item.variacion,
                    cantidad=item.cantidad,
                    precio_unitario=precio
                )
                # Actualizar stock
                if item.prenda.stock >= item.cantidad:
                    item.prenda.stock -= item.cantidad
                    item.prenda.save()
            
            # 5. Vaciar Carrito
            carrito.items.all().delete()
            
            # 6. Enviar Correo (reutilizando lógica existente)
            if cliente.user.email:
                try:
                    pdf_buffer = generate_invoice_pdf(venta)
                    pdf_content = pdf_buffer.getvalue()
                    context = {
                        'cliente': cliente,
                        'venta': venta,
                        'total': total,
                        'metodo_pago': "PayPal",
                        'site_url': settings.SITE_URL,
                        'current_year': datetime.datetime.now().year,
                    }
                    html_content = render_to_string('email/email_factura.html', context)
                    email = EmailMessage(
                        f"Factura de Compra #{venta.id} - Andrea Jiménez",
                        html_content,
                        settings.EMAIL_HOST_USER,
                        [cliente.user.email]
                    )
                    email.content_subtype = "html"
                    if len(pdf_content) > 0:
                        email.attach(f"Factura_{venta.id}.pdf", pdf_content, "application/pdf")
                        email.send(fail_silently=True)
                except Exception as e:
                    logger.error(f"Error correo PayPal: {str(e)}")
            
            return JsonResponse({"status": "success", "venta_id": venta.id})
            
        except Exception as e:
            logger.error(f"Error captura PayPal: {str(e)}")
            return JsonResponse({"status": "error", "message": str(e)}, status=500)
            
    return JsonResponse({"status": "error", "message": "Método no permitido"}, status=405)


@login_required
def factura_imprimir(request, venta_id):
    venta = get_object_or_404(Venta, id=venta_id)
    # Solo el dueño de la venta o un admin pueden ver la factura
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
            "codigo_barras": d.prenda.codigo_barras if d.prenda else f"AJ-{d.prenda.id:04d}"
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
    })


@login_required
def descargar_factura_pdf(request, venta_id):
    venta = get_object_or_404(Venta, id=venta_id)
    # Solo el dueño de la venta o un admin pueden descargar la factura
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
    # 1. Estadísticas Generales
    total_productos = Prenda.objects.filter(is_archived=False).count()
    total_ventas = Venta.objects.count()
    ingresos_totales = Venta.objects.aggregate(total=Sum('total'))['total'] or 0
    total_clientes = Cliente.objects.count()

    # 2. Estadísticas Mensuales (Mes actual)
    hoy = datetime.datetime.now()
    inicio_mes = hoy.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    
    productos_mes = Prenda.objects.filter(created_at__gte=inicio_mes, is_archived=False).count()
    ventas_mes = Venta.objects.filter(fecha_venta__gte=inicio_mes).count()
    clientes_mes = User.objects.filter(date_joined__gte=inicio_mes, groups__name="Cliente").count()

    # 3. Gráfico de Tendencia de Ventas (Últimos 12 meses)
    ventas_mensuales = []
    meses_nombres = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic']
    labels_grafica = []
    
    # Obtener datos de los últimos 12 meses incluyendo el actual
    for i in range(11, -1, -1):
        # Calcular mes y año para cada uno de los últimos 12 meses
        mes_idx = (hoy.month - i - 1) % 12
        anio_adj = hoy.year if (hoy.month - i) > 0 else hoy.year - 1
        
        ventas_count = Venta.objects.filter(fecha_venta__month=mes_idx + 1, fecha_venta__year=anio_adj).count()
        ventas_mensuales.append(ventas_count)
        labels_grafica.append(meses_nombres[mes_idx])

    # 4. Gráfico de Distribución por Categorías
    # Filtramos categorías que tengan al menos una unidad vendida para que la gráfica sea clara
    categorias_qs = Categoria.objects.annotate(
        num_ventas=Sum('prendas__detalleventa__cantidad')
    ).filter(num_ventas__gt=0)
    
    categorias_labels = [cat.nombre for cat in categorias_qs]
    total_unidades = sum(cat.num_ventas or 0 for cat in categorias_qs)
    
    if total_unidades > 0:
        categorias_data = [round((cat.num_ventas or 0) * 100 / total_unidades, 1) for cat in categorias_qs]
    else:
        # Si no hay ventas en ninguna categoría, enviamos datos vacíos
        categorias_labels = []
        categorias_data = []

    # 5. Actividad Reciente y Alertas
    ventas_recientes = Venta.objects.select_related('cliente__user').order_by('-fecha_venta')[:5]
    productos_bajo_stock = Prenda.objects.filter(stock__lt=5, is_archived=False).order_by('stock')[:5]

    # 6. Indicadores de Progreso
    # Stock
    productos_en_stock = Prenda.objects.filter(stock__gt=0, is_archived=False).count()
    if total_productos > 0:
        stock_porcentaje = round(productos_en_stock * 100 / total_productos, 1)
    else:
        stock_porcentaje = 0
    # El offset de SVG funciona al revés: 0 es lleno, 251.2 es vacío
    stock_offset = 251.2 * (1 - (stock_porcentaje / 100))

    # Meta de ventas
    meta_ventas = 100
    ventas_actuales = ventas_mes
    if meta_ventas > 0:
        porcentaje_meta = min(round(ventas_actuales * 100 / meta_ventas, 1), 100)
    else:
        porcentaje_meta = 0
    meta_ventas_offset = 251.2 * (1 - (porcentaje_meta / 100))

    # Productos en Oferta
    productos_oferta = Prenda.objects.filter(precio_descuento__isnull=False, is_archived=False).count()
    if total_productos > 0:
        ofertas_porcentaje = round(productos_oferta * 100 / total_productos, 1)
    else:
        ofertas_porcentaje = 0
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


@login_required
@user_passes_test(es_admin)
def gestion_productos(request):
    # 1. Filtros y Búsqueda
    search_query = request.GET.get('search', '')
    category_id = request.GET.get('categoria', '')
    stock_status = request.GET.get('stock', '')
    sort_by = request.GET.get('sort', '-id')
    order = request.GET.get('order', 'desc')
    
    # Mapeo de campos para ordenamiento seguro
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
    
    # Aplicar búsqueda
    if search_query:
        productos_qs = productos_qs.filter(
            Q(nombre__icontains=search_query) | 
            Q(codigo_barras__icontains=search_query)
        )
    
    # Aplicar filtro de categoría
    if category_id:
        try:
            category_id = int(category_id)
            productos_qs = productos_qs.filter(categoria_id=category_id)
        except (ValueError, TypeError):
            category_id = ''
        
    # Aplicar filtro de stock
    if stock_status == 'disponible':
        productos_qs = productos_qs.filter(stock__gt=0, is_archived=False)
    elif stock_status == 'bajo':
        productos_qs = productos_qs.filter(stock__lte=5, stock__gt=0, is_archived=False)
    elif stock_status == 'agotado':
        productos_qs = productos_qs.filter(stock=0)

    # 2. Estadísticas para los mini-contadores (siempre sobre el total)
    total_productos = Prenda.objects.count()
    activos = Prenda.objects.filter(is_archived=False, stock__gt=0).count()
    bajo_stock = Prenda.objects.filter(stock__lte=5, is_archived=False, stock__gt=0).count()
    en_oferta = Prenda.objects.filter(precio_descuento__isnull=False, is_archived=False).count()

    # 3. Paginación
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
    # 1. Filtros y Búsqueda
    search_query = request.GET.get('search', '')
    status = request.GET.get('status', '')
    sort = request.GET.get('sort', 'reciente')
    
    # Anotar con datos de compras
    clientes_qs = Cliente.objects.annotate(
        total_compras=Count('ventas'),
        total_gastado=Sum('ventas__total'),
        fecha_registro=F('user__date_joined')
    ).all()
    
    # Aplicar filtros
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
        
    # Ordenamiento
    if sort == 'nombre':
        clientes_qs = clientes_qs.order_by('user__first_name')
    elif sort == 'compras':
        clientes_qs = clientes_qs.order_by('-total_compras')
    else: # reciente
        clientes_qs = clientes_qs.order_by('-user__date_joined')
        
    # Estadísticas
    total_clientes = Cliente.objects.count()
    clientes_mes = Cliente.objects.filter(user__date_joined__month=datetime.datetime.now().month).count()
    clientes_con_compras = Cliente.objects.annotate(num_compras=Count('ventas')).filter(num_compras__gt=0).count()
    
    # Cliente Top
    cliente_top_obj = Cliente.objects.annotate(gastado=Sum('ventas__total')).order_by('-gastado').first()
    cliente_top = {
        'nombre': cliente_top_obj.user.first_name or cliente_top_obj.user.username if cliente_top_obj else "-"
    }

    # Paginación
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
    
    # 1. Filtros y Búsqueda
    search_query = request.GET.get('search', '')
    from_date = request.GET.get('from', '')
    to_date = request.GET.get('to', '')
    status = request.GET.get('status', '')
    
    ventas_qs = Venta.objects.all().order_by("-fecha_venta")
    
    # Aplicar filtros
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
    
    # 2. Estadísticas para los mini-contadores
    total_ventas = Venta.objects.count()
    ventas_hoy = Venta.objects.filter(fecha_venta__date=hoy.date()).count()
    ingresos_mes = Venta.objects.filter(fecha_venta__gte=inicio_mes).aggregate(total=Sum('total'))['total'] or 0
    promedio_venta = ingresos_mes / total_ventas if total_ventas > 0 else 0
    
    # 3. Datos para el gráfico (Últimos 7 días)
    labels = []
    data = []
    dias_semana = ['Lun', 'Mar', 'Mie', 'Jue', 'Vie', 'Sab', 'Dom']
    
    for i in range(6, -1, -1):
        dia = hoy - datetime.timedelta(days=i)
        count = Venta.objects.filter(fecha_venta__date=dia.date()).count()
        labels.append(dias_semana[dia.weekday()])
        data.append(count)
    
    # 4. Paginación
    paginator = Paginator(ventas_qs, 10) # 10 ventas por página
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        "ventas": page_obj,  # Usamos el objeto de página en lugar del queryset completo
        "page_obj": page_obj,
        "total_ventas": total_ventas,
        "ventas_hoy": ventas_hoy,
        "ingresos_mes": ingresos_mes,
        "promedio_venta": promedio_venta,
        "labels": labels,
        "data": data,
        "search_query": search_query,
    }
    
    return render(request, "admin/gestion_ventas.html", context)


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

        Categoria.objects.create(nombre=nombre)

        messages.success(request, "Categoría creada correctamente.")
        return redirect("gestion_categorias")

    return render(request, "admin/crear_categoria.html")


@login_required
@user_passes_test(es_admin)
def editar_categoria(request, categoria_id):
    categoria = get_object_or_404(Categoria, id=categoria_id)

    if request.method == "POST":
        categoria.nombre = request.POST.get("nombre", "").strip()
        categoria.save()
        return redirect("gestion_categorias")

    return render(request, "admin/editar_categoria.html", {"categoria": categoria})


@login_required
@user_passes_test(es_admin)
def eliminar_categoria(request, categoria_id):
    categoria = get_object_or_404(Categoria, id=categoria_id)

    if categoria.prendas.exists():
        messages.error(request, "No se puede eliminar una categoría con productos asociados.")
        return redirect("gestion_categorias")

    categoria.delete()
    messages.success(request, "Categoría eliminada correctamente.")
    return redirect("gestion_categorias")


# =====================================================
#        PERFIL CLIENTE
# =====================================================

@login_required
@user_passes_test(es_cliente)
def perfil_cliente(request):
    cliente, created = Cliente.objects.get_or_create(
        user=request.user,
        defaults={'telefono': 'N/A', 'direccion': 'N/A'}
    )
    return render(request, "cliente/perfil_cliente.html", {"cliente": cliente})


@login_required
@user_passes_test(es_cliente)
def editar_perfil(request):
    cliente, created = Cliente.objects.get_or_create(
        user=request.user,
        defaults={'telefono': 'N/A', 'direccion': 'N/A'}
    )
    if request.method == "POST":
        cliente.user.first_name = request.POST.get("first_name", "")
        cliente.user.email = request.POST.get("email", "")
        cliente.telefono = request.POST.get("telefono", "")
        cliente.direccion = request.POST.get("direccion", "")

        cliente.user.save()
        cliente.save()

        return redirect("perfil_cliente")

    return render(request, "cliente/editar_perfil.html", {"cliente": cliente})


# =====================================================
#        MIS VENTAS
# =====================================================

@login_required
@user_passes_test(es_cliente)
@login_required
@user_passes_test(es_cliente)
def mis_ventas(request):
    cliente = get_object_or_404(Cliente, user=request.user)
    ventas = Venta.objects.filter(cliente=cliente).select_related('pago__pedido').order_by("-fecha_venta")

    return render(request, "cliente/mis_ventas.html", {"ventas": ventas})

# =====================================================
#        CATÁLOGO (FALTABA)
# =====================================================

@login_required
@user_passes_test(es_admin)
def actualizar_estado_pedido(request, pedido_id):
    pedido = get_object_or_404(Pedido, id=pedido_id)
    if request.method == "POST":
        nuevo_estado = request.POST.get("nuevo_estado")
        if nuevo_estado in dict(Pedido.ESTADOS):
            pedido.estado = nuevo_estado
            pedido.save()
            messages.success(request, f"Estado del pedido #{pedido.id} actualizado a {nuevo_estado}.")
        else:
            messages.error(request, "Estado no válido.")
    return redirect("gestion_ventas")


@login_required
@user_passes_test(es_admin)
def actualizar_envio_pedido(request, pedido_id):
    pedido = get_object_or_404(Pedido, id=pedido_id)
    if request.method == "POST":
        pedido.transportadora = request.POST.get("transportadora")
        pedido.guia_rastreo = request.POST.get("guia_rastreo")
        pedido.save()
        messages.success(request, f"Información de envío del pedido #{pedido.id} actualizada.")
    return redirect("gestion_ventas")


@login_required
@user_passes_test(es_cliente)
def catalogo(request):
    prendas = Prenda.objects.filter(is_archived=False).order_by("nombre")
    return render(request, "cliente/catalogo.html", {"prendas": prendas})
@login_required
@user_passes_test(es_admin)
def escanear_venta(request):
    clientes = Cliente.objects.all().order_by("user__username")
    return render(request, 'admin/escanear_venta.html', {'clientes': clientes})

from django.http import JsonResponse

@login_required
@user_passes_test(es_admin)
def buscar_producto_api(request):
    barcode = request.GET.get('barcode')
    q = request.GET.get('q')
    
    if barcode:
        producto = Prenda.objects.filter(codigo_barras=barcode, is_archived=False).first()
        if producto:
            return JsonResponse({
                'id': producto.id,
                'nombre': producto.nombre,
                'codigo': producto.codigo_barras,
                'precio': float(producto.precio),
                'stock': producto.stock
            })
        return JsonResponse({'error': 'Producto no encontrado'}, status=404)
    
    if q:
        productos = Prenda.objects.filter(nombre__icontains=q, is_archived=False)[:10]
        results = [{
            'id': p.id,
            'nombre': p.nombre,
            'precio': float(p.precio),
            'stock': p.stock
        } for p in productos]
        return JsonResponse(results, safe=False)
        
    return JsonResponse({'error': 'Parámetros insuficientes'}, status=400)

@login_required
@user_passes_test(es_cliente)
def simular_pago(request):
    total = request.GET.get('total', 0)
    metodo = request.GET.get('metodo', 'PSE')
    return render(request, 'cliente/simular_pago.html', {
        'total': total,
        'metodo': metodo
    })
