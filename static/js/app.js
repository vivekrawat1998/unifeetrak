/**
 * UniFeeTrak — Main Application Script
 * static/js/app.js
 *
 * Module structure:
 *   Config          — constants (API base, page size, month names)
 *   State           — single source of truth for data + sort + page
 *   API             — all fetch calls, centralised in one object
 *   Filters         — reads all filter control values from the DOM
 *   TableRenderer   — transforms State data into DOM table rows
 *   StatsBar        — updates the four stat cards
 *   DataLoader      — orchestrates API calls and wires results to UI
 *   DropdownInit    — populates month / year / batch / semester selects
 *   SortController  — header-click → sort state → re-render (no API call)
 *   FilterController— wires filter controls to re-renders
 *   makeModal()     — reusable upload-modal factory
 *   StudentsModal   — instance for the Students CSV upload
 *   FeesModal       — instance for the Fees CSV upload
 *   Exporter        — triggers the server-side CSV download
 *   Toast           — lightweight notification system
 *   _esc()          — XSS-safe HTML escaper utility
 *   Boot            — DOMContentLoaded initialisation
 */

"use strict";

/* ── Config ─────────────────────────────────────────────────────────────────── */
const Config = {
    API_BASE: "https://unifeetrak.onrender.com/",        // same-origin — Flask serves this HTML file
    PAGE_SIZE: 15,
    MONTHS: [
        "January", "February", "March", "April", "May", "June",
        "July", "August", "September", "October", "November", "December",
    ],
};


/* ── State ──────────────────────────────────────────────────────────────────── */
const State = (() => {
    let _data = [];
    let _col = "roll_number";
    let _dir = "asc";
    let _page = 1;

    return {
        setData(rows) { _data = rows; },
        getData() { return _data; },

        setSortCol(c) { _col = c; },
        getSortCol() { return _col; },

        setSortDir(d) { _dir = d; },
        getSortDir() { return _dir; },

        setPage(p) { _page = p; },
        getPage() { return _page; },
    };
})();


/* ── API ────────────────────────────────────────────────────────────────────── */
const API = (() => {
    async function _fetch(path, opts = {}) {
        const res = await fetch(Config.API_BASE + path, opts);
        const json = await res.json();
        if (!res.ok) throw new Error(json.error || `HTTP ${res.status}`);
        return json;
    }

    return {
        getStudents: (m, y, batchYear = "", batch = "") => {
            const p = new URLSearchParams({ month: m, year: y });
            if (batch)          p.set("batch",      batch);
            else if (batchYear) p.set("batch_year", batchYear);
            return _fetch(`/api/students?${p}`);
        },
        getStats: (m, y, batchYear = "", batch = "") => {
            const p = new URLSearchParams({ month: m, year: y });
            if (batch)          p.set("batch",      batch);
            else if (batchYear) p.set("batch_year", batchYear);
            return _fetch(`/api/fees/stats?${p}`);
        },
        getBatches:    (year = "") => _fetch(`/api/students/batches${year ? "?year=" + encodeURIComponent(year) : ""}`),
        getSemesters:  (b = "")   => _fetch(`/api/students/semesters${b ? "?batch=" + encodeURIComponent(b) : ""}`),
        uploadFees:    fd => _fetch("/api/fees/upload",     { method: "POST", body: fd }),
        uploadStudents:fd => _fetch("/api/students/upload", { method: "POST", body: fd }),
    };
})();


/* ── Filters ────────────────────────────────────────────────────────────────── */
const Filters = {
    month() { return new Date().getMonth() + 1; },
    year()  { return new Date().getFullYear(); },
    batch() { return document.getElementById("ctrl-batch").value.trim(); },
    semester() { return document.getElementById("ctrl-semester").value.trim(); },
    status() { return document.getElementById("ctrl-status").value.trim(); },
    search() { return document.getElementById("ctrl-search").value.toLowerCase().trim(); },
};


