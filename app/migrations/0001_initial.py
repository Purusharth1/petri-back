# Generated by Django 5.0 on 2024-06-15 17:00

from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Profile',
            fields=[
                ('username', models.TextField()),
                ('email', models.EmailField(default=True, max_length=254, primary_key=True, serialize=False)),
            ],
        ),
    ]
