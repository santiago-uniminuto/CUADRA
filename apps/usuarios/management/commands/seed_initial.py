"""
Carga datos mínimos para poder trabajar en desarrollo:
  - Las 3 sedes de CUADRA (las direcciones son marcadores: se actualizan luego)
  - 1 administrador, y 1 mesero + 1 cajero por sede
Uso:  python manage.py seed_initial
SOLO PARA DESARROLLO: las contraseñas son de prueba.
"""
from django.core.management.base import BaseCommand

from apps.usuarios.models import Sede, Usuario

DEV_PASSWORD = "Cuadra2026*"


class Command(BaseCommand):
    help = "Seed initial development data (branches and test users)."

    def handle(self, *args, **options):
        sedes = {}
        for nombre in ("Zona T", "Galerias", "Restrepo"):
            sedes[nombre], _ = Sede.objects.get_or_create(
                nombre=nombre, defaults={"direccion": f"{nombre}, Bogota (pending)"}
            )

        admin, created = Usuario.objects.get_or_create(
            username="admin",
            defaults={"nombre": "Administrator", "rol": Usuario.Rol.ADMIN, "sede": sedes["Zona T"],
                      "is_staff": True, "is_superuser": True},
        )
        if created:
            admin.set_password(DEV_PASSWORD)
            admin.save()

        for clave, sede in (("zonat", "Zona T"), ("galerias", "Galerias"), ("restrepo", "Restrepo")):
            for rol, prefijo in ((Usuario.Rol.MESERO, "waiter"), (Usuario.Rol.CAJERO, "cashier")):
                u, created = Usuario.objects.get_or_create(
                    username=f"{prefijo}_{clave}",
                    # Meseros y cajeros NO son staff: no deben poder entrar a /django-admin/.
                    defaults={"nombre": f"{prefijo.title()} {sede}", "rol": rol, "sede": sedes[sede], "is_staff": False},
                )
                if created:
                    u.set_password(DEV_PASSWORD)
                    u.save()

        self.stdout.write(self.style.SUCCESS(f"Seed done. Test password for all users: {DEV_PASSWORD}"))
