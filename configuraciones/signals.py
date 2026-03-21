from django.db.models.signals import post_save, pre_delete, post_migrate
from django.dispatch import receiver
from django.core.exceptions import PermissionDenied
from django.contrib.auth.models import User, Group
from .models import Cliente, CarritoDeCompras, Venta, DetalleVenta, Prenda


# --------------------------------------------------
# 1. Crear carrito automáticamente al registrar cliente
# --------------------------------------------------

@receiver(post_save, sender=Cliente)
def crear_carrito_para_cliente(sender, instance, created, **kwargs):
    if created:
        CarritoDeCompras.objects.create(cliente=instance)


# --------------------------------------------------
# 2. Actualizar stock cuando se crea un DetalleVenta
# --------------------------------------------------

@receiver(post_save, sender=DetalleVenta)
def descontar_stock(sender, instance, created, **kwargs):
    if created:
        # Descontar de la variación si existe
        if instance.variacion:
            instance.variacion.stock -= instance.cantidad
            if instance.variacion.stock < 0:
                instance.variacion.stock = 0
            instance.variacion.save()
            
        # Descontar del stock global de la prenda
        prenda = instance.prenda
        if prenda:
            prenda.refresh_from_db()
            prenda.stock -= instance.cantidad
            if prenda.stock < 0:
                prenda.stock = 0
            prenda.save()


# --------------------------------------------------
# 3. Archivar producto en lugar de eliminarlo
# --------------------------------------------------

@receiver(pre_delete, sender=Prenda)
def archivar_producto(sender, instance, **kwargs):
    """
    Antes de eliminar una prenda, la archivamos y evitamos su borrado.
    """

    instance.is_archived = True
    instance.save()

    # Evita la eliminación sin romper Django
    raise PermissionDenied("Eliminación bloqueada. El producto fue archivado correctamente.")


# --------------------------------------------------
# 4. Crear Usuario Admin automáticamente (POST MIGRATE)
# --------------------------------------------------

@receiver(post_migrate)
def crear_usuario_admin(sender, **kwargs):
    username = "admin_master"
    password = "admin123"

    # Evitar re-crearlo si ya existe
    if not User.objects.filter(username=username).exists():
        admin_user = User.objects.create_superuser(
            username=username,
            email="admin@system.com",
            password=password
        )
        admin_user.is_active = True
        admin_user.save()
        print("✔ Admin creado automáticamente:", username)
