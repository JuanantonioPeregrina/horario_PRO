# Generated by Django 5.1.1 on 2024-10-11 11:29

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0008_alter_profile_foto'),
    ]

    operations = [
        migrations.AlterField(
            model_name='profile',
            name='foto',
            field=models.ImageField(default='productos/avatar.webp', upload_to='perfil_fotos/'),
        ),
    ]