from django.db import migrations


def clear_staff(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    User.objects.filter(is_superuser=False, is_staff=True).update(is_staff=False)


class Migration(migrations.Migration):
    dependencies = [("accounts", "0002_user_photo")]
    operations = [migrations.RunPython(clear_staff, migrations.RunPython.noop)]
