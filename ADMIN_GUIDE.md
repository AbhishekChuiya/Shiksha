# Admin panel — quick guide

Open **Manage Content** in the left menu (admins only), or go to `/manage/`.

| I want to… | Go to |
|---|---|
| Add a new learning module | Modules → **Add module** → then add steps, photos, safety rules, quiz |
| Add many steps at once | Module → **SOP steps** → *Paste or import* (paste lines, or upload an Excel/CSV file) |
| Reorder / delete steps | Use the ▲ ▼ and bin buttons, then **Save changes** (nothing changes until you save) |
| Add photos to a module or plant | Module → **Photos** · Plants → plant → **Photos** (they are shrunk automatically) |
| Add Hindi text | Open the collapsed **Hindi (optional)** box on any form |
| Make a quiz | Module → **Quiz** → Create quiz → Add question (or import from Excel) |
| Hide something from learners | Module → **Hide from learners** (or untick "Active" on a plant) |
| Upload a new SOP version | SOP library → the SOP → *Versions* → Add new version → status **Approved** |
| Add people | Users → Add user (or Import from Excel) |
| See progress | Reports (download as CSV) |
| Remove a bad discussion post | Discussion → Hide / Delete |

## Good to know
* **Quizzes rotate by themselves.** Each attempt shows the questions in a new order (question 1 is never question 1 twice in a row) and shuffles the answer options. Turn this off per quiz in *Quiz settings*, or keep a single question's options fixed ("All of the above" style).
* **Quiz with a question bank:** set *Questions per attempt* (e.g. 10 of 40). Questions a learner hasn't seen recently are picked first, so the whole bank rotates.
* **New modules start as Draft** — use **Preview as learner**, then **Publish**.
* **Deleting** a module/SOP/plant always asks first. Plants with incident reports can only be hidden.
* **Knowledge base** (left menu): add PDFs, Word/Excel files, videos or links under categories you create. SOP documents and module videos appear there automatically.
* **Safety rules** (inside a module): pick a group for each rule — PPE required, Hazards, Safe practices, Do's, Don'ts, Environment — and learners see them in matching colours.
* The Django admin (`/admin/`, *Advanced admin*) is only for superusers made with `python manage.py createsuperuser`. Giving someone the Admin role in the panel does not give them this.

## Discussion
There is **one global discussion** for everyone (Discussion in the left menu). Posts can be tagged to a module; each module's *Discussion* tab shows its tagged posts. Admins can pin, hide or delete posts.
