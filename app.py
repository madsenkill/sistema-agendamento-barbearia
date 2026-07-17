import os
import re
import secrets
from datetime import date, datetime, time, timedelta
from pathlib import Path
from urllib.parse import urlparse, unquote

import pg8000.dbapi
from dotenv import load_dotenv
from flask import Flask, abort, jsonify, redirect, render_template, request, session, url_for


load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
DATABASE_URL = os.getenv("DATABASE_URL")
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")

SERVICES = {
    "corte": {"name": "Corte de cabelo + sobrancelha", "price_cents": 3000},
    "pente": {"name": "Corte de 1 pente", "price_cents": 2000},
    "barba": {"name": "Barba", "price_cents": 2000},
    "combo": {"name": "Cabelo + barba", "price_cents": 5000},
    "assinatura-corte": {"name": "Assinatura mensal — só corte", "price_cents": 9500},
    "assinatura-combo": {"name": "Assinatura mensal — corte + barba", "price_cents": 14500},
}
SLOTS = tuple(time(hour, 0) for hour in range(9, 20))
MAX_BOOKING_DAYS = 60


def get_secret_key():
    """Uses an env var in production, with a persistent local fallback for first use."""
    configured_key = os.getenv("SECRET_KEY")
    if configured_key:
        return configured_key

    key_file = BASE_DIR / ".flask_secret_key"
    if key_file.exists():
        return key_file.read_text(encoding="utf-8").strip()
    generated_key = secrets.token_urlsafe(48)
    key_file.write_text(generated_key, encoding="utf-8")
    return generated_key


app = Flask(__name__)
app.config.update(
    SECRET_KEY=get_secret_key(),
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.getenv("COOKIE_SECURE", "false").lower() == "true",
)


def db_connection():
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL não foi configurada no arquivo .env.")
    parsed = urlparse(DATABASE_URL)
    if parsed.scheme not in {"postgres", "postgresql"} or not parsed.hostname or not parsed.path:
        raise RuntimeError("DATABASE_URL inválida. Use postgresql://usuario:senha@host:porta/banco")
    return pg8000.dbapi.connect(
        user=unquote(parsed.username or ""),
        password=unquote(parsed.password or ""),
        host=parsed.hostname,
        port=parsed.port or 5432,
        database=parsed.path.lstrip("/"),
        ssl_context=True,
    )


def init_database():
    statements = (
        """
        CREATE TABLE IF NOT EXISTS appointments (
            id BIGSERIAL PRIMARY KEY,
            customer_name VARCHAR(100) NOT NULL,
            whatsapp VARCHAR(20) NOT NULL,
            service_code VARCHAR(40) NOT NULL,
            service_name VARCHAR(120) NOT NULL,
            price_cents INTEGER NOT NULL CHECK (price_cents >= 0),
            appointment_date DATE NOT NULL,
            appointment_time TIME NOT NULL,
            status VARCHAR(16) NOT NULL DEFAULT 'scheduled'
                CHECK (status IN ('scheduled', 'cancelled')),
            created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
            cancelled_at TIMESTAMPTZ
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS blocked_slots (
            id BIGSERIAL PRIMARY KEY,
            blocked_date DATE NOT NULL,
            blocked_time TIME NOT NULL,
            note VARCHAR(140),
            created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (blocked_date, blocked_time)
        )
        """,
        """
        CREATE UNIQUE INDEX IF NOT EXISTS unique_active_appointment_slot
        ON appointments (appointment_date, appointment_time)
        WHERE status = 'scheduled'
        """,
        """
        CREATE INDEX IF NOT EXISTS appointments_schedule_index
        ON appointments (appointment_date, appointment_time)
        """,
    )
    connection = db_connection()
    cursor = connection.cursor()
    try:
        for statement in statements:
            cursor.execute(statement)
        connection.commit()
    finally:
        cursor.close()
        connection.close()


def parse_booking_date(value):
    try:
        selected_date = date.fromisoformat(value)
    except (TypeError, ValueError):
        abort(400, "Escolha uma data válida.")
    if not date.today() <= selected_date <= date.today() + timedelta(days=MAX_BOOKING_DAYS):
        abort(400, f"Escolha uma data entre hoje e os próximos {MAX_BOOKING_DAYS} dias.")
    return selected_date


