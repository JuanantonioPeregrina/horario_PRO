# Generated by Django 5.1.2 on 2024-10-15 22:31

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0024_alter_producto_tiempo_preparacion'),
    ]

    operations = [
        migrations.AddField(
            model_name='pedido',
            name='nota_especial',
            field=models.TextField(blank=True, null=True),
        ),
    ]
