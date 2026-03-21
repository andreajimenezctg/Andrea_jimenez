import os
import urllib.request
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.conf import settings
from decimal import Decimal
from configuraciones.models import Categoria, Prenda
from pathlib import Path

# Nuevos productos para agregar
NUEVOS_PRODUCTOS = [
    {
        "categoria": "Vestidos",
        "nombre": "Vestido Midi Seda",
        "descripcion": "Elegante vestido midi de seda ideal para eventos de tarde.",
        "precio": Decimal("145000"),
        "stock": 10,
        "imagen_url": "https://images.unsplash.com/photo-1595777457583-95e059d581b8?q=80&w=1000&auto=format&fit=crop"
    },
    {
        "categoria": "Vestidos",
        "nombre": "Vestido Boho Chic",
        "descripcion": "Vestido estilo bohemio con bordados artesanales.",
        "precio": Decimal("115000"),
        "stock": 12,
        "imagen_url": "https://images.unsplash.com/photo-1515372039744-b8f02a3ae446?q=80&w=1000&auto=format&fit=crop"
    },
    {
        "categoria": "Bolsos",
        "nombre": "Cartera de Cuero Premium",
        "descripcion": "Cartera de cuero legítimo con acabados dorados.",
        "precio": Decimal("185000"),
        "stock": 5,
        "imagen_url": "https://images.unsplash.com/photo-1584917865442-de89df76afd3?q=80&w=1000&auto=format&fit=crop"
    },
    {
        "categoria": "Bolsos",
        "nombre": "Bolso Tote Canvas",
        "descripcion": "Bolso espacioso de tela resistente para el uso diario.",
        "precio": Decimal("65000"),
        "stock": 20,
        "imagen_url": "https://images.unsplash.com/photo-1590874103328-eac38a683ce7?q=80&w=1000&auto=format&fit=crop"
    },
    {
        "categoria": "Accesorios",
        "nombre": "Gafas de Sol Vintage",
        "descripcion": "Gafas de sol con estilo retro y protección UV.",
        "precio": Decimal("55000"),
        "stock": 15,
        "imagen_url": "https://images.unsplash.com/photo-1572635196237-14b3f281503f?q=80&w=1000&auto=format&fit=crop"
    },
    {
        "categoria": "Accesorios",
        "nombre": "Sombrero de Playa",
        "descripcion": "Sombrero de ala ancha tejido a mano.",
        "precio": Decimal("42000"),
        "stock": 8,
        "imagen_url": "https://images.unsplash.com/photo-1521335629791-ce4aec67dd15?q=80&w=1000&auto=format&fit=crop"
    }
]

class Command(BaseCommand):
    help = "Descarga imágenes y agrega nuevos productos a la tienda."

    def handle(self, *args, **options):
        media_productos = Path(settings.MEDIA_ROOT) / "productos"
        media_productos.mkdir(parents=True, exist_ok=True)

        creados = 0
        for item in NUEVOS_PRODUCTOS:
            cat, _ = Categoria.objects.get_or_create(nombre=item["categoria"])
            
            if not Prenda.objects.filter(nombre=item["nombre"]).exists():
                prenda = Prenda.objects.create(
                    nombre=item["nombre"],
                    descripcion=item["descripcion"],
                    precio=item["precio"],
                    stock=item["stock"],
                    categoria=cat
                )
                
                # Descargar imagen usando urllib.request
                try:
                    nombre_archivo = f"{prenda.slug}.jpg"
                    headers = {'User-Agent': 'Mozilla/5.0'}
                    req = urllib.request.Request(item["imagen_url"], headers=headers)
                    with urllib.request.urlopen(req, timeout=10) as response:
                        content = response.read()
                        prenda.imagen.save(nombre_archivo, ContentFile(content), save=True)
                        self.stdout.write(self.style.SUCCESS(f"✓ Creado: {item['nombre']} con imagen."))
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f"✗ Error descargando imagen para {item['nombre']}: {e}"))
                
                creados += 1
            else:
                self.stdout.write(self.style.NOTICE(f"- El producto {item['nombre']} ya existe."))

        self.stdout.write(self.style.SUCCESS(f"\n✅ Proceso terminado. Nuevos productos creados: {creados}"))
