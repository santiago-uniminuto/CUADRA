from django.contrib.auth.forms import AuthenticationForm


class CuadraAuthenticationForm(AuthenticationForm):
    """Same as Django's default AuthenticationForm, just with an English
    message for inactive accounts (HU001, alternate flow A2 / CU001-A2)."""

    error_messages = {
        **AuthenticationForm.error_messages,
        "inactive": "This account is inactive. Contact an administrator.",
    }
