from django import forms

from .models import Producto, Proveedor, TipoProducto

NUMERIC_ERROR = {"invalid": "The value must be numeric"}


class ProductoForm(forms.ModelForm):
    valor_compra = forms.DecimalField(
        max_digits=12, decimal_places=2, min_value=0, error_messages=NUMERIC_ERROR,
        widget=forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
    )
    valor_venta = forms.DecimalField(
        max_digits=12, decimal_places=2, min_value=0, error_messages=NUMERIC_ERROR,
        widget=forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
    )
    # Campo oculto: solo se marca en el segundo envío, cuando el usuario confirma
    # el aviso de "precio de venta menor al de compra" (HU013 Escenario 4).
    confirm_price = forms.BooleanField(required=False, widget=forms.HiddenInput)

    class Meta:
        model = Producto
        fields = ["nombre", "valor_compra", "valor_venta", "tipo_producto", "proveedor"]
        widgets = {
            "nombre": forms.TextInput(attrs={"class": "form-control"}),
            "tipo_producto": forms.Select(attrs={"class": "form-select"}),
            "proveedor": forms.Select(attrs={"class": "form-select"}),
        }

    def clean_nombre(self):
        nombre = self.cleaned_data["nombre"].strip()
        qs = Producto.objects.filter(nombre__iexact=nombre)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError("A product with this name already exists.")
        return nombre

    def price_warning(self):
        """True si venta < compra y el usuario todavía no confirmó (HU013 Escenario 4)."""
        venta = self.cleaned_data.get("valor_venta")
        compra = self.cleaned_data.get("valor_compra")
        if venta is None or compra is None:
            return False
        return venta < compra and not self.cleaned_data.get("confirm_price")


class ProveedorForm(forms.ModelForm):
    nombre = forms.CharField(
        error_messages={"required": "Name is required"},
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    contacto = forms.CharField(required=False, widget=forms.TextInput(attrs={"class": "form-control"}))

    class Meta:
        model = Proveedor
        fields = ["nombre", "contacto"]

    def clean_nombre(self):
        nombre = self.cleaned_data["nombre"].strip()
        qs = Proveedor.objects.filter(nombre__iexact=nombre)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError("A supplier with this name already exists.")
        return nombre


class TipoProductoForm(forms.ModelForm):
    nombre = forms.CharField(widget=forms.TextInput(attrs={"class": "form-control"}))

    class Meta:
        model = TipoProducto
        fields = ["nombre"]

    def clean_nombre(self):
        nombre = self.cleaned_data["nombre"].strip()
        if TipoProducto.objects.filter(nombre__iexact=nombre).exists():
            raise forms.ValidationError("This product type already exists")
        return nombre
