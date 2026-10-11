from django.core.validators import MinValueValidator
from django.db import models


class TipoProducto(models.Model):
    nombre = models.CharField(max_length=80, unique=True)
    activo = models.BooleanField(default=True)

    def __str__(self):
        return self.nombre


class Proveedor(models.Model):
    nombre = models.CharField(max_length=120)
    contacto = models.CharField(max_length=150)
    activo = models.BooleanField(default=True)

    def __str__(self):
        return self.nombre


class Producto(models.Model):
    """Catálogo GLOBAL: compartido por las 3 sedes, mismo precio en todas."""
    nombre = models.CharField(max_length=120)
    valor_compra = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(0)])
    valor_venta = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(0)])
    tipo_producto = models.ForeignKey(TipoProducto, on_delete=models.PROTECT)
    proveedor = models.ForeignKey(Proveedor, on_delete=models.PROTECT)
    # Un producto inactivo no se vende (no sale en inventario/pedidos) pero se conserva en el historial.
    activo = models.BooleanField(default=True)

    def __str__(self):
        return self.nombre
