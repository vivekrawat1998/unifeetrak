# =============================================================================
# routes/fees.py  —  /api/fees  endpoints
# =============================================================================
#
# GET  /api/fees/stats?month=&year=  — aggregate counts for stat cards
# POST /api/fees/upload              — CSV bulk upsert into fees table
# GET  /api/fees/export?month=&year= — download filtered view as CSV
#
# =============================================================================

import csv
import io
from datetime import date

from flask import Blueprint, jsonify, request, send_file
import psycopg2
import psycopg2.extras

from database.db import get_connection

fees_bp = Blueprint("fees", __name__, url_prefix="/api/fees")


# ---------------------------------------------------------------------------
# Helper — parse & validate month / year query params
# ---------------------------------------------------------------------------
def _parse_month_year(args: dict) -> tuple[int, int]:
    """Return (month, year) as ints; raise ValueError on bad input."""
    month = int(args.get("month", 0))
    year  = int(args.get("year",  0))
    if not (1 <= month <= 12):
        raise ValueError("month must be 1–12")
    if not (2000 <= year <= 2100):
        raise ValueError("year must be 2000–2100")
    return month, year


# ---------------------------------------------------------------------------
# GET /api/fees/stats?month=4&year=2026
# ---------------------------------------------------------------------------
# Aggregate counts for the four dashboard stat-cards.
# Uses the same LEFT JOIN logic as the students endpoint so numbers are
# always consistent with the table.
# ---------------------------------------------------------------------------
@fees_bp.route("/stats", methods=["GET"])
def get_stats():
    try:
        month, year = _parse_month_year(request.args)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    sql = """
        SELECT
            COUNT(*)                                  AS total_students,
            COUNT(f.fee_id)                           AS paid_count,
            COUNT(*) - COUNT(f.fee_id)                AS unpaid_count,
            COALESCE(SUM(f.amount_paid), 0.00)        AS total_collected
        FROM  students s
        LEFT  JOIN fees f
               ON  f.student_id = s.student_id
               AND f.month      = %(month)s
               AND f.year       = %(year)s;
    """
    try:
        with get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(sql, {"month": month, "year": year})
                row = dict(cur.fetchone())

        row["total_collected"] = float(row["total_collected"])
        return jsonify(row), 200

    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


# ---------------------------------------------------------------------------
# POST /api/fees/upload
# ---------------------------------------------------------------------------
# Accepts multipart/form-data CSV.
#
# Required CSV columns:  roll_number | month | year | amount_paid
# Optional CSV column:   payment_date  (YYYY-MM-DD, defaults to today)
#
# Key implementation decisions:
#   1. Resolve roll_number → student_id with a SELECT before INSERT.
#      This avoids a NULL FK crash from a subquery returning no rows.
#   2. Check fee existence BEFORE the upsert for an accurate count.
#   3. SAVEPOINT per row isolates DB errors — one bad row keeps the rest.
#   4. updated_at is omitted from the SQL; the DB trigger manages it.
#   5. Single COMMIT at the end.
# ---------------------------------------------------------------------------
@fees_bp.route("/upload", methods=["POST"])
def upload_csv():

    # ── File validation ───────────────────────────────────────────────────
    if "file" not in request.files:
        return jsonify({"error": "No file part in request"}), 400

    upload = request.files["file"]
    if not upload.filename:
        return jsonify({"error": "No file selected"}), 400
    if not upload.filename.lower().endswith(".csv"):
        return jsonify({"error": "Only .csv files are accepted"}), 400

    try:
        # utf-8-sig strips the BOM that Excel sometimes prepends
        stream = io.StringIO(upload.stream.read().decode("utf-8-sig"))
    except UnicodeDecodeError:
        return jsonify({"error": "File must be UTF-8 encoded"}), 400

    reader = csv.DictReader(stream)
    if reader.fieldnames:
        reader.fieldnames = [f.strip() for f in reader.fieldnames]

    required = {"roll_number", "month", "year", "amount_paid"}
    missing  = required - set(reader.fieldnames or [])
    if missing:
        return jsonify({"error": f"Missing CSV columns: {sorted(missing)}"}), 400

    # ── SQL statements ────────────────────────────────────────────────────
    find_student_sql = "SELECT student_id FROM students WHERE roll_number = %s;"

    check_fee_sql = """
        SELECT fee_id FROM fees
        WHERE student_id = %s AND month = %s AND year = %s;
    """

    # updated_at intentionally absent — handled automatically by DB trigger
    upsert_sql = """
        INSERT INTO fees (student_id, month, year, amount_paid, payment_date)
        VALUES (%(student_id)s, %(month)s, %(year)s, %(amount)s, %(pdate)s)
        ON CONFLICT (student_id, month, year)
        DO UPDATE SET
            amount_paid  = EXCLUDED.amount_paid,
            payment_date = EXCLUDED.payment_date;
    """

    inserted = updated = skipped = 0
    errors   = []

    try:
        with get_connection() as conn:
            with conn.cursor() as cur:

                for line_no, row in enumerate(reader, start=2):

                    # ── Parse & validate row fields ────────────────────────
                    try:
                        roll   = row["roll_number"].strip()
                        month  = int(row["month"].strip())
                        year   = int(row["year"].strip())
                        amount = float(row["amount_paid"].strip())
                        raw_pd = row.get("payment_date", "").strip()
                        pdate  = raw_pd if raw_pd else date.today().isoformat()

                        if not roll:
                            raise ValueError("roll_number is empty")
                        if not (1 <= month <= 12):
                            raise ValueError(f"month '{month}' must be 1–12")
                        if not (2000 <= year <= 2100):
                            raise ValueError(f"year '{year}' must be 2000–2100")
                        if amount < 0:
                            raise ValueError("amount_paid cannot be negative")

                    except (ValueError, KeyError) as exc:
                        errors.append({"row": line_no, "error": str(exc)})
                        skipped += 1
                        continue

                    # ── Resolve roll_number → student_id ───────────────────
                    cur.execute(find_student_sql, (roll,))
                    student_row = cur.fetchone()
                    if student_row is None:
                        errors.append({
                            "row":   line_no,
                            "error": f"roll_number '{roll}' not found in students",
                        })
                        skipped += 1
                        continue

                    student_id = student_row[0]

                    # ── Check existence before upsert (accurate counting) ───
                    cur.execute(check_fee_sql, (student_id, month, year))
                    already_exists = cur.fetchone() is not None

                    # ── Upsert inside a SAVEPOINT ──────────────────────────
                    try:
                        cur.execute("SAVEPOINT sp")
                        cur.execute(upsert_sql, {
                            "student_id": student_id,
                            "month":      month,
                            "year":       year,
                            "amount":     amount,
                            "pdate":      pdate,
                        })
                        cur.execute("RELEASE SAVEPOINT sp")

                        if already_exists:
                            updated += 1
                        else:
                            inserted += 1

                    except psycopg2.Error as db_exc:
                        cur.execute("ROLLBACK TO SAVEPOINT sp")
                        errors.append({
                            "row":   line_no,
                            "error": f"DB error: {db_exc.pgerror or str(db_exc)}",
                        })
                        skipped += 1

            conn.commit()

    except Exception as exc:
        return jsonify({"error": f"Upload failed: {str(exc)}"}), 500

    return jsonify({
        "message": (
            f"Upload complete — {inserted + updated} row(s) processed "
            f"({inserted} new, {updated} updated, {skipped} skipped)."
        ),
        "inserted": inserted,
        "updated":  updated,
        "skipped":  skipped,
        "errors":   errors,
    }), 200


