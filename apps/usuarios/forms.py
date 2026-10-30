"""
Sprint 2 — formularios de gestión de usuarios (HU004, HU005, HU007, HU008).
Todos los mensajes visibles están en inglés (requisito del cliente).
"""
from django import forms
from django.db.models import Q
from django.contrib.auth.password_validation import validate_password

from .models import Sede, Usuario

REQUIRED_MSG = "This field is required."
PENDING_FIELDS_MSG = "Please complete the pending fields."


class UsuarioCreateForm(forms.ModelForm):
    """HU004 — Crear usuario."""

    password1 = forms.CharField(
        label="Password",
        strip=False,
        error_messages={"required": REQUIRED_MSG},
        widget=forms.PasswordInput(attrs={"class": "form-control", "autocomplete": "new-password"}),
    )
    password2 = forms.CharField(
        label="Confirm password",
        strip=False,
        error_messages={"required": REQUIRED_MSG},
        widget=forms.PasswordInput(attrs={"class": "form-control", "autocomplete": "new-password"}),
    )

    class Meta:
        model = Usuario
        fields = ["nombre", "username", "rol", "sede"]
        labels = {"nombre": "Name", "username": "Username", "rol": "Role", "sede": "Site"}
        widgets = {
            "nombre": forms.TextInput(attrs={"class": "form-control"}),
            "username": forms.TextInput(attrs={"class": "form-control", "autocomplete": "off"}),
            "rol": forms.Select(attrs={"class": "form-select"}),
            "sede": forms.Select(attrs={"class": "form-select"}),
        }
        error_messages = {
            "nombre": {"required": REQUIRED_MSG},
            "username": {"required": REQUIRED_MSG, "unique": "This username already exists"},
            "rol": {"required": REQUIRED_MSG},
            "sede": {"required": REQUIRED_MSG},
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # El rol y la sede son obligatorios: sin opción vacía "por defecto".
        self.fields["rol"].choices = [("", "---------")] + list(Usuario.Rol.choices)
        self.fields["sede"].empty_label = "---------"
        self.fields["sede"].queryset = Sede.objects.filter(activo=True)

    def clean_nombre(self):
        return self.cleaned_data["nombre"].strip()

    def clean_username(self):
        username = self.cleaned_data["username"].strip()
        # El unique de Django distingue mayúsculas; aquí también se rechaza "Admin" vs "admin".
        if Usuario.objects.filter(username__iexact=username).exists():
            raise forms.ValidationError("This username already exists")
        return username

    def clean(self):
        cleaned = super().clean()
        p1, p2 = cleaned.get("password1"), cleaned.get("password2")
        if p1 and p2:
            if p1 != p2:
                self.add_error("password2", "Passwords do not match")
            else:
                try:
                    validate_password(p1, user=Usuario(
                        username=cleaned.get("username", ""), nombre=cleaned.get("nombre", "")))
                except forms.ValidationError as exc:
                    self.add_error("password1", exc)
        return cleaned

    def save(self, commit=True):
        usuario = super().save(commit=False)
        usuario.set_password(self.cleaned_data["password1"])  # hash PBKDF2, nunca texto plano
        usuario.is_active = True
        if commit:
            usuario.save()
        return usuario


class UsuarioUpdateForm(forms.ModelForm):
    """HU005 — Editar usuario (nombre, rol y sede)."""

    class Meta:
        model = Usuario
        fields = ["nombre", "rol", "sede"]
        labels = {"nombre": "Name", "rol": "Role", "sede": "Site"}
        widgets = {
            "nombre": forms.TextInput(attrs={"class": "form-control"}),
            "rol": forms.Select(attrs={"class": "form-select"}),
            "sede": forms.Select(attrs={"class": "form-select"}),
        }
        error_messages = {
            "nombre": {"required": "Name is required."},
            "rol": {"required": REQUIRED_MSG},
            "sede": {"required": REQUIRED_MSG},
        }

    def __init__(self, *args, editing_self=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.editing_self = editing_self
        # Solo sedes activas (más la actual del usuario, aunque se haya deshabilitado).
        self.fields["sede"].queryset = Sede.objects.filter(Q(activo=True) | Q(pk=self.instance.sede_id))

    def clean_nombre(self):
        return self.cleaned_data["nombre"].strip()

    def clean_rol(self):
        rol = self.cleaned_data["rol"]
        # Evita que el administrador se quite a sí mismo el acceso a esta gestión.
        if self.editing_self and rol != Usuario.Rol.ADMIN:
            raise forms.ValidationError("You cannot remove your own Administrator role.")
        return rol


class AsignarRolSedeForm(forms.Form):
    """HU007 — Reasignación rápida de rol y sede desde el listado."""

    usuario = forms.ModelChoiceField(
        queryset=Usuario.objects.all(), error_messages={"required": REQUIRED_MSG, "invalid_choice": REQUIRED_MSG})
    rol = forms.ChoiceField(
        choices=Usuario.Rol.choices, error_messages={"required": REQUIRED_MSG, "invalid_choice": REQUIRED_MSG})
    sede = forms.ModelChoiceField(
        queryset=Sede.objects.filter(activo=True), error_messages={"required": REQUIRED_MSG, "invalid_choice": REQUIRED_MSG})

    def __init__(self, *args, current_user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.current_user = current_user

    def clean(self):
        cleaned = super().clean()
        usuario, rol = cleaned.get("usuario"), cleaned.get("rol")
        if usuario and rol and self.current_user and usuario.pk == self.current_user.pk \
                and rol != Usuario.Rol.ADMIN:
            self.add_error("rol", "You cannot remove your own Administrator role.")
        return cleaned


class ResetPasswordForm(forms.Form):
    """HU008 — Restablecer contraseña de un usuario."""

    password1 = forms.CharField(
        label="New password", strip=False, error_messages={"required": REQUIRED_MSG},
        widget=forms.PasswordInput(attrs={"class": "form-control", "autocomplete": "new-password"}))
    password2 = forms.CharField(
        label="Confirm new password", strip=False, error_messages={"required": REQUIRED_MSG},
        widget=forms.PasswordInput(attrs={"class": "form-control", "autocomplete": "new-password"}))

    def __init__(self, *args, usuario=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.usuario = usuario

    def clean(self):
        cleaned = super().clean()
        p1, p2 = cleaned.get("password1"), cleaned.get("password2")
        if p1 and p2:
            if p1 != p2:
                self.add_error("password2", "Passwords do not match")
            else:
                try:
                    validate_password(p1, user=self.usuario)
                except forms.ValidationError as exc:
                    self.add_error("password1", exc)
        return cleaned

    def save(self):
        self.usuario.set_password(self.cleaned_data["password1"])
        self.usuario.save(update_fields=["password"])
        return self.usuario
