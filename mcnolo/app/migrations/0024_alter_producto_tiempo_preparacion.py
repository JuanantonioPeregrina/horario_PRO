# Generated by Django 5.1.2 on 2024-10-15 10:04

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0023_producto_tiempo_preparacion'),
    ]

    operations = [
        migrations.AlterField(
            model_name='producto',
            name='tiempo_preparacion',
            field=models.IntegerField(),
        ),
    ]
