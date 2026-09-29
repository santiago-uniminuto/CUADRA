from django.contrib.auth.models import AbstractUser
from django.db import models


class Sede(models.Model):
    nombre = models.CharField(max_length=100, unique=True)
    direccion = models.CharField(max_length=200)

    def __str__(self):
        return self.nombre


class Usuario(AbstractUser):
    """
    Un único rol activo y una única sede por usuario.
    Estado Active/Inactive = is_active (campo nativo: un usuario inactivo no puede iniciar sesión).
    La contraseña se guarda con hash (PBKDF2).
    El campo 'usuario' del modelo lógico es 'username' de AbstractUser.
    """

    class Rol(models.TextChoices):
        MESERO = "WAITER", "Waiter"
        CAJERO = "CASHIER", "Cashier"
        ADMIN = "ADMIN", "Administrator"

    nombre = models.CharField(max_length=150)
    rol = models.CharField(max_length=10, choices=Rol.choices)
    sede = models.ForeignKey(Sede, on_delete=models.PROTECT, related_name="usuarios")

    def __str__(self):
        return f"{self.nombre} ({self.get_rol_display()})"