def parse_slot(value, selected_date):
    try:
        selected_time = time.fromisoformat(value)
    except (TypeError, ValueError):
        abort(400, "Escolha um horário válido.")
    if selected_time not in SLOTS:
        abort(400, "Esse horário não está disponível.")
    if date.today() == selected_date and selected_time <= datetime.now().time().replace(second=0, microsecond=0):
        abort(400, "Esse horário já passou.")
    return selected_time


def is_admin():
    return session.get("admin_logged_in") is True


def require_admin():
    if not is_admin():
        abort(401)


def lock_slot(cursor, selected_date, selected_time):
    """Serializes booking/blocking of one slot across concurrent requests."""
    cursor.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (f"{selected_date.isoformat()}:{selected_time.isoformat()}",))


def format_brl(cents):
    return f"R$ {cents / 100:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


@app.errorhandler(400)
def invalid_request(error):
    return jsonify(status="error", message=getattr(error, "description", "Dados inválidos.")), 400


@app.errorhandler(401)
def unauthorized(error):
    if request.path.startswith("/api/"):
        return jsonify(status="error", message="Acesso não autorizado."), 401
    return redirect(url_for("login"))


@app.get("/")
def index():
    return render_template("index.html", services=SERVICES, max_booking_days=MAX_BOOKING_DAYS)


@app.get("/api/availability")
def availability():
    selected_date = parse_booking_date(request.args.get("date"))
    connection = db_connection()
    cursor = connection.cursor()
    try:
        cursor.execute(
            "SELECT appointment_time FROM appointments WHERE appointment_date = %s AND status = 'scheduled'",
            (selected_date,),
        )
        occupied = {row[0].strftime("%H:%M") for row in cursor.fetchall()}
        cursor.execute("SELECT blocked_time FROM blocked_slots WHERE blocked_date = %s", (selected_date,))
        blocked = {row[0].strftime("%H:%M") for row in cursor.fetchall()}
    finally:
        cursor.close()
        connection.close()

    now = datetime.now()
    unavailable = occupied | blocked
    if selected_date == now.date():
        unavailable |= {slot.strftime("%H:%M") for slot in SLOTS if slot <= now.time()}
    return jsonify(unavailable=sorted(unavailable), slots=[slot.strftime("%H:%M") for slot in SLOTS])


