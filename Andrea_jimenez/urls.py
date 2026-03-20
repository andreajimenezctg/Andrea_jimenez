from django.contrib import admin
from django.urls import path, re_path
from django.views.generic.base import RedirectView
from django.views.static import serve
from configuraciones import views
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth import views as auth_views

urlpatterns = [
    # ----------------------------
    # PÁGINA PRINCIPAL
    # ----------------------------
    path("", views.home, name="home"),
    path("home/", views.home, name="home_redirect"),
    path("favicon.ico", RedirectView.as_view(url=settings.STATIC_URL + "img/favicon-round.png")),

    # ----------------------------
    # ADMIN DE DJANGO
    # ----------------------------
    path("admin/", admin.site.urls),

    # ----------------------------
    # AUTENTICACIÓN
    # ----------------------------
    path("migrar-produccion-secreto-xyz/", views.migrar_datos_produccion, name="migrar_produccion"),
    path("login/", views.inicio_sesion, name="login"),
    path("registro/", views.registro, name="registro"),
    path("logout/", views.cerrar_sesion, name="logout"),

    # Recuperación de contraseña
    path("password_reset/", 
         auth_views.PasswordResetView.as_view(template_name="registration/password_reset.html"),
         name="password_reset"),
    path("password_reset/done/",
         auth_views.PasswordResetDoneView.as_view(template_name="registration/password_reset_done.html"),
         name="password_reset_done"),
    path("reset/<uidb64>/<token>/",
         auth_views.PasswordResetConfirmView.as_view(template_name="registration/password_reset_confirm.html"),
         name="password_reset_confirm"),
    path("reset/done/",
         auth_views.PasswordResetCompleteView.as_view(template_name="registration/password_reset_complete.html"),
         name="password_reset_complete"),

    # ----------------------------
    # PÁGINAS PÚBLICAS
    # ----------------------------
    path("tienda/", views.tienda, name="tienda"),
    path("oferta/", views.oferta, name="oferta"),
    path("atencion/", views.atencion, name="atencion"),
    path("distribuidores/", views.distribuidores, name="distribuidores"),
    path("producto/<slug:slug>/", views.detalle_producto, name="detalle_producto"),

    # ----------------------------
    # PANEL DE USUARIOS
    # ----------------------------
    path("panel_admin/", views.panel_admin, name="panel_admin"),
    path("panel_cliente/", views.panel_cliente, name="panel_cliente"),

    # ----------------------------
    # CLIENTE – PERFIL Y COMPRAS
    # ----------------------------
    path("perfil/", views.perfil_cliente, name="perfil_cliente"),
    path("editar_perfil/", views.editar_perfil, name="editar_perfil"),
    path("catalogo/", views.catalogo, name="catalogo"),
    path("mis_ventas/", views.mis_ventas, name="mis_ventas"),

    # ----------------------------
    # CARRITO DE COMPRAS
    # ----------------------------
    path("carrito/", views.carrito, name="carrito"),
    path("carrito/agregar/<int:prenda_id>/", views.agregar_al_carrito, name="agregar_al_carrito"),
    path("carrito/restar/<int:item_id>/", views.restar_del_carrito, name="restar_item"),
    path("carrito/eliminar/<int:item_id>/", views.eliminar_item_carrito, name="eliminar_item_carrito"),
    path("carrito/actualizar/<int:item_id>/", views.actualizar_cantidad, name="actualizar_cantidad"),
    path("checkout/", views.checkout, name="checkout"),
    path("confirmar/", views.confirmar_compra, name="confirmar_compra"),
    path("confirmar_compra/", views.confirmar_compra, name="confirmar_compra_alt"),
    path("api/crear-venta-preliminar/", views.api_crear_venta_preliminar, name="api_crear_venta_preliminar"),
    path("factura/<int:venta_id>/", views.factura_imprimir, name="factura_imprimir"),
    path("descargar_factura/<int:venta_id>/", views.descargar_factura_pdf, name="descargar_factura_pdf"),

    # ----------------------------
    # ADMIN – GESTIÓN
    # ----------------------------
    path("gestion_productos/", views.gestion_productos, name="gestion_productos"),
    path("crear_producto/", views.crear_producto, name="crear_producto"),
    path("editar_producto/<int:prenda_id>/", views.editar_producto, name="editar_producto"),
    path("eliminar_producto/<int:prenda_id>/", views.eliminar_producto, name="eliminar_producto"),

    path("gestion_clientes/", views.gestion_clientes, name="gestion_clientes"),
    path("detalle_cliente/<int:cliente_id>/", views.detalle_cliente_ajax, name="detalle_cliente_ajax"),
    path("gestion_ventas/", views.gestion_ventas, name="gestion_ventas"),

    # Categorías
    path("gestion_categorias/", views.gestion_categorias, name="gestion_categorias"),
    path("crear_categoria/", views.crear_categoria, name="crear_categoria"),
    path("editar_categoria/<int:categoria_id>/", views.editar_categoria, name="editar_categoria"),
    path("eliminar_categoria/<int:categoria_id>/", views.eliminar_categoria, name="eliminar_categoria"),
    path('escanear-venta/', views.escanear_venta, name='escanear_venta'),
    path('api/buscar_producto/', views.buscar_producto_api, name='buscar_producto_api'),
    path('simular_pago/', views.simular_pago, name='simular_pago'),
    path('pedido/actualizar_estado/<int:pedido_id>/', views.actualizar_estado_pedido, name='actualizar_estado_pedido'),
    path('pedido/actualizar_envio/<int:pedido_id>/', views.actualizar_envio_pedido, name='actualizar_envio_pedido'),
]

# ----------------------------
# ARCHIVOS MEDIA
# ----------------------------
urlpatterns += [
    re_path(r'^media/(?P<path>.*)$', serve, {'document_root': settings.MEDIA_ROOT}),
]
