from __future__ import annotations

import os
import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from faker import Faker
from flask import (
    Flask,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from sqlalchemy import asc, desc, func, select
from sqlalchemy.exc import IntegrityError

from admin_panel.models import AuditLog, User, create_sqlite_db, init_db


EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
ROLES: Tuple[str, ...] = ("admin", "member", "viewer")
LICENSE_TYPES: Tuple[str, ...] = ("Basic", "Pro", "Enterprise")
PAGE_SIZE: int = 10
SEED_USER_COUNT: int = 15
FAKER_SEED: int = 1337


def create_app() -> Flask:
    """Create the Flask mock IT admin panel app."""

    app = Flask(__name__)
    app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-secret-key-change-me")

    os.makedirs(app.instance_path, exist_ok=True)
    default_db_path = os.path.join(app.instance_path, "admin_panel.db")
    db_url = os.environ.get("ADMIN_PANEL_DATABASE_URL", f"sqlite:///{default_db_path}")
    app.config["ADMIN_PANEL_DATABASE_URL"] = db_url

    db = create_sqlite_db(db_url)
    init_db(db)

    _seed_if_needed(db)

    @app.context_processor
    def _inject_globals() -> Dict[str, Any]:
        return {
            "ADMIN_USERNAME": "admin",
            "ROLES": ROLES,
            "LICENSE_TYPES": LICENSE_TYPES,
        }

    def _audit(actor: str, action: str, target: str, details: str) -> None:
        with db.session() as s:
            s.add(
                AuditLog(
                    timestamp=datetime.utcnow(),
                    actor=actor,
                    action=action,
                    target=target,
                    details=details,
                )
            )
            s.commit()

    def _current_actor() -> str:
        return str(session.get("actor") or "anonymous")

    def _paginate(page: int, page_size: int, total: int) -> Tuple[int, int, int]:
        pages = max(1, (total + page_size - 1) // page_size)
        page = max(1, min(page, pages))
        offset = (page - 1) * page_size
        return page, pages, offset

    @app.get("/")
    def index() -> Any:
        return redirect(url_for("admin_users"))

    @app.get("/admin/login")
    def admin_login() -> Any:
        return render_template("login.html")

    @app.post("/admin/login")
    def admin_login_post() -> Any:
        username = (request.form.get("username") or "").strip()
        password = (request.form.get("password") or "").strip()
        if not username or not password:
            flash("Username and password are required.", "danger")
            return redirect(url_for("admin_login"))

        if username == "admin" and password == "admin123":
            session["actor"] = "admin"
            flash("Logged in successfully.", "success")
            _audit(actor="admin", action="login", target="admin", details="Admin logged in.")
            return redirect(url_for("admin_users"))

        flash("Invalid credentials.", "danger")
        _audit(actor="anonymous", action="login_failed", target=username or "unknown", details="Invalid credentials.")
        return redirect(url_for("admin_login"))

    @app.get("/admin/users")
    def admin_users() -> Any:
        q = (request.args.get("q") or "").strip()
        page = int(request.args.get("page") or "1")

        with db.session() as s:
            base = select(User)
            count_stmt = select(func.count()).select_from(User)
            if q:
                base = base.where(User.email.ilike(f"%{q}%"))
                count_stmt = count_stmt.where(User.email.ilike(f"%{q}%"))

            total = int(s.execute(count_stmt).scalar_one())
            page, pages, offset = _paginate(page, PAGE_SIZE, total)

            users = (
                s.execute(base.order_by(asc(User.id)).offset(offset).limit(PAGE_SIZE))
                .scalars()
                .all()
            )

        return render_template(
            "users.html",
            users=users,
            q=q,
            page=page,
            pages=pages,
            total=total,
            page_size=PAGE_SIZE,
        )

    @app.get("/admin/users/<int:user_id>")
    def admin_user_detail(user_id: int) -> Any:
        with db.session() as s:
            user = s.get(User, user_id)
            if not user:
                flash("User not found.", "danger")
                return redirect(url_for("admin_users"))
            return render_template("user_detail.html", user=user)

    @app.post("/admin/users/create")
    def admin_users_create() -> Any:
        email = (request.form.get("email") or "").strip().lower()
        full_name = (request.form.get("full_name") or "").strip()
        role = (request.form.get("role") or "").strip()
        active = request.form.get("active") == "on"

        if not email or not full_name or not role:
            flash("Email, full name, and role are required.", "danger")
            return redirect(url_for("admin_users"))
        if not EMAIL_RE.match(email):
            flash("Invalid email format.", "danger")
            return redirect(url_for("admin_users"))
        if role not in ROLES:
            flash("Invalid role selected.", "danger")
            return redirect(url_for("admin_users"))

        with db.session() as s:
            s.add(User(email=email, full_name=full_name, role=role, active=active))
            try:
                s.commit()
            except IntegrityError:
                s.rollback()
                flash("A user with that email already exists.", "danger")
                return redirect(url_for("admin_users"))

        _audit(
            actor=_current_actor(),
            action="create_user",
            target=email,
            details=f"Created user {email} role={role} active={active}.",
        )
        flash("User created successfully.", "success")
        return redirect(url_for("admin_users"))

    @app.post("/admin/users/<int:user_id>/delete")
    def admin_users_delete(user_id: int) -> Any:
        with db.session() as s:
            user = s.get(User, user_id)
            if not user:
                flash("User not found.", "danger")
                return redirect(url_for("admin_users"))
            email = user.email
            s.delete(user)
            s.commit()

        _audit(
            actor=_current_actor(),
            action="delete_user",
            target=email,
            details=f"Deleted user id={user_id} email={email}.",
        )
        flash("User deleted successfully.", "success")
        return redirect(url_for("admin_users"))

    @app.get("/admin/reset-password")
    def admin_reset_password() -> Any:
        return render_template("reset_password.html")

    @app.post("/admin/reset-password")
    def admin_reset_password_post() -> Any:
        email = (request.form.get("email") or "").strip().lower()
        if not email:
            flash("Email is required.", "danger")
            return redirect(url_for("admin_reset_password"))
        if not EMAIL_RE.match(email):
            flash("Invalid email format.", "danger")
            return redirect(url_for("admin_reset_password"))

        _audit(
            actor=_current_actor(),
            action="reset_password",
            target=email,
            details="Password reset link generated (mock).",
        )
        flash(f"Reset link sent to {email}.", "success")
        return redirect(url_for("admin_users"))

    @app.post("/admin/users/<int:user_id>/assign-license")
    def admin_assign_license(user_id: int) -> Any:
        license_type = (request.form.get("license_type") or "").strip()
        if not license_type:
            flash("License type is required.", "danger")
            return redirect(url_for("admin_user_detail", user_id=user_id))
        if license_type not in LICENSE_TYPES:
            flash("Invalid license type selected.", "danger")
            return redirect(url_for("admin_user_detail", user_id=user_id))

        with db.session() as s:
            user = s.get(User, user_id)
            if not user:
                flash("User not found.", "danger")
                return redirect(url_for("admin_users"))
            user.license_type = license_type
            email = user.email
            s.commit()

        _audit(
            actor=_current_actor(),
            action="assign_license",
            target=email,
            details=f"Assigned license={license_type} to user id={user_id}.",
        )
        flash("License assigned successfully.", "success")
        return redirect(url_for("admin_users"))

    @app.get("/admin/audit")
    def admin_audit() -> Any:
        action_filter = (request.args.get("action") or "").strip()
        page = int(request.args.get("page") or "1")

        with db.session() as s:
            base = select(AuditLog)
            count_stmt = select(func.count()).select_from(AuditLog)
            if action_filter:
                base = base.where(AuditLog.action == action_filter)
                count_stmt = count_stmt.where(AuditLog.action == action_filter)

            total = int(s.execute(count_stmt).scalar_one())
            page, pages, offset = _paginate(page, PAGE_SIZE, total)
            rows = (
                s.execute(base.order_by(desc(AuditLog.timestamp)).offset(offset).limit(PAGE_SIZE))
                .scalars()
                .all()
            )

            action_types = (
                s.execute(select(AuditLog.action).distinct().order_by(asc(AuditLog.action)))
                .scalars()
                .all()
            )

        return render_template(
            "audit_log.html",
            rows=rows,
            page=page,
            pages=pages,
            total=total,
            page_size=PAGE_SIZE,
            action_filter=action_filter,
            action_types=action_types,
        )

    return app


def _seed_if_needed(db: Any) -> None:
    """Seed the DB with deterministic fake users if empty."""

    fake = Faker()
    Faker.seed(FAKER_SEED)

    with db.session() as s:
        existing = int(s.execute(select(func.count()).select_from(User)).scalar_one())
        if existing >= SEED_USER_COUNT:
            return

        created = 0
        # Keep generating until we reach SEED_USER_COUNT unique emails.
        while existing + created < SEED_USER_COUNT:
            email = fake.unique.email().lower()
            full_name = fake.name()
            role = fake.random_element(elements=ROLES)
            active = fake.boolean(chance_of_getting_true=85)
            s.add(User(email=email, full_name=full_name, role=role, active=active))
            created += 1

        s.commit()


app = create_app()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")), debug=True)