@app.post("/api/bookings")
def create_booking():
    payload = request.get_json(silent=True) or {}
    customer_name = re.sub(r"\s+", " ", str(payload.get("name", "")).strip())
    whatsapp = re.sub(r"\D", "", str(payload.get("whatsapp", "")))
    service_code = payload.get("service")
    if not 2 <= len(customer_name) <= 100:
        abort(400, "Informe seu nome completo.")
    if not 10 <= len(whatsapp) <= 13:
        abort(400, "Informe um WhatsApp válido com DDD.")
    if service_code not in SERVICES:
        abort(400, "Escolha um serviço válido.")

    selected_date = parse_booking_date(payload.get("date"))
    selected_time = parse_slot(payload.get("time"), selected_date)
    service = SERVICES[service_code]
    connection = db_connection()
    cursor = connection.cursor()
    try:
        lock_slot(cursor, selected_date, selected_time)
        cursor.execute(
            "SELECT 1 FROM blocked_slots WHERE blocked_date = %s AND blocked_time = %s",
            (selected_date, selected_time),
        )
        if cursor.fetchone():
            return jsonify(status="error", message="Esse horário foi bloqueado pela barbearia."), 409
        try:
            cursor.execute(
                """
                INSERT INTO appointments
                    (customer_name, whatsapp, service_code, service_name, price_cents, appointment_date, appointment_time)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (customer_name, whatsapp, service_code, service["name"], service["price_cents"], selected_date, selected_time),
            )
            appointment_id = cursor.fetchone()[0]
            connection.commit()
        except Exception as exc:
            connection.rollback()
            if "unique_active_appointment_slot" in str(exc):
                return jsonify(status="error", message="Esse horário acabou de ser reservado. Escolha outro."), 409
            raise
    finally:
        cursor.close()
        connection.close()
    return jsonify(
        status="success",
        booking_id=appointment_id,
        customer_name=customer_name,
        date=selected_date.strftime("%d/%m/%Y"),
        time=selected_time.strftime("%H:%M"),
        service=service["name"],
    ), 201


@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")
        if ADMIN_PASSWORD and secrets.compare_digest(username, ADMIN_USERNAME) and secrets.compare_digest(password, ADMIN_PASSWORD):
            session.clear()
            session["admin_logged_in"] = True
            session["csrf_token"] = secrets.token_urlsafe(32)
            return redirect(url_for("admin_dashboard"))
        error = "Usuário ou senha incorretos."
    return render_template("login.html", error=error)


@app.post("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.get("/admin")
def admin_dashboard():
    require_admin()
    selected_date = request.args.get("date", date.today().isoformat())
    try:
        selected_date = date.fromisoformat(selected_date)
    except ValueError:
        selected_date = date.today()
    connection = db_connection()
    cursor = connection.cursor()
    try:
        cursor.execute(
            """
            SELECT id, customer_name, whatsapp, service_name, price_cents, appointment_time
            FROM appointments
            WHERE appointment_date = %s AND status = 'scheduled'
            ORDER BY appointment_time
            """,
            (selected_date,),
        )
        appointments = [
            {"id": row[0], "name": row[1], "whatsapp": row[2], "service": row[3], "value": format_brl(row[4]), "time": row[5].strftime("%H:%M")}
            for row in cursor.fetchall()
        ]
        cursor.execute("SELECT blocked_time, note FROM blocked_slots WHERE blocked_date = %s", (selected_date,))
        blocks = {row[0].strftime("%H:%M"): row[1] or "Indisponível" for row in cursor.fetchall()}
        cursor.execute("SELECT COUNT(*), COALESCE(SUM(price_cents), 0) FROM appointments WHERE appointment_date = %s AND status = 'scheduled'", (selected_date,))
        count, total_cents = cursor.fetchone()
    finally:
        cursor.close()
        connection.close()
    return render_template("admin.html", selected_date=selected_date.isoformat(), appointments=appointments, blocks=blocks, slots=[slot.strftime("%H:%M") for slot in SLOTS], count=count, total=format_brl(total_cents))


@app.post("/api/admin/appointments/<int:appointment_id>/cancel")
def cancel_appointment(appointment_id):
    require_admin()
    connection = db_connection()
    cursor = connection.cursor()
    try:
        cursor.execute("UPDATE appointments SET status = 'cancelled', cancelled_at = CURRENT_TIMESTAMP WHERE id = %s AND status = 'scheduled'", (appointment_id,))
        if cursor.rowcount != 1:
            abort(404, "Agendamento não encontrado ou já cancelado.")
        connection.commit()
    finally:
        cursor.close()
        connection.close()
    return jsonify(status="success", message="Agendamento cancelado e horário liberado.")


@app.post("/api/admin/blocks")
def create_block():
    require_admin()
    payload = request.get_json(silent=True) or {}
    try:
        blocked_date = date.fromisoformat(payload.get("date", ""))
        blocked_time = time.fromisoformat(payload.get("time", ""))
    except ValueError:
        abort(400, "Data ou horário inválido.")
    if blocked_time not in SLOTS:
        abort(400, "Esse horário não faz parte da agenda.")
    note = str(payload.get("note", "")).strip()[:140] or None
    connection = db_connection()
    cursor = connection.cursor()
    try:
        lock_slot(cursor, blocked_date, blocked_time)
        cursor.execute("SELECT 1 FROM appointments WHERE appointment_date = %s AND appointment_time = %s AND status = 'scheduled'", (blocked_date, blocked_time))
        if cursor.fetchone():
            return jsonify(status="error", message="Cancele o agendamento antes de bloquear esse horário."), 409
        try:
            cursor.execute("INSERT INTO blocked_slots (blocked_date, blocked_time, note) VALUES (%s, %s, %s)", (blocked_date, blocked_time, note))
            connection.commit()
        except Exception as exc:
            connection.rollback()
            if "blocked_slots_blocked_date_blocked_time_key" in str(exc):
                return jsonify(status="error", message="Esse horário já está bloqueado."), 409
            raise
    finally:
        cursor.close()
        connection.close()
    return jsonify(status="success", message="Horário bloqueado.")


@app.delete("/api/admin/blocks/<date_value>/<time_value>")
def delete_block(date_value, time_value):
    require_admin()
    try:
        blocked_date = date.fromisoformat(date_value)
        blocked_time = time.fromisoformat(time_value)
    except ValueError:
        abort(400, "Data ou horário inválido.")
    connection = db_connection()
    cursor = connection.cursor()
    try:
        cursor.execute("DELETE FROM blocked_slots WHERE blocked_date = %s AND blocked_time = %s", (blocked_date, blocked_time))
        connection.commit()
    finally:
        cursor.close()
        connection.close()
    return jsonify(status="success", message="Horário liberado.")


init_database()


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=os.getenv("FLASK_DEBUG", "false").lower() == "true")
