# CUADRA — Operations Management System
Engineery Solutions S.A.S. · Proyecto de desarrollo de software (Scrum). Django + MySQL + Bootstrap.

## Estructura
```
config/            Configuración de Django (settings, urls, wsgi)
apps/
  autenticacion/   Login, logout, cierre por inactividad          (Sprint 1)
  usuarios/        Usuarios y Sedes (modelos Sede, Usuario)       (Sprint 1-2)
  catalogo/        Productos, tipos de producto, proveedores      (Sprint 3)
  inventario/      Inventario por sede                            (Sprint 3)
  pedidos/         Mesas y pedidos                                (Sprint 4)
  pagos/           Cierre de pedido y pago                        (Sprint 5)
  reportes/        Reportes y exportación a Excel                 (Sprint 5)
  auditoria/       Bitácora de acciones (transversal)
templates/         base.html + una carpeta por módulo
static/            CSS / JS / imágenes propias
deploy/            Ejemplos de Gunicorn y Nginx (despliegue en red local)
scripts/           create_database.sql
docs/              Documentos del proyecto
```
Cada módulo tiene su propio `urls.py` (ya enlazado en `config/urls.py`) para que cada quien
trabaje en su carpeta y se eviten conflictos en Git.

## Puesta en marcha (Windows, PowerShell)
1. Instalar: Python 3.12, MySQL 8 (con MySQL Workbench), Git.
2. Clonar el repositorio y entrar a la carpeta.
3. Crear la base de datos: abrir `scripts/create_database.sql` en MySQL Workbench
   (conexión root), cambiar la clave y ejecutarlo.
4. Entorno virtual y dependencias:
   ```
   python -m venv .venv
   .venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   ```
5. Copiar `.env.example` a `.env` y poner la misma clave del paso 3 en `DB_PASSWORD`.
6. Crear las tablas y cargar datos de prueba:
   ```
   python manage.py migrate
   python manage.py seed_initial
   python manage.py runserver
   ```
   Abrir http://127.0.0.1:8000/django-admin/ (usuario `admin`, clave de prueba `Cuadra2026*`).

## Reglas de trabajo en equipo (Git)
- `main` siempre debe funcionar. Cada historia de usuario en su rama: `feature/HU001-login`.
- Se trabaja con Pull Request y al menos una revisión de un compañero.
- **Migraciones:** los archivos de `migrations/` SÍ se suben a Git. Antes de cambiar un modelo,
  avisar al grupo, hacer `git pull`, y después `makemigrations`. Si dos personas crean migraciones
  en la misma app a la vez, hay conflicto: por eso los modelos ya están todos creados desde el inicio.
- Después de cada `git pull` correr `python manage.py migrate`.
- Nunca subir `.env`.
- La interfaz (todas las pantallas) va en inglés.

## Reglas de negocio que el código debe respetar
Ver Historias de Usuario y Documento de Arquitectura en `docs/`. Puntos que la base de datos NO
puede garantizar sola y se validan en la lógica: un solo pedido abierto por mesa, no vender sin stock,
gana quien pide primero la última unidad (transacción + `select_for_update`), un pedido cerrado no se modifica.
