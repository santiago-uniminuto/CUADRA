from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render

from apps.algoritmos.ordenamiento import binary_search, selection_sort
from apps.auditoria.utils import registrar
from apps.usuarios.decorators import role_required

from .forms import ProductoForm, ProveedorForm, TipoProductoForm
from .models import Producto, Proveedor, TipoProducto


# ---------------------------------------------------------------- Producto (HU013, HU014, HU015)
@role_required("ADMIN")
def producto_list(request):
    """
    HU015 — Listar productos, con búsqueda por nombre (Escenarios 1-3).
    Orden final con ordenamiento por selección (requisito de algoritmos
    funcionales del proyecto), por precio de venta ascendente; a igual precio, por nombre.
    """
    query = request.GET.get("q", "").strip()
    productos_qs = Producto.objects.select_related("tipo_producto", "proveedor")
    if query.startswith("#") and query[1:].isascii() and query[1:].isdecimal():
        # Búsqueda exacta por código: el índice binario requiere ordenar por PK,
        # no por precio. El catálogo es global y solo ADMIN accede a esta vista.
        product_id = int(query[1:])
        by_code = list(productos_qs.order_by("pk"))
        found = binary_search(by_code, product_id, key=lambda p: p.pk)
        productos = [found] if found is not None else []
    else:
        if query:
            productos_qs = productos_qs.filter(nombre__icontains=query)
        productos = selection_sort(productos_qs, key=lambda p: (p.valor_venta, p.nombre.lower()))
    return render(request, "catalogo/producto_list.html", {"productos": productos, "query": query})


@role_required("ADMIN")
def producto_create(request):
    """HU013 — Crear producto (Escenarios 1-6)."""
    warning = False
    if request.method == "POST":
        form = ProductoForm(request.POST)
        if form.is_valid():
            if form.price_warning():
                warning = True
            else:
                producto = form.save()
                registrar(request, "CREATE", "Producto", producto, f"Created product {producto.nombre}")
                messages.success(request, "Product created successfully.")
                return redirect("catalogo:producto_list")
    else:
        form = ProductoForm()
    return render(request, "catalogo/producto_form.html",
                  {"form": form, "warning": warning, "title": "New Product"})


@role_required("ADMIN")
def producto_edit(request, pk):
    """HU014 — Editar producto (Escenarios 1-4)."""
    producto = get_object_or_404(Producto, pk=pk)
    warning = False
    if request.method == "POST":
        form = ProductoForm(request.POST, instance=producto)
        if form.is_valid():
            if form.price_warning():
                warning = True
            else:
                producto = form.save()
                registrar(request, "UPDATE", "Producto", producto, f"Updated product {producto.nombre}")
                messages.success(request, "Product updated successfully.")
                return redirect("catalogo:producto_list")
    else:
        form = ProductoForm(instance=producto)
    return render(request, "catalogo/producto_form.html",
                  {"form": form, "warning": warning, "title": f"Edit Product — {producto.nombre}", "producto": producto})


# ---------------------------------------------------------------- Proveedor (HU016, HU017)
@role_required("ADMIN")
def proveedor_list(request):
    proveedores = Proveedor.objects.order_by("-activo", "nombre")
    return render(request, "catalogo/proveedor_list.html", {"proveedores": proveedores})


@role_required("ADMIN")
def proveedor_create(request):
    """HU016 — Crear proveedor (Escenarios 1-4)."""
    if request.method == "POST":
        form = ProveedorForm(request.POST)
        if form.is_valid():
            proveedor = form.save()
            registrar(request, "CREATE", "Proveedor", proveedor, f"Created supplier {proveedor.nombre}")
            messages.success(request, "Supplier created successfully.")
            return redirect("catalogo:proveedor_list")
    else:
        form = ProveedorForm()
    return render(request, "catalogo/proveedor_form.html", {"form": form, "title": "New Supplier"})


@role_required("ADMIN")
def proveedor_edit(request, pk):
    """HU017 — Editar proveedor (Escenarios 1-3)."""
    proveedor = get_object_or_404(Proveedor, pk=pk)
    if request.method == "POST":
        form = ProveedorForm(request.POST, instance=proveedor)
        if form.is_valid():
            proveedor = form.save()
            registrar(request, "UPDATE", "Proveedor", proveedor, f"Updated supplier {proveedor.nombre}")
            messages.success(request, "Supplier updated successfully.")
            return redirect("catalogo:proveedor_list")
    else:
        form = ProveedorForm(instance=proveedor)
    return render(request, "catalogo/proveedor_form.html",
                  {"form": form, "title": f"Edit Supplier — {proveedor.nombre}"})


# ---------------------------------------------------------------- TipoProducto (HU018)
@role_required("ADMIN")
def tipoproducto_list(request):
    tipos = TipoProducto.objects.order_by("-activo", "nombre")
    return render(request, "catalogo/tipoproducto_list.html", {"tipos": tipos})


@role_required("ADMIN")
def tipoproducto_create(request):
    """HU018 — Crear tipo de producto (Escenarios 1-4)."""
    if request.method == "POST":
        form = TipoProductoForm(request.POST)
        if form.is_valid():
            tipo = form.save()
            registrar(request, "CREATE", "TipoProducto", tipo, f"Created product type {tipo.nombre}")
            messages.success(request, "Product type created successfully.")
            return redirect("catalogo:tipoproducto_list")
    else:
        form = TipoProductoForm()
    return render(request, "catalogo/tipoproducto_form.html", {"form": form, "title": "New Product Type"})


# ---------------------------------------------------------------- Deshabilitar / reactivar
def _toggle(request, modelo, pk, entidad, nombre_en, lista_url, aviso=""):
    """
    Deshabilita (o reactiva) un registro del catálogo, igual que ya se hace con los
    usuarios: nada se borra, así el historial de ventas y reportes sigue completo.
    GET pide confirmación; POST ejecuta y deja la acción en la bitácora.
    """
    objeto = get_object_or_404(modelo, pk=pk)
    reactivar = not objeto.activo
    if request.method == "POST":
        objeto.activo = reactivar
        objeto.save(update_fields=["activo"])
        registrar(request, "REACTIVATE" if reactivar else "DEACTIVATE", entidad, objeto,
                  f"{'Reactivated' if reactivar else 'Deactivated'} {nombre_en} {objeto}")
        messages.success(request, f"{nombre_en.capitalize()} {objeto} was {'reactivated' if reactivar else 'deactivated'}.")
        return redirect(lista_url)
    return render(request, "confirm_toggle.html", {
        "objeto": objeto, "nombre_en": nombre_en, "reactivar": reactivar,
        "aviso": "" if reactivar else aviso, "cancel_url": lista_url,
    })


@role_required("ADMIN")
def producto_toggle(request, pk):
    return _toggle(request, Producto, pk, "Producto", "product", "catalogo:producto_list",
                   "It will no longer appear in the inventory or in new orders. Past sales and reports are kept.")


@role_required("ADMIN")
def proveedor_toggle(request, pk):
    usados = Producto.objects.filter(proveedor_id=pk, activo=True).count()
    aviso = "It will no longer be offered when creating or editing products."
    if usados:
        aviso += f" {usados} active product(s) use this supplier and stay on sale."
    return _toggle(request, Proveedor, pk, "Proveedor", "supplier", "catalogo:proveedor_list", aviso)


@role_required("ADMIN")
def tipoproducto_toggle(request, pk):
    usados = Producto.objects.filter(tipo_producto_id=pk, activo=True).count()
    aviso = "It will no longer be offered when creating or editing products."
    if usados:
        aviso += f" {usados} active product(s) use this type and stay on sale."
    return _toggle(request, TipoProducto, pk, "TipoProducto", "product type", "catalogo:tipoproducto_list", aviso)
