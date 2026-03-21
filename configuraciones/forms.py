from django import forms
from .models import Prenda, Inventario

class PrendaForm(forms.ModelForm):
    stock = forms.IntegerField(min_value=0, required=True, label="Stock")

    class Meta:
        model = Prenda
        fields = ['nombre', 'descripcion', 'precio', 'categoria']
