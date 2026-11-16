(function () {
  "use strict";
  var $ = function (s, c) { return (c || document).querySelector(s); };
  var $$ = function (s, c) { return Array.prototype.slice.call((c || document).querySelectorAll(s)); };
  var dirty = false, submitting = false, counter = 0;
  function toast(level, text) { if (window.shikshaToast) window.shikshaToast(level, text); }
  function markDirty() { dirty = true; }

  // ------------------------------------------------------------ row editors
  $$("[data-editor]").forEach(function (ed) {
    var rows = $("[data-rows]", ed), order = $("[data-order]", ed), tpl = $("template[data-tpl]", ed),
        empty = $("[data-empty]", ed), count = $("[data-count]", ed), key = ed.getAttribute("data-editor");

    function items() { return $$(":scope > .ed-row", rows); }
    function sync() {
      var list = items();
      order.value = list.map(function (r) { return r.getAttribute("data-uid"); }).join(",");
      list.forEach(function (r, i) {
        $(".ed-num", r).textContent = i + 1;
        $("[data-up]", r).disabled = i === 0;
        $("[data-down]", r).disabled = i === list.length - 1;
      });
      if (empty) empty.hidden = list.length > 0;
      if (count) count.textContent = list.length;
    }
    ed._sync = sync;

    $("[data-add]", ed).addEventListener("click", function () {
      var uid = "n" + Date.now().toString(36) + (counter++);
      rows.insertAdjacentHTML("beforeend", tpl.innerHTML.split("__UID__").join(uid));
      sync(); markDirty();
      var row = items().pop(), first = $("input[type=text], textarea, select, input[type=file]", row);
      row.scrollIntoView({ behavior: "smooth", block: "center" });
      if (first && first.type !== "file") setTimeout(function () { first.focus(); }, 250);
    });

    ed.addEventListener("click", function (e) {
      var btn = e.target.closest("button");
      if (!btn) return;
      var row = btn.closest(".ed-row");
      if (!row || row.parentNode !== rows) return;
      if (btn.hasAttribute("data-del")) {
        var go = row.querySelector("input[name$='-id']").value ? window.confirm("Remove this " + key.replace(/s$/, "") + "? It is deleted when you press Save changes.") : true;
        if (!go) return;
        row.parentNode.removeChild(row); sync(); markDirty();
        toast("info", "Removed — press “Save changes” to apply.");
      } else if (btn.hasAttribute("data-up") && row.previousElementSibling) {
        rows.insertBefore(row, row.previousElementSibling); sync(); markDirty();
      } else if (btn.hasAttribute("data-down") && row.nextElementSibling) {
        rows.insertBefore(row.nextElementSibling, row); sync(); markDirty();
      }
    });
    sync();
  });

  // ------------------------------------------------------------ photo / file preview
  document.addEventListener("change", function (e) {
    var input = e.target;
    if (!input.matches || !input.matches(".pn-drop input[type=file]")) return;
    var f = input.files && input.files[0], label = input.closest(".pn-drop"), prev = $(".pn-newprev", label), span = $("span b", label);
    if (!f) return;
    if (span) span.textContent = f.name;
    if (prev && /^image\//.test(f.type)) {
      var r = new FileReader();
      r.onload = function (ev) { prev.src = ev.target.result; prev.hidden = false; };
      r.readAsDataURL(f);
    }
    markDirty();
  });
  document.addEventListener("dragover", function (e) { var d = e.target.closest && e.target.closest(".pn-drop"); if (d) d.classList.add("over"); });
  ["dragleave", "drop"].forEach(function (ev) { document.addEventListener(ev, function (e) { var d = e.target.closest && e.target.closest(".pn-drop"); if (d) d.classList.remove("over"); }); });

  // ------------------------------------------------------------ unsaved-changes guard + submit
  $$("form[data-dirty-guard]").forEach(function (f) {
    f.addEventListener("input", markDirty);
    f.addEventListener("change", markDirty);
    f.addEventListener("submit", function () { submitting = true; $$("[data-editor]", f).forEach(function (ed) { ed._sync(); }); });
  });
  window.addEventListener("beforeunload", function (e) { if (dirty && !submitting) { e.preventDefault(); e.returnValue = ""; } });

  // ------------------------------------------------------------ confirmations
  document.addEventListener("click", function (e) {
    var b = e.target.closest && e.target.closest("[data-confirm]");
    if (b && !window.confirm(b.getAttribute("data-confirm"))) { e.preventDefault(); e.stopPropagation(); }
    else if (b) { submitting = true; }
  }, true);
  document.addEventListener("submit", function (e) {
    var f = e.target, msg = f.getAttribute && f.getAttribute("data-confirm-form");
    if (msg && !window.confirm(msg)) e.preventDefault();
  }, true);

  // ------------------------------------------------------------ bulk select (module list)
  var all = $("[data-checkall]");
  if (all) {
    var bar = $("[data-bulkbar]"), cnt = $("[data-bulkcount]");
    function refresh() {
      var n = $$("[data-check]:checked").length;
      if (bar) { bar.hidden = n === 0; if (cnt) cnt.textContent = n + " selected"; }
    }
    all.addEventListener("change", function () { $$("[data-check]").forEach(function (c) { c.checked = all.checked; }); refresh(); });
    document.addEventListener("change", function (e) { if (e.target.matches && e.target.matches("[data-check]")) refresh(); });
  }
})();

/* Import centre: show the chosen file name in the drop box */
document.addEventListener("change", function (e) {
  var input = e.target;
  if (!input.matches || !input.matches(".imp-drop input[type=file]")) return;
  var box = input.closest(".imp-drop"), label = box.querySelector("b"), name = input.files && input.files[0] ? input.files[0].name : "";
  box.classList.toggle("has-file", !!name);
  if (!label.dataset.orig) label.dataset.orig = label.textContent;
  label.textContent = name || label.dataset.orig;
});
