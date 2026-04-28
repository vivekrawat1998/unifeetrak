# routes/fees.py

import csv
import io
from datetime import date

from flask import Blueprint, jsonify, request, send_file
import psycopg2
import psycopg2.extras

from database.db import get_connection

fees_bp = Blueprint("fees", __name__, url_prefix="/api/fees")


def _parse_month_year(args):
    try:
        month = int(args.get("month", 0))
        year  = int(args.get("year",  0))
    except ValueError:
        raise ValueError("month and year must be integers")
    if not (1 <= month <= 12):
        raise ValueError("month must be 1-12")
    if not (2000 <= year <= 2100):
        raise ValueError("year must be 2000-2100")
    return month, year


@fees_bp.route("/stats", methods=["GET"])
def get_stats():
    try:
        month, year = _parse_month_year(request.args)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    batch      = request.args.get("batch",      "").strip()
    batch_year = request.args.get("batch_year", "").strip()

    where_parts = []
    params = {"month": month, "year": year}

    if batch:
        where_parts.append("s.batch_name = %(batch)s")
        params["batch"] = batch
    elif batch_year:
        where_parts.append("s.batch_name LIKE %(batch_year_like)s")
        params["batch_year_like"] = f"{batch_year}%"

    where_sql = ("WHERE " + " AND ".join(where_parts)) if where_parts else ""

    sql = f"""
        SELECT
            COUNT(*)                                AS total_students,
            COUNT(f.fee_id)                         AS paid_count,
            COUNT(*) - COUNT(f.fee_id)              AS unpaid_count,
            COALESCE(SUM(f.amount_paid), 0.00)      AS total_collected
        FROM  students s
        LEFT  JOIN fees f
               ON  f.student_id = s.student_id
               AND f.month      = %(month)s
               AND f.year       = %(year)s
        {where_sql};
    """

    try:
        with get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(sql, params)
                row = dict(cur.fetchone())
        row["total_collected"] = float(row["total_collected"])
        return jsonify(row), 200
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@fees_bp.route("/upload", methods=["POST"])
def upload_csv():
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

    required = {"roll_number", "month", "year", "amount_paid"}
    missing  = required - set(reader.fieldnames or [])
    if missing:
        return jsonify({"error": f"Missing CSV columns: {sorted(missing)}"}), 400

    find_student_sql = "SELECT student_id FROM students WHERE roll_number = %s;"
    check_fee_sql    = "SELECT fee_id FROM fees WHERE student_id=%s AND month=%s AND year=%s;"
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
                    try:
                        roll   = row["roll_number"].strip()
                        month  = int(row["month"].strip())
                        year   = int(row["year"].strip())
                        amount = float(row["amount_paid"].strip())
                        raw_pd = row.get("payment_date", "").strip()
                        pdate  = raw_pd if raw_pd else date.today().isoformat()
                        if not roll:               raise ValueError("roll_number empty")
                        if not (1 <= month <= 12): raise ValueError("month out of range")
                        if not (2000<=year<=2100): raise ValueError("year out of range")
                        if amount < 0:             raise ValueError("amount negative")
                    except (ValueError, KeyError) as exc:
                        errors.append({"row": line_no, "error": str(exc)})
                        skipped += 1
                        continue

                    cur.execute(find_student_sql, (roll,))
                    student_row = cur.fetchone()
                    if student_row is None:
                        errors.append({"row": line_no,
                                       "error": f"roll_number '{roll}' not found"})
                        skipped += 1
                        continue

                    student_id = student_row[0]
                    cur.execute(check_fee_sql, (student_id, month, year))
                    already_exists = cur.fetchone() is not None

                    try:
                        cur.execute("SAVEPOINT sp")
                        cur.execute(upsert_sql, {
                            "student_id": student_id,
                            "month": month, "year": year,
                            "amount": amount, "pdate": pdate,
                        })
                        cur.execute("RELEASE SAVEPOINT sp")
                        if already_exists: updated  += 1
                        else:              inserted += 1
                    except psycopg2.Error as db_exc:
                        cur.execute("ROLLBACK TO SAVEPOINT sp")
                        errors.append({"row": line_no,
                                       "error": f"DB: {db_exc.pgerror or str(db_exc)}"})
                        skipped += 1

            conn.commit()
    except Exception as exc:
        return jsonify({"error": f"Upload failed: {str(exc)}"}), 500

    return jsonify({
        "message": (
            f"Upload complete — {inserted+updated} row(s) processed "
            f"({inserted} new, {updated} updated, {skipped} skipped)."
        ),
        "inserted": inserted, "updated": updated,
        "skipped":  skipped,  "errors":  errors,
    }), 200


