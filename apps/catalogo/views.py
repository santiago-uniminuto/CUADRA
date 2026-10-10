from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render

from apps.algoritmos.ordenamiento import selection_sort
from apps.usuarios.decorators import role_required

from .forms import ProductoForm, ProveedorForm, TipoProductoForm
from .models import Producto, Proveedor, TipoProducto


# ---------------------------------------------------------------- Producto (HU013, HU014, HU015)
@role_required("ADMIN")
def producto_list(request):
    """
    HU015 — Listar productos, con búsqueda por nombre (Escenarios 1-3).
    Orden final con ordenamiento por selección (requisito académico de
    algoritmos), por precio de venta ascendente; a igual precio, por nombre.
    """
    query = request.GET.get("q", "").strip()
    productos_qs = Producto.objects.select_related("tipo_producto", "proveedor")
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
                form.save()
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
                form.save()
                messages.success(request, "Product updated successfully.")
                return redirect("catalogo:producto_list")
    else:
        form = ProductoForm(instance=producto)
    return render(request, "catalogo/producto_form.html",
                  {"form": form, "warning": warning, "title": f"Edit Product — {producto.nombre}", "producto": producto})


# ---------------------------------------------------------------- Proveedor (HU016, HU017)
@role_required("ADMIN")
def proveedor_list(request):
    proveedores = Proveedor.objects.order_by("nombre")
    return render(request, "catalogo/proveedor_list.html", {"proveedores": proveedores})


@role_required("ADMIN")
def proveedor_create(request):
    """HU016 — Crear proveedor (Escenarios 1-4)."""
    if request.method == "POST":
        form = ProveedorForm(request.POST)
        if form.is_valid():
            form.save()
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
            form.save()
            messages.success(request, "Supplier updated successfully.")
            return redirect("catalogo:proveedor_list")
    else:
        form = ProveedorForm(instance=proveedor)
    return render(request, "catalogo/proveedor_form.html",
                  {"form": form, "title": f"Edit Supplier — {proveedor.nombre}"})


# ---------------------------------------------------------------- TipoProducto (HU018)
@role_required("ADMIN")
def tipoproducto_list(request):
    tipos = TipoProducto.objects.order_by("nombre")
    return render(request, "catalogo/tipoproducto_list.html", {"tipos": tipos})


@role_required("ADMIN")
def tipoproducto_create(request):
    """HU018 — Crear tipo de producto (Escenarios 1-4)."""
    if request.method == "POST":
        form = TipoProductoForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Product type created successfully.")
            return redirect("catalogo:tipoproducto_list")
    else:
        form = TipoProductoForm()
    return render(request, "catalogo/tipoproducto_form.html", {"form": form, "title": "New Product Type"})
