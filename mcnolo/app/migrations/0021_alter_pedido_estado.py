# Generated by Django 5.1.1 on 2024-10-12 12:16

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0020_pedido_estado'),
    ]

    operations = [
        migrations.AlterField(
            model_name='pedido',
            name='estado',
            field=models.CharField(choices=[('pendiente', 'Pendiente'), ('listo', 'Listo')], default='Pendiente', max_length=20),
        ),
    ]
