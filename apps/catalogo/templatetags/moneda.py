"""Presentation-only formatting of monetary values in Colombian pesos."""
from decimal import Decimal, InvalidOperation
from django import template

register = template.Library()

@register.filter(name="cop")
def cop(value):
    if value is None or value == "":
        return "—"
    try:
        amount = Decimal(str(value))
        if not amount.is_finite():
            return "—"
        number = f"{abs(amount):,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")
        return f"{'-' if amount < 0 else ''}${number}"
    except (InvalidOperation, ValueError, TypeError):
        return "—"