# ---------------------------------------------------------------------------
# GET /api/fees/export?month=4&year=2026[&batch=…][&status=…]
# ---------------------------------------------------------------------------
# Streams the current filtered view as a downloadable CSV.
# Server-side filtering keeps the export consistent with what the user sees.
# ---------------------------------------------------------------------------
@fees_bp.route("/export", methods=["GET"])
def export_csv():
    try:
        month, year = _parse_month_year(request.args)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    batch  = request.args.get("batch",  "").strip()
    status = request.args.get("status", "").strip()  # "Paid" | "Unpaid" | ""

    params       = {"month": month, "year": year}
    batch_clause = ""
    if batch:
        batch_clause    = "AND s.batch_name = %(batch)s"
        params["batch"] = batch

    sql = f"""
        SELECT
            s.student_id,
            s.name,
            s.roll_number,
            s.batch_name,
            s.semester,
            CASE WHEN f.fee_id IS NOT NULL THEN 'Paid' ELSE 'Unpaid' END AS fee_status,
            COALESCE(f.amount_paid, 0.00)  AS amount_paid,
            f.payment_date
        FROM  students s
        LEFT  JOIN fees f
               ON  f.student_id = s.student_id
               AND f.month      = %(month)s
               AND f.year       = %(year)s
        WHERE 1=1 {batch_clause}
        ORDER BY s.batch_name, s.semester, s.roll_number;
    """

    try:
        with get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(sql, params)
                rows = cur.fetchall()
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500

    # Optional in-memory status filter (keeps export consistent with table)
    if status:
        rows = [r for r in rows if r["fee_status"] == status]

    # Build CSV in memory
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Student ID", "Name", "Roll Number", "Batch", "Semester",
        "Fee Status", "Amount Paid (Rs.)", "Payment Date",
    ])
    for r in rows:
        pd_val = (
            r["payment_date"].isoformat()
            if isinstance(r["payment_date"], date)
            else (r["payment_date"] or "")
        )
        writer.writerow([
            r["student_id"], r["name"], r["roll_number"],
            r["batch_name"], r["semester"], r["fee_status"],
            f"{float(r['amount_paid']):.2f}", pd_val,
        ])

    filename = f"fees_{year}_{month:02d}.csv"
    return send_file(
        io.BytesIO(output.getvalue().encode("utf-8-sig")),  # utf-8-sig opens cleanly in Excel
        mimetype="text/csv",
        as_attachment=True,
        download_name=filename,
    )
