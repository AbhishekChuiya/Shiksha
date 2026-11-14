"""Replace a module's SOP steps from a CSV file (UTF-8, Excel "CSV UTF-8" works).

Columns: step, text, text_hi (text_hi optional)

    python manage.py import_steps vmpl_melt_cast melt_cast_steps.csv
"""
import csv

from django.core.management.base import BaseCommand, CommandError

from apps.learning.importers import ImportError_, import_steps
from apps.learning.models import Module


class Command(BaseCommand):
    help = "Import SOP steps for a module from CSV (columns: step,text,text_hi)."

    def add_arguments(self, parser):
        parser.add_argument("module_slug")
        parser.add_argument("csv_path")

    def handle(self, module_slug, csv_path, **opts):
        try:
            module = Module.objects.get(slug=module_slug)
        except Module.DoesNotExist:
            raise CommandError(f"No module with slug '{module_slug}'")
        with open(csv_path, newline="", encoding="utf-8-sig") as fh:
            rows = list(csv.DictReader(fh))
        try:
            n = import_steps(module, rows, replace=True)
        except ImportError_ as exc:
            raise CommandError(str(exc))
        self.stdout.write(self.style.SUCCESS(f"{n} steps imported into {module}"))
