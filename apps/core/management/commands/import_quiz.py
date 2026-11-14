"""Replace a module's quiz questions from CSV.

Columns: question, option_a, option_b, option_c, option_d, correct (A-D),
         kind (optional), explanation (optional), question_hi (optional)

    python manage.py import_quiz vmpl_melt_cast melt_cast_quiz.csv --pass 80
"""
import csv

from django.core.management.base import BaseCommand, CommandError

from apps.learning.importers import ImportError_, import_quiz
from apps.learning.models import Module


class Command(BaseCommand):
    help = "Import quiz questions for a module from CSV."

    def add_arguments(self, parser):
        parser.add_argument("module_slug")
        parser.add_argument("csv_path")
        parser.add_argument("--pass", dest="pass_percent", type=int, default=None)

    def handle(self, module_slug, csv_path, pass_percent=None, **opts):
        try:
            module = Module.objects.get(slug=module_slug)
        except Module.DoesNotExist:
            raise CommandError(f"No module with slug '{module_slug}'")
        with open(csv_path, newline="", encoding="utf-8-sig") as fh:
            rows = list(csv.DictReader(fh))
        try:
            n = import_quiz(module, rows, pass_percent, replace=True)
        except ImportError_ as exc:
            raise CommandError(str(exc))
        self.stdout.write(self.style.SUCCESS(f"{n} questions imported for {module}"))