# @fees_bp.route("/export", methods=["GET"])
# def export_csv():


@fees_bp.route("/export", methods=["GET"])
def export_csv():
    try:
        month, year = _parse_month_year(request.args)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    batch = request.args.get("batch", "").strip()
    status = request.args.get("status", "").strip()  # "Paid" | "Unpaid" | ""

    params = {"month": month, "year": year}
    batch_clause = ""
    if batch:
        batch_clause = "AND s.batch_name = %(batch)s"
        params["batch"] = batch

    sql = f"""
        SELECT
            s.student_id,
            s.name,
            s.roll_number,
            s.batch_name,
            s.semester,
            CASE WHEN f.fee_id IS NOT NULL THEN 'Paid' ELSE 'Unpaid' END AS fee_status,
            COALESCE(f.amount_paid, 0.00) AS amount_paid,
            f.payment_date
        FROM students s
        LEFT JOIN fees f
               ON f.student_id = s.student_id
              AND f.month = %(month)s
              AND f.year = %(year)s
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

    if status:
        rows = [r for r in rows if r["fee_status"] == status]

    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow([
        "Student ID",
        "Name",
        "Roll Number",
        "Batch",
        "Semester",
        "Fee Status",
        "Amount Paid (Rs.)",
        "Payment Date",
    ])

    for r in rows:
        pd_val = ""
        if r["payment_date"]:
            if isinstance(r["payment_date"], date):
                pd_val = r["payment_date"].strftime("%d-%b-%Y")
            else:
                pd_val = str(r["payment_date"])

        writer.writerow([
            r["student_id"],
            r["name"],
            r["roll_number"],
            r["batch_name"],
            r["semester"],
            r["fee_status"],
            f"{float(r['amount_paid']):.2f}",
            pd_val,
        ])

    filename = f"fees_{year}_{month:02d}.csv"
    return send_file(
        io.BytesIO(output.getvalue().encode("utf-8-sig")),
        mimetype="text/csv",
        as_attachment=True,
        download_name=filename,
    )
    try:
        month, year = _parse_month_year(request.args)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    batch  = request.args.get("batch",  "").strip()
    status = request.args.get("status", "").strip()

    where_parts = []
    params = {"month": month, "year": year}

    if batch:
        where_parts.append("s.batch_name = %(batch)s")
        params["batch"] = batch

    where_sql = ("WHERE " + " AND ".join(where_parts)) if where_parts else ""

    sql = f"""
        SELECT
            s.student_id,
            s.name,
            s.roll_number,
            s.batch_name,
            s.semester,
            CASE WHEN f.fee_id IS NOT NULL THEN 'Paid' ELSE 'Unpaid' END AS fee_status,
            COALESCE(f.amount_paid, 0.00) AS amount_paid,
            f.payment_date
        FROM  students s
        LEFT  JOIN fees f
               ON  f.student_id = s.student_id
               AND f.month      = %(month)s
               AND f.year       = %(year)s
        {where_sql}
        ORDER BY s.batch_name, s.semester, s.roll_number;
    """

    try:
        with get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(sql, params)
                rows = cur.fetchall()
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500

    if status:
        rows = [r for r in rows if r["fee_status"] == status]

    output = io.StringIO()
    writer = csv.writer(output, quoting=csv.QUOTE_ALL)
    writer.writerow([
        "Student ID", "Name", "Roll Number", "Batch", "Semester",
        "Fee Status", "Amount Paid (Rs.)", "Payment Date (YYYY-MM-DD)",
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
        io.BytesIO(output.getvalue().encode("utf-8")),
        mimetype="text/csv",
        as_attachment=True,
        download_name=filename,
    )