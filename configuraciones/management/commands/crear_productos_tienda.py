# configuraciones/management/commands/crear_productos_tienda.py
from pathlib import Path

from django.core.management.base import BaseCommand
from django.conf import settings
from decimal import Decimal
from configuraciones.models import Categoria, Prenda


# Mapeo: nombre del producto -> archivo de imagen en media/productos/
IMAGENES_POR_PRODUCTO = {
    "Vestido floral verano": "vestido_floral.jpg",
    "Vestido noche elegante": "vestido_noche.jpg",
    "Vestido casual": "vestido_casual.jpg",
    "Bolso mano": "bolso_mano.jpg",
    "Bolso cruzado": "bolso_cruzado.jpg",
    "Cinturón clásico": "cinturon_clasico.jpg",
    "Pañoleta": "panolleta.jpg",
}


class Command(BaseCommand):
    help = "Crea categorías y productos de ejemplo para la tienda y el carrusel."

    def handle(self, *args, **options):
        categorias_data = [
            ("Vestidos", [
                ("Vestido floral verano", "Vestido cómodo para el día.", Decimal("89900"), 15),
                ("Vestido noche elegante", "Ideal para ocasiones especiales.", Decimal("129900"), 8),
                ("Vestido casual", "Perfecto para el día a día.", Decimal("59900"), 20),
            ]),
            ("Bolsos", [
                ("Bolso mano", "Bolso de mano elegante.", Decimal("45000"), 12),
                ("Bolso cruzado", "Práctico y moderno.", Decimal("39900"), 18),
            ]),
            ("Accesorios", [
                ("Cinturón clásico", "Acompaña cualquier outfit.", Decimal("24900"), 25),
                ("Pañoleta", "Detalle que marca la diferencia.", Decimal("19900"), 30),
            ]),
        ]

        media_productos = Path(settings.MEDIA_ROOT) / "productos"
        media_productos.mkdir(parents=True, exist_ok=True)

        creados = 0
        for nombre_cat, productos in categorias_data:
            cat, _ = Categoria.objects.get_or_create(nombre=nombre_cat)
            for nombre, desc, precio, stock in productos:
                if not Prenda.objects.filter(nombre=nombre).exists():
                    prenda = Prenda.objects.create(
                        nombre=nombre,
                        descripcion=desc,
                        precio=precio,
                        stock=stock,
                        categoria=cat,
                    )
                    creados += 1
                    self.stdout.write(self.style.SUCCESS(f"  Creado: {nombre}"))

                    archivo = IMAGENES_POR_PRODUCTO.get(nombre)
                    if archivo:
                        ruta = media_productos / archivo
                        if ruta.exists():
                            with open(ruta, "rb") as f:
                                prenda.imagen.save(archivo, f, save=True)
                            self.stdout.write(self.style.SUCCESS(f"    Imagen asignada: {archivo}"))

        self.stdout.write(self.style.SUCCESS(f"\n✅ Listo. Productos creados: {creados}"))
