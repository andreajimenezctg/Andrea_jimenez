from django.core.management.base import BaseCommand
from configuraciones.models import Prenda

class Command(BaseCommand):
    help = 'Genera codigos de barras e imagenes para productos que no los tienen'

    def handle(self, *args, **options):
        productos = Prenda.objects.filter(is_archived=False)
        total = productos.count()
        self.stdout.write(f"Iniciando generacion de codigos para {total} productos...")
        
        actualizados = 0
        for producto in productos:
            # Forzamos el guardado para que el metodo save() genere el codigo e imagen
            # si faltan.
            producto.save()
            actualizados += 1
            if actualizados % 10 == 0:
                self.stdout.write(f"Procesados {actualizados}/{total}...")

        self.stdout.write(self.style.SUCCESS(f"¡Exito! Se procesaron {actualizados} productos."))
