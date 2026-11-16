"""Plain-language setup checklists for admins: what is done, what is missing, and where to fix it."""
from apps.learning.models import Module, SafetyGuideline
from apps.plants.models import Department, Plant
from apps.accounts.models import User


def module_checks(module):
    """Returns (checks, percent, next_check). Each check: key, label, done, tab, optional."""
    quiz = getattr(module, "quiz", None)
    has_rules = module.safety_guidelines().exists() or SafetyGuideline.objects.filter(sop__module=module).exists()
    checks = [
        {"key": "basics", "label": "Description written", "done": bool(module.summary and module.overview), "tab": "details", "optional": False,
         "hint": "Add a short summary and an overview on the Details tab."},
        {"key": "steps", "label": "SOP steps added", "done": module.steps.exists(), "tab": "steps", "optional": False,
         "hint": "Add the steps learners must follow (or import them from Excel)."},
        {"key": "safety", "label": "Safety rules added", "done": has_rules, "tab": "safety", "optional": False,
         "hint": "Add PPE, hazards and safe-operating rules."},
        {"key": "quiz", "label": "Quiz with questions", "done": bool(quiz and quiz.questions.exists()), "tab": "quiz", "optional": False,
         "hint": "Create the quiz and add its questions."},
        {"key": "published", "label": "Visible to learners", "done": module.status == Module.Status.PUBLISHED, "tab": "details", "optional": False,
         "hint": "Press Publish when everything is ready."},
        {"key": "translations", "label": "Hindi & Gujarati titles", "done": bool(module.title_hi and module.title_gu), "tab": "details", "optional": True,
         "hint": "Optional — add Hindi and Gujarati text so every learner reads their own language."},
    ]
    required = [c for c in checks if not c["optional"]]
    percent = round(100 * sum(1 for c in required if c["done"]) / len(required))
    nxt = next((c for c in required if not c["done"]), None)
    return checks, percent, nxt


def setup_guide():
    """The admin dashboard's 'Getting started' steps."""
    steps = [
        {"label": "Add your plant", "done": Plant.objects.exists(), "url": "panel:plants", "text": "Create each plant — or import many from Excel."},
        {"label": "Add departments", "done": Department.objects.exists(), "url": "panel:plants", "text": "Production, QC, Maintenance … (Plants → Departments & processes)."},
        {"label": "Create modules", "done": Module.objects.exists(), "url": "panel:modules", "text": "One module per process."},
        {"label": "Add SOP steps and safety rules", "done": Module.objects.filter(steps__isnull=False).exists(), "url": "panel:modules", "text": "Open a module → SOP steps / Safety rules."},
        {"label": "Create quizzes", "done": Module.objects.filter(quiz__questions__isnull=False).exists(), "url": "panel:quiz_new", "text": "Quizzes → Create a quiz."},
        {"label": "Invite your team", "done": User.objects.filter(role=User.Role.LEARNER).count() > 1, "url": "panel:users", "text": "Add users or import them from a file."},
        {"label": "Publish a module", "done": Module.objects.filter(status=Module.Status.PUBLISHED).exists(), "url": "panel:modules", "text": "Learners only see published modules."},
    ]
    done = sum(1 for s in steps if s["done"])
    return {"steps": steps, "done": done, "total": len(steps), "percent": round(100 * done / len(steps)), "finished": done == len(steps)}