/* ── TableRenderer ──────────────────────────────────────────────────────────── */
const TableRenderer = (() => {
    // DOM shortcuts
    const tbody = () => document.getElementById("js-tbody");
    const count = () => document.getElementById("js-count");
    const pgInfo = () => document.getElementById("js-pg-info");
    const pgBtns = () => document.getElementById("js-pg-btns");

    /**
     * _filtered()
     * Applies client-side filters (batch, semester, status, search) and
     * sort to the raw data in State. No API call — instant re-render.
     */
    function _filtered() {
        const batch = Filters.batch();
        const sem = Filters.semester();
        const status = Filters.status();
        const q = Filters.search();
        const col = State.getSortCol();
        const dir = State.getSortDir();

        return State.getData()
            .filter(r => {
                if (batch && r.batch_name !== batch) return false;
                if (sem && r.semester !== sem) return false;
                if (status && r.fee_status !== status) return false;
                if (q && !r.name.toLowerCase().includes(q)
                    && !r.roll_number.toLowerCase().includes(q)) return false;
                return true;
            })
            .sort((a, b) => {
                let av = a[col], bv = b[col];
                if (typeof av === "string") { av = av.toLowerCase(); bv = bv.toLowerCase(); }
                if (av < bv) return dir === "asc" ? -1 : 1;
                if (av > bv) return dir === "asc" ? 1 : -1;
                return 0;
            });
    }

    /** Format ISO date string → "28 Apr 2026" */
    function _fmtDate(iso) {
        if (!iso) return "—";
        const [y, m, d] = iso.split("-");
        const mon = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
            "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"][parseInt(m) - 1];
        return `${d} ${mon} ${y}`;
    }

    /** Build a single <tr> HTML string for one student record */
    function _row(r) {
        const paid = r.fee_status === "Paid";
        return `
      <tr class="${paid ? "" : "unpaid-row"}">
        <td><span class="c-name">${_esc(r.name)}</span></td>
        <td><span class="c-roll">${_esc(r.roll_number)}</span></td>
        <td><span class="c-batch" title="${_esc(r.batch_name)}">${_esc(r.batch_name)}</span></td>
        <td>${_esc(r.semester)}</td>
        <td>
          ${paid
                ? `<span class="badge badge-paid">Paid</span>`
                : `<span class="badge badge-unpaid">Unpaid</span>`}
        </td>
        <td>
          ${paid
                ? `<span class="c-amt">&#8377;${Number(r.amount_paid).toLocaleString("en-IN")}</span>`
                : `<span class="c-zero">—</span>`}
        </td>
        <td><span class="c-date">${_fmtDate(r.payment_date)}</span></td>
      </tr>`;
    }

    /** Re-render the table from the current State (no API call) */
    function render() {
        const rows = _filtered();
        const total = rows.length;
        const page = State.getPage();
        const start = (page - 1) * Config.PAGE_SIZE;
        const slice = rows.slice(start, start + Config.PAGE_SIZE);

        count().textContent = `${total} record${total !== 1 ? "s" : ""}`;

        if (total === 0) {
            tbody().innerHTML = `
        <tr><td colspan="7" class="state-cell">
          <svg width="32" height="32" fill="none" stroke="currentColor"
               stroke-width="1.5" viewBox="0 0 24 24" style="color:var(--ink-3)">
            <circle cx="12" cy="12" r="10"/>
            <path d="M8 12h8M12 8v8" stroke-linecap="round"/>
          </svg>
          <p>No records match the current filters.</p>
        </td></tr>`;
            pgInfo().textContent = "No records";
            pgBtns().innerHTML = "";
            return;
        }

        tbody().innerHTML = slice.map(_row).join("");

        const end = Math.min(start + Config.PAGE_SIZE, total);
        pgInfo().textContent = `Showing ${start + 1}–${end} of ${total} records`;
        _renderPagination(total, page);
    }

    /** Build numbered pagination buttons */
    function _renderPagination(total, cur) {
        const pages = Math.ceil(total / Config.PAGE_SIZE);
        if (pages <= 1) { pgBtns().innerHTML = ""; return; }

        let html = `<button class="pg-btn" onclick="TableRenderer.goTo(${cur - 1})"
                  ${cur === 1 ? "disabled" : ""}>‹</button>`;

        for (let p = 1; p <= pages; p++) {
            html += `<button class="pg-btn ${p === cur ? "active" : ""}"
                 onclick="TableRenderer.goTo(${p})">${p}</button>`;
        }

        html += `<button class="pg-btn" onclick="TableRenderer.goTo(${cur + 1})"
               ${cur === pages ? "disabled" : ""}>›</button>`;

        pgBtns().innerHTML = html;
    }

    /** Navigate to a specific page */
    function goTo(p) {
        const pages = Math.ceil(_filtered().length / Config.PAGE_SIZE);
        if (p < 1 || p > pages) return;
        State.setPage(p);
        render();
    }

    function showLoading() {
        tbody().innerHTML = `
      <tr><td colspan="7" class="state-cell">
        <div class="spinner"></div>
        <p>Loading student records…</p>
      </td></tr>`;
    }

    function showError(msg) {
        tbody().innerHTML = `
      <tr><td colspan="7" class="state-cell">
        <p>⚠ ${_esc(msg)}</p>
      </td></tr>`;
    }

    return { render, goTo, showLoading, showError };
})();


/* ── StatsBar ───────────────────────────────────────────────────────────────── */
const StatsBar = {
    update(s) {
        document.getElementById("stat-total").textContent = s.total_students ?? "—";
        document.getElementById("stat-paid").textContent = s.paid_count ?? "—";
        document.getElementById("stat-unpaid").textContent = s.unpaid_count ?? "—";
        document.getElementById("stat-collected").textContent =
            s.total_collected != null
                ? "₹" + Number(s.total_collected).toLocaleString("en-IN")
                : "—";
    },
    reset() {
        ["stat-total", "stat-paid", "stat-unpaid", "stat-collected"]
            .forEach(id => { document.getElementById(id).textContent = "—"; });
    },
};


/* ── DataLoader ─────────────────────────────────────────────────────────────── */
const DataLoader = {
    /**
     * Fires both API calls in parallel (students + stats) to minimise
     * round-trips, then updates the table and stat cards together.
     */
    async load() {
        const m     = Filters.month();
        const y     = Filters.year();
        const batch = Filters.batch();
        // batchYear is NOT derived from the year dropdown —
        // the year filter controls the fee period, not which students to show.
        // batch_year is only sent when user explicitly picks a specific batch.
        const batchYear = "";

        document.getElementById("js-period").textContent =
            `${Config.MONTHS[m - 1]} ${y}`;

        TableRenderer.showLoading();
        StatsBar.reset();
        State.setPage(1);

        try {
            const [studRes, statsRes] = await Promise.all([
                API.getStudents(m, y, batchYear, batch),
                API.getStats(m, y, batchYear, batch),
            ]);
            State.setData(studRes.data || []);
            StatsBar.update(statsRes);
            TableRenderer.render();
        } catch (err) {
            TableRenderer.showError("Could not load data — is the Flask server running?");
            Toast.show(err.message, "error");
        }
    },
};


/* ── DropdownInit ───────────────────────────────────────────────────────────── */
const DropdownInit = {
    async init() {
        await this.refreshBatches("");  // load all batches — not scoped to year
    },

    // Refresh batch dropdown scoped to selected year
    async refreshBatches(year = "") {
        try {
            const res       = await API.getBatches(year);
            const sel       = document.getElementById("ctrl-batch");
            const prevBatch = sel.value;
            sel.innerHTML   = '<option value="">All Batches</option>';
            (res.data || []).forEach(b => sel.appendChild(new Option(b, b)));
            if ([...sel.options].some(o => o.value === prevBatch)) sel.value = prevBatch;
            else sel.value = "";
        } catch {}
    },

    async refreshSemesters(batch = "") {
        const sel  = document.getElementById("ctrl-semester");
        const prev = sel.value;
        sel.innerHTML = '<option value="">All Semesters</option>';
        try {
            const res = await API.getSemesters(batch);
            (res.data || []).forEach(s => sel.appendChild(new Option(s, s)));
            if ([...sel.options].some(o => o.value === prev)) sel.value = prev;
        } catch {}
    },
};


/* ── SortController ─────────────────────────────────────────────────────────── */
const SortController = {
    /** Attach click handlers to all sortable column headers */
    init() {
        document.querySelectorAll("thead th.sortable").forEach(th => {
            th.addEventListener("click", () => {
                const col = th.dataset.col;

                // Toggle direction if same column, else reset to ascending
                if (State.getSortCol() === col) {
                    State.setSortDir(State.getSortDir() === "asc" ? "desc" : "asc");
                } else {
                    State.setSortCol(col);
                    State.setSortDir("asc");
                }

                // Update visual indicators on all headers
                document.querySelectorAll("thead th").forEach(h => h.classList.remove("asc", "desc"));
                th.classList.add(State.getSortDir());

                State.setPage(1);
                TableRenderer.render();  // no API call — client-side sort only
            });
        });
    },
};


/* ── FilterController ───────────────────────────────────────────────────────── */
const FilterController = {
    init() {
        document.getElementById("ctrl-batch").addEventListener("change", async () => {
            await DropdownInit.refreshSemesters(Filters.batch());
            State.setPage(1);
            await DataLoader.load();
        });

        // Semester, Status, Search → pure client-side re-render (no API call)
        ["ctrl-semester", "ctrl-status", "ctrl-search"].forEach(id => {
            document.getElementById(id).addEventListener("input", () => {
                State.setPage(1);
                TableRenderer.render();
            });
        });
    },
};


/* ── makeModal() ────────────────────────────────────────────────────────────── */
/**
 * Reusable upload-modal factory.
 * Both StudentsModal and FeesModal are created with this function —
 * they share identical open / close / submit / dragDrop logic but
 * operate on different DOM element IDs and call different API endpoints.
 *
 * @param {object} cfg
 *   bgId      — id of the modal backdrop element
 *   dzId      — id of the drop-zone div
 *   fiId      — id of the hidden <input type="file">
 *   fnId      — id of the filename display span
 *   btnId     — id of the submit button
 *   urId      — id of the inline result div
 *   apiFn     — function(FormData) → Promise  (API call to make)
 *   onSuccess — async function() called after a successful upload
 */
function makeModal({ bgId, dzId, fiId, fnId, btnId, urId, apiFn, onSuccess }) {
    let _file = null;

    // Cached DOM references (evaluated lazily so they're always fresh)
    const el = {
        bg: () => document.getElementById(bgId),
        dz: () => document.getElementById(dzId),
        fi: () => document.getElementById(fiId),
        fn: () => document.getElementById(fnId),
        btn: () => document.getElementById(btnId),
        ur: () => document.getElementById(urId),
    };

    /** Open the modal */
    function open() {
        el.bg().classList.add("open");
        el.ur().style.display = "none";
    }

    /** Close and reset the modal */
    function close() {
        el.bg().classList.remove("open");
        _file = null;
        el.fn().textContent = "";
        el.fi().value = "";
        el.ur().style.display = "none";
    }

    /** Validate and store the selected file */
    function _setFile(f) {
        if (!f) return;
        if (!f.name.toLowerCase().endsWith(".csv")) {
            Toast.show("Only .csv files are accepted", "error");
            return;
        }
        _file = f;
        el.fn().textContent = f.name;
    }

    /** Wire up drag-and-drop and file-input events */
    function initDragDrop() {
        const dz = el.dz();
        dz.addEventListener("dragover", e => { e.preventDefault(); dz.classList.add("over"); });
        dz.addEventListener("dragleave", () => dz.classList.remove("over"));
        dz.addEventListener("drop", e => {
            e.preventDefault();
            dz.classList.remove("over");
            _setFile(e.dataTransfer.files[0]);
        });
        el.fi().addEventListener("change", e => _setFile(e.target.files[0]));
    }

    /** Upload the file via the provided apiFn, then call onSuccess */
    async function submit() {
        if (!_file) {
            Toast.show("Please select a CSV file first", "error");
            return;
        }

        const btn = el.btn();
        btn.disabled = true;
        btn.textContent = "Uploading…";

        const fd = new FormData();
        fd.append("file", _file);

        try {
            const res = await apiFn(fd);

            // Show inline success result with any per-row errors
            const ur = el.ur();
            ur.style.display = "block";
            ur.className = "upload-result success";
            ur.innerHTML = res.message +
                (res.errors && res.errors.length
                    ? "<br><br>" + res.errors.map(e => `Row ${e.row}: ${_esc(e.error)}`).join("<br>")
                    : "");

            Toast.show(res.message, "success");
            await onSuccess();

        } catch (err) {
            const ur = el.ur();
            ur.style.display = "block";
            ur.className = "upload-result error";
            ur.textContent = err.message;
            Toast.show(err.message, "error");

        } finally {
            btn.disabled = false;
            btn.textContent = "Upload & Process";
        }
    }

    return { open, close, submit, initDragDrop };
}


/* ── StudentsModal ──────────────────────────────────────────────────────────── */
const StudentsModal = makeModal({
    bgId: "modal-students",
    dzId: "dz-s", fiId: "fi-s", fnId: "fn-s", btnId: "btn-s", urId: "ur-s",
    apiFn: fd => API.uploadStudents(fd),
    onSuccess: async () => {
        await DropdownInit.refreshBatches("");
        await DataLoader.load();
    },
});


/* ── FeesModal ──────────────────────────────────────────────────────────────── */
const FeesModal = makeModal({
    bgId: "modal-fees",
    dzId: "dz-f", fiId: "fi-f", fnId: "fn-f", btnId: "btn-f", urId: "ur-f",
    apiFn: fd => API.uploadFees(fd),
    onSuccess: async () => DataLoader.load(),
});


const Exporter = {
    /**
     * Triggers a server-side CSV download via the export endpoint.
     * Passes current batch + status filters so the downloaded file
     * matches exactly what the user sees in the table.
     */
    download() {
        const params = new URLSearchParams({
            month: Filters.month(),
            year: Filters.year(),
            batch: Filters.batch(),
            status: Filters.status(),
        });

        window.location.href = `${Config.API_BASE}/api/fees/export?${params.toString()}`;
        Toast.show("Preparing download…", "info");
    },
};


/* ── Toast ──────────────────────────────────────────────────────────────────── */
const Toast = {
    /**
     * Show a temporary notification at the bottom-right of the screen.
     * @param {string} msg
     * @param {"info"|"success"|"error"} type
     * @param {number} duration  milliseconds before auto-dismiss
     */
    show(msg, type = "info", duration = 5000) {
        const root = document.getElementById("toast-root");
        const el = document.createElement("div");
        el.className = `toast t-${type}`;
        el.textContent = msg;
        root.appendChild(el);
        setTimeout(() => el.remove(), duration);
    },
};


/* ── Utility ────────────────────────────────────────────────────────────────── */
/**
 * _esc(str)
 * Escapes HTML special characters to prevent XSS when inserting
 * server-returned strings into innerHTML.
 */
function _esc(str) {
    return String(str)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;");
}


/* ── Boot ───────────────────────────────────────────────────────────────────── */
document.addEventListener("DOMContentLoaded", async () => {
    await DropdownInit.init();       // populate all select dropdowns first
    SortController.init();           // attach sort-click handlers to thead
    FilterController.init();         // attach filter-change handlers
    StudentsModal.initDragDrop();    // enable drag-and-drop for students modal
    FeesModal.initDragDrop();        // enable drag-and-drop for fees modal
    await DataLoader.load();         // initial API fetch + render
});

// Expose modules that are referenced from inline onclick= attributes in HTML
window.TableRenderer = TableRenderer;
window.StudentsModal = StudentsModal;
window.FeesModal = FeesModal;
window.Exporter = Exporter;