"""
Script para asignar códigos de barras a productos existentes que no lo tienen.
Ejecutar: python manage.py shell < asignar_codigos_barras.py
O copiar y pegar el contenido en el shell de Django.
"""

from configuraciones.models import Prenda

# Obtener todos los productos que no tienen código de barras
productos_sin_codigo = Prenda.objects.filter(codigo_barras__isnull=True) | Prenda.objects.filter(codigo_barras='')

print(f"Encontrados {productos_sin_codigo.count()} productos sin código de barras")

# Asignar código de barras a cada producto
for producto in productos_sin_codigo:
    try:
        producto.codigo_barras = f"AJ-{producto.id:06d}"
        producto.save(update_fields=["codigo_barras"])
        print(f"✓ Asignado código {producto.codigo_barras} a producto '{producto.nombre}' (ID: {producto.id})")
    except Exception as e:
        print(f"✗ Error al asignar código a producto '{producto.nombre}' (ID: {producto.id}): {e}")

print("\n¡Proceso completado!")
