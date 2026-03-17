# seed_roles.py
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission

def run():
    User = get_user_model()

    # Crear grupos
    admin_group, _ = Group.objects.get_or_create(name='Administrador')
    client_group, _ = Group.objects.get_or_create(name='Cliente')

    # Permisos para administrador (full CRUD de todos los modelos)
    admin_permissions = Permission.objects.filter(codename__in=[
        'view_user', 'add_user', 'change_user', 'delete_user',
        'view_cliente', 'add_cliente', 'change_cliente', 'delete_cliente',
        'view_administrador', 'add_administrador', 'change_administrador', 'delete_administrador',
        'view_categoria', 'add_categoria', 'change_categoria', 'delete_categoria',
        'view_prenda', 'add_prenda', 'change_prenda', 'delete_prenda',
        'view_inventario', 'add_inventario', 'change_inventario', 'delete_inventario',
        'view_pedido', 'add_pedido', 'change_pedido', 'delete_pedido',
        'view_pago', 'add_pago', 'change_pago', 'delete_pago',
        'view_venta', 'add_venta', 'change_venta', 'delete_venta',
        'view_detalleventa', 'add_detalleventa', 'change_detalleventa', 'delete_detalleventa',
    ])
    admin_group.permissions.set(admin_permissions)

    # Permisos para cliente (solo lectura de productos y ventas propias)
    client_permissions = Permission.objects.filter(codename__in=[
        'view_prenda', 'view_categoria', 'view_venta', 'view_detalleventa'
    ])
    client_group.permissions.set(client_permissions)

    # Crear usuario administrador principal
    admin_user, created = User.objects.get_or_create(username='admin_master')
    admin_user.set_password('admin123')  # 🔑 siempre se actualiza la clave
    admin_user.is_staff = True
    admin_user.is_superuser = True  # 🔑 acceso total
    admin_user.save()
    admin_user.groups.set([admin_group])  # 🔑 evita duplicados

    # Crear usuario cliente de prueba
    client_user, _ = User.objects.get_or_create(username='cliente_test')
    client_user.set_password('cliente123')
    client_user.is_staff = False
    client_user.is_superuser = False
    client_user.save()
    client_user.groups.set([client_group])

    print("✅ Roles, permisos y usuarios creados correctamente.")
