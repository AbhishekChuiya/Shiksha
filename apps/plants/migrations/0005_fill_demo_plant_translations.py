from django.db import migrations


def fill(apps, schema_editor):
    """Give the demo plant (the one whose About text starts with the VMPL paragraph) its Hindi and Gujarati text.
    Only empty fields are filled — anything an admin typed is kept."""
    from apps.core.management.commands.seed_gujarati import PLANT as GU
    from apps.core.management.commands.seed_hindi import VMPL as HI
    Plant = apps.get_model("plants", "Plant")
    for plant in Plant.objects.filter(about__startswith="Vishakha Metals Private Limited"):
        for values in (GU, HI):
            for field, value in values.items():
                if value and not getattr(plant, field, ""):
                    setattr(plant, field, value)
        plant.save()


class Migration(migrations.Migration):
    dependencies = [("plants", "0004_department_name_gu_plant_about_gu_plant_location_gu_and_more")]
    operations = [migrations.RunPython(fill, migrations.RunPython.noop)]
