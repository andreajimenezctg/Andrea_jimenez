from django.contrib import admin
from .models import Cliente, CarritoDeCompras, Pedido, Pago, Prenda, Categoria, Administrador, Inventario, ItemCarrito


# ===========================
#  INVENTARIO INLINE PARA PRENDA
# ===========================

class InventarioInline(admin.StackedInline):
    model = Inventario
    extra = 0
    fk_name = "administrador"   # Inventario tiene FK hacia Administrador, no Prenda
    can_delete = False


# ===========================
#  ADMIN PRENDA (CORRECTO)
# ===========================

@admin.register(Prenda)
class PrendaAdmin(admin.ModelAdmin):
    list_display = ("nombre", "precio", "stock", "is_archived", "created_at")
    list_filter = ("categoria", "is_archived")
    search_fields = ("nombre", "slug")
    ordering = ("-created_at",)


# ===========================
#  INVENTARIO ADMIN (CORRECTO)
# ===========================

@admin.register(Inventario)
class InventarioAdmin(admin.ModelAdmin):
    list_display = ("id", "cantidad_actual", "fecha_actualizacion", "administrador")
    list_filter = ("fecha_actualizacion",)
    search_fields = ("administrador__user__username",)


# ===========================
#  REGISTROS BÁSICOS
# ===========================

admin.site.register(Cliente)
admin.site.register(CarritoDeCompras)
admin.site.register(ItemCarrito)
admin.site.register(Pedido)
admin.site.register(Pago)
admin.site.register(Categoria)
admin.site.register(Administrador)
