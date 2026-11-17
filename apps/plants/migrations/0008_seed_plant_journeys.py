from django.db import migrations


def seed(apps, schema_editor):
    """Give every VMPL / VGPL / VRPL plant its starting journey (only if it has none yet)."""
    from apps.plants.journeys import STAGES
    Plant = apps.get_model("plants", "Plant")
    PlantStage = apps.get_model("plants", "PlantStage")
    for plant in Plant.objects.all():
        prefix = next((k for k in STAGES if plant.name.upper().startswith(k)), None)
        if prefix and not PlantStage.objects.filter(plant=plant).exists():
            PlantStage.objects.bulk_create([PlantStage(plant=plant, name=n, order=i) for i, n in enumerate(STAGES[prefix])])


class Migration(migrations.Migration):
    dependencies = [("plants", "0007_journey_and_studyday")]
    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
