# configuraciones/management/commands/asignar_imagenes_productos.py
"""
Asigna imágenes a los productos de la tienda.
Las imágenes deben estar en media/productos/ con los nombres indicados.
Ejecutar: python manage.py asignar_imagenes_productos
"""
import shutil
from pathlib import Path

from django.core.management.base import BaseCommand
from django.conf import settings
from configuraciones.models import Prenda


# Mapeo: nombre del producto -> archivo en media/productos/
IMAGENES_POR_PRODUCTO = {
    "Vestido floral verano": "vestido_floral.jpg",
    "Vestido noche elegante": "vestido_noche.jpg",
    "Vestido casual": "vestido_casual.jpg",
    "Bolso mano": "bolso_mano.jpg",
    "Bolso cruzado": "bolso_cruzado.jpg",
    "Cinturón clásico": "cinturon_clasico.jpg",
    "Pañoleta": "panolleta.jpg",
}

# Fallback: si no existe en media, usar static/img/
FALLBACK_STATIC = {
    "Vestido floral verano": "vestido.jpeg",
    "Vestido noche elegante": "vestido.jpeg",
    "Vestido casual": "vestido.jpeg",
    "Bolso mano": "bolsos.jpeg",
    "Bolso cruzado": "bolsos.jpeg",
    "Cinturón clásico": "accesorios.jpeg",
    "Pañoleta": "accesorios.jpeg",
}


class Command(BaseCommand):
    help = "Asigna imágenes a los productos de la tienda desde media/productos/"

    def add_arguments(self, parser):
        parser.add_argument(
            "--copiar-desde",
            type=str,
            default=None,
            help="Ruta de carpeta con imágenes para copiar a media/productos/ (ej: ../assets)",
        )

    def handle(self, *args, **options):
        media_productos = Path(settings.MEDIA_ROOT) / "productos"
        media_productos.mkdir(parents=True, exist_ok=True)

        copiar_desde = options.get("copiar_desde")
        if copiar_desde:
            origen = Path(copiar_desde).resolve()
            if origen.exists():
                for archivo in IMAGENES_POR_PRODUCTO.values():
                    src = origen / archivo
                    dst = media_productos / archivo
                    if src.exists():
                        shutil.copy2(src, dst)
                        self.stdout.write(self.style.SUCCESS(f"  Copiado: {archivo}"))
                    else:
                        self.stdout.write(self.style.WARNING(f"  No existe: {src}"))

        static_img = Path(settings.BASE_DIR) / "static" / "img"

        asignados = 0
        for nombre_producto, archivo in IMAGENES_POR_PRODUCTO.items():
            ruta_imagen = media_productos / archivo
            if not ruta_imagen.exists():
                fallback = FALLBACK_STATIC.get(nombre_producto)
                if fallback:
                    ruta_fallback = static_img / fallback
                    if ruta_fallback.exists():
                        ruta_imagen = ruta_fallback
                        archivo = fallback

            if not ruta_imagen.exists():
                self.stdout.write(self.style.WARNING(f"  Imagen no encontrada: {nombre_producto}"))
                continue

            try:
                prenda = Prenda.objects.get(nombre=nombre_producto)
                with open(ruta_imagen, "rb") as f:
                    prenda.imagen.save(archivo, f, save=True)
                asignados += 1
                self.stdout.write(self.style.SUCCESS(f"  Imagen asignada: {nombre_producto}"))
            except Prenda.DoesNotExist:
                self.stdout.write(self.style.WARNING(f"  Producto no encontrado: {nombre_producto}"))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"  Error en {nombre_producto}: {e}"))

        self.stdout.write(self.style.SUCCESS(f"\nListo. Imagenes asignadas: {asignados}"))
