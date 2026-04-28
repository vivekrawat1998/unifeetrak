# =============================================================================
# routes/student.py  —  /api/students  endpoints
# =============================================================================
#
# GET  /api/students?month=&year=   — all students LEFT JOINed with fee status
# GET  /api/students/batches        — distinct batch names (for filter dropdown)
# GET  /api/students/semesters      — distinct semesters (optional ?batch= filter)
# POST /api/students/upload         — CSV bulk upsert
#
# =============================================================================

import csv
import io

from flask import Blueprint, jsonify, request
import psycopg2
import psycopg2.extras

from database.db import get_connection

students_bp = Blueprint("students", __name__, url_prefix="/api/students")


# ---------------------------------------------------------------------------
# GET /api/students?month=4&year=2026
# ---------------------------------------------------------------------------
# Core data endpoint required by the assignment.
#
# Performs a single LEFT JOIN between students and fees, filtered strictly
# to the requested month + year on the JOIN condition (not in WHERE) so that
# ALL students appear — those without a payment row show fee_status = "Unpaid".
#
# This single query replaces the naive N+1 approach of fetching students then
# looking up each student's fee separately.
#
# Response row shape:
#   student_id | name | roll_number | batch_name | semester
#   fee_status ("Paid" | "Unpaid") | amount_paid | payment_date
# ---------------------------------------------------------------------------
@students_bp.route("", methods=["GET"])
def get_students():
    # ── Validate required query params ────────────────────────────────────
    try:
        month = int(request.args.get("month", 0))
        year  = int(request.args.get("year",  0))
    except ValueError:
        return jsonify({"error": "month and year must be integers"}), 400

    if not (1 <= month <= 12):
        return jsonify({"error": "month must be 1–12"}), 400
    if not (2000 <= year <= 2100):
        return jsonify({"error": "year must be 2000–2100"}), 400

    # ── Single efficient LEFT JOIN query ──────────────────────────────────
    # Month/year filter lives on the JOIN condition, not in WHERE.
    # This ensures students with no fee row still appear (Unpaid).
    sql = """
        SELECT
            s.student_id,
            s.name,
            s.roll_number,
            s.batch_name,
            s.semester,
            CASE
                WHEN f.fee_id IS NOT NULL THEN 'Paid'
                ELSE                           'Unpaid'
            END                                          AS fee_status,
            COALESCE(f.amount_paid, 0.00)                AS amount_paid,
            f.payment_date
        FROM  students s
        LEFT  JOIN fees f
               ON  f.student_id = s.student_id
               AND f.month      = %(month)s
               AND f.year       = %(year)s
        ORDER BY s.batch_name, s.semester, s.roll_number;
    """

    try:
        with get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(sql, {"month": month, "year": year})
                rows = cur.fetchall()

        data = []
        for row in rows:
            rec = dict(row)
            if rec["payment_date"] is not None:
                rec["payment_date"] = rec["payment_date"].isoformat()
            rec["amount_paid"] = float(rec["amount_paid"])
            data.append(rec)

        return jsonify({"data": data, "month": month, "year": year}), 200

    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


# ---------------------------------------------------------------------------
# GET /api/students/batches
# Distinct batch names for the batch filter dropdown.
# ---------------------------------------------------------------------------
@students_bp.route("/batches", methods=["GET"])
def get_batches():
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT DISTINCT batch_name FROM students ORDER BY batch_name;"
                )
                batches = [row[0] for row in cur.fetchall()]
        return jsonify({"data": batches}), 200
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


# ---------------------------------------------------------------------------
# GET /api/students/semesters[?batch=…]
# Distinct semesters, optionally filtered by batch_name.
# ---------------------------------------------------------------------------
@students_bp.route("/semesters", methods=["GET"])
def get_semesters():
    batch = request.args.get("batch", "").strip()
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                if batch:
                    cur.execute(
                        "SELECT DISTINCT semester FROM students "
                        "WHERE batch_name = %s ORDER BY semester;",
                        (batch,),
                    )
                else:
                    cur.execute(
                        "SELECT DISTINCT semester FROM students ORDER BY semester;"
                    )
                semesters = [row[0] for row in cur.fetchall()]
        return jsonify({"data": semesters}), 200
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


# ---------------------------------------------------------------------------
# POST /api/students/upload
# ---------------------------------------------------------------------------
# Bulk-upsert students from a CSV file.
#
# Required CSV columns:  name | roll_number | batch_name | semester
#
# Uses INSERT … ON CONFLICT (roll_number) DO UPDATE so the endpoint is
# idempotent — uploading the same file twice updates existing students.
# A SAVEPOINT isolates DB errors per row so one bad row never kills the batch.
# ---------------------------------------------------------------------------
@students_bp.route("/upload", methods=["POST"])
def upload_students_csv():

    # ── File validation ───────────────────────────────────────────────────
    if "file" not in request.files:
        return jsonify({"error": "No file part in request"}), 400

    upload = request.files["file"]
    if not upload.filename:
        return jsonify({"error": "No file selected"}), 400
    if not upload.filename.lower().endswith(".csv"):
        return jsonify({"error": "Only .csv files are accepted"}), 400

    try:
        stream = io.StringIO(upload.stream.read().decode("utf-8-sig"))
    except UnicodeDecodeError:
        return jsonify({"error": "File must be UTF-8 encoded"}), 400

    reader = csv.DictReader(stream)
    if reader.fieldnames:
        reader.fieldnames = [f.strip() for f in reader.fieldnames]

    required = {"name", "roll_number", "batch_name", "semester"}
    missing  = required - set(reader.fieldnames or [])
    if missing:
        return jsonify({"error": f"Missing CSV columns: {sorted(missing)}"}), 400

    # ── SQL ───────────────────────────────────────────────────────────────
    check_sql = "SELECT student_id FROM students WHERE roll_number = %s;"

    upsert_sql = """
        INSERT INTO students (name, roll_number, batch_name, semester)
        VALUES (%(name)s, %(roll_number)s, %(batch_name)s, %(semester)s)
        ON CONFLICT (roll_number)
        DO UPDATE SET
            name       = EXCLUDED.name,
            batch_name = EXCLUDED.batch_name,
            semester   = EXCLUDED.semester;
    """

    inserted = updated = skipped = 0
    errors = []

    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                for line_no, row in enumerate(reader, start=2):
                    try:
                        name       = row["name"].strip()
                        roll       = row["roll_number"].strip()
                        batch_name = row["batch_name"].strip()
                        semester   = row["semester"].strip()

                        if not name:       raise ValueError("name is empty")
                        if not roll:       raise ValueError("roll_number is empty")
                        if not batch_name: raise ValueError("batch_name is empty")
                        if not semester:   raise ValueError("semester is empty")

                    except (ValueError, KeyError) as exc:
                        errors.append({"row": line_no, "error": str(exc)})
                        skipped += 1
                        continue

                    cur.execute(check_sql, (roll,))
                    already_exists = cur.fetchone() is not None

                    try:
                        cur.execute("SAVEPOINT sp")
                        cur.execute(upsert_sql, {
                            "name": name, "roll_number": roll,
                            "batch_name": batch_name, "semester": semester,
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
            f"Upload complete — {inserted + updated} student(s) processed "
            f"({inserted} new, {updated} updated, {skipped} skipped)."
        ),
        "inserted": inserted,
        "updated":  updated,
        "skipped":  skipped,
        "errors":   errors,
    }), 200
