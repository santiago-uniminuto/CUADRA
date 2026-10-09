from django.contrib.auth.forms import AuthenticationForm


class CuadraAuthenticationForm(AuthenticationForm):
    """Django's AuthenticationForm with the exact messages required by the
    user stories.

    HU001, scenario 2: wrong username or password.
    Note: Django's default backend refuses inactive users inside
    authenticate(), so an inactive user also gets "invalid_login" (access is
    denied either way, which is what the story requires).
    """

    error_messages = {
        **AuthenticationForm.error_messages,
        "invalid_login": "Incorrect username or password",
        "inactive": "This account is inactive. Contact an administrator.",
    }
