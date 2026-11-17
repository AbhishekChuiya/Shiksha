"""Builds the dashboard "Your plant journey" strip for one learner."""
from apps.learning.models import Module, ModuleProgress

from .journeys import find_module, icon_for


def build_journey(user, plant):
    stages = list(plant.stages.select_related("module").all())
    if not stages:
        return []
    modules = list(Module.objects.filter(plant=plant, status=Module.Status.PUBLISHED).select_related("process").order_by("order", "title"))
    published = {m.pk: m for m in modules}
    done = set(ModuleProgress.objects.filter(user=user, module__plant=plant, completed_at__isnull=False).values_list("module_id", flat=True))
    out, current_set = [], False
    for st in stages:
        m = published.get(st.module_id) if st.module_id else find_module(st.name, modules)
        state = "none"
        if m is not None:
            if m.pk in done:
                state = "done"
            elif not current_set:
                state, current_set = "current", True
            else:
                state = "todo"
        out.append({"name": st.display_name, "icon": icon_for(st.name), "state": state, "module": m, "url": m.get_absolute_url() if m else ""})
    return out
