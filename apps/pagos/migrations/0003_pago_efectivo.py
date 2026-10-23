from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [('pagos', '0002_initial')]
    operations = [
        migrations.AddField(model_name='pago', name='efectivo_recibido', field=models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)),
        migrations.AddField(model_name='pago', name='cambio', field=models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)),
    ]
