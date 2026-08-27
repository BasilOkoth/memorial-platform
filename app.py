from __future__ import annotations

import hashlib
from io import BytesIO
import hmac
import os
import re
import secrets
from datetime import datetime, timedelta, timezone
from functools import wraps
from pathlib import Path
from typing import Any, Callable
from urllib.parse import quote

from dotenv import load_dotenv
from flask import (
    Flask,
    Response,
    abort,
    flash,
    redirect,
    render_template,
    request,
    send_file,
    session,
    url_for,
)
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    LargeBinary,
    String,
    Text,
    func,
    select,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.security import check_password_hash, generate_password_hash


load_dotenv()


class Base(DeclarativeBase):
    pass


db = SQLAlchemy(model_class=Base)


class Memorial(db.Model):
    __tablename__ = "memorials"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(80), unique=True, nullable=False, index=True)
    memorial_name: Mapped[str] = mapped_column(String(160), nullable=False)
    birth_date: Mapped[str] = mapped_column(String(60), default="", nullable=False)
    death_date: Mapped[str] = mapped_column(String(60), default="", nullable=False)
    hero_message: Mapped[str] = mapped_column(
        String(320),
        default="Forever loved, forever remembered, forever in our hearts.",
        nullable=False,
    )
    biography: Mapped[str] = mapped_column(Text, default="", nullable=False)

    burial_date: Mapped[str] = mapped_column(String(160), default="", nullable=False)
    burial_venue: Mapped[str] = mapped_column(String(260), default="", nullable=False)
    burial_map_url: Mapped[str] = mapped_column(String(600), default="", nullable=False)
    livestream_url: Mapped[str] = mapped_column(String(600), default="", nullable=False)

    mpesa_number: Mapped[str] = mapped_column(String(50), default="", nullable=False)
    mpesa_name: Mapped[str] = mapped_column(String(140), default="", nullable=False)
    contribution_purpose: Mapped[str] = mapped_column(String(220), default="", nullable=False)
    whatsapp_url: Mapped[str] = mapped_column(String(600), default="", nullable=False)

    family_acknowledgement: Mapped[str] = mapped_column(Text, default="", nullable=False)
    theme: Mapped[str] = mapped_column(String(30), default="classic", nullable=False)
    is_published: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False, index=True
    )

    family_password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )


class Tribute(db.Model):
    __tablename__ = "tributes"

    id: Mapped[int] = mapped_column(primary_key=True)
    memorial_id: Mapped[int] = mapped_column(
        ForeignKey("memorials.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    participant_name: Mapped[str] = mapped_column(String(90), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )
    ip_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    is_visible: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False, index=True
    )
    is_acknowledged: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False, index=True
    )


class MediaAsset(db.Model):
    __tablename__ = "media_assets"

    id: Mapped[int] = mapped_column(primary_key=True)
    memorial_id: Mapped[int] = mapped_column(
        ForeignKey("memorials.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    kind: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    data: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )


class MemorialEvent(db.Model):
    __tablename__ = "memorial_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    memorial_id: Mapped[int] = mapped_column(
        ForeignKey("memorials.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    service_datetime: Mapped[str] = mapped_column(String(40), default="", nullable=False)
    timezone_offset: Mapped[str] = mapped_column(
        String(6), default="+03:00", nullable=False
    )


class MemorialRequest(db.Model):
    __tablename__ = "memorial_requests"

    id: Mapped[int] = mapped_column(primary_key=True)
    reference_code: Mapped[str] = mapped_column(
        String(20),
        unique=True,
        nullable=False,
        index=True,
        default=lambda: f"EM-{secrets.token_hex(4).upper()}",
    )

    # Person requesting the memorial
    requester_name: Mapped[str] = mapped_column(String(160), nullable=False)
    relationship: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    phone: Mapped[str] = mapped_column(String(60), nullable=False)
    email: Mapped[str] = mapped_column(String(180), default="", nullable=False)
    preferred_contact: Mapped[str] = mapped_column(
        String(30), default="whatsapp", nullable=False
    )

    # Loved one
    memorial_name: Mapped[str] = mapped_column(String(160), nullable=False)
    display_name: Mapped[str] = mapped_column(String(160), default="", nullable=False)
    birth_date: Mapped[str] = mapped_column(String(60), default="", nullable=False)
    death_date: Mapped[str] = mapped_column(String(60), default="", nullable=False)
    place_of_birth: Mapped[str] = mapped_column(String(160), default="", nullable=False)
    memorial_message: Mapped[str] = mapped_column(String(320), default="", nullable=False)
    biography: Mapped[str] = mapped_column(Text, default="", nullable=False)

    # Materials available
    has_portrait: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    has_gallery: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    has_eulogy: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    has_programme: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Funeral information
    funeral_date: Mapped[str] = mapped_column(String(160), default="", nullable=False)
    service_datetime: Mapped[str] = mapped_column(String(40), default="", nullable=False)
    timezone_offset: Mapped[str] = mapped_column(
        String(6), default="+03:00", nullable=False
    )
    burial_venue: Mapped[str] = mapped_column(String(260), default="", nullable=False)
    burial_map_url: Mapped[str] = mapped_column(String(600), default="", nullable=False)
    livestream_url: Mapped[str] = mapped_column(String(600), default="", nullable=False)

    # Family support
    mpesa_number: Mapped[str] = mapped_column(String(50), default="", nullable=False)
    mpesa_name: Mapped[str] = mapped_column(String(140), default="", nullable=False)
    contribution_purpose: Mapped[str] = mapped_column(
        String(220), default="", nullable=False
    )
    whatsapp_url: Mapped[str] = mapped_column(String(600), default="", nullable=False)

    # Family acknowledgement and preferences
    family_acknowledgement: Mapped[str] = mapped_column(
        Text, default="", nullable=False
    )
    preferred_theme: Mapped[str] = mapped_column(
        String(30), default="classic", nullable=False
    )
    preferred_slug: Mapped[str] = mapped_column(String(80), default="", nullable=False)
    publishing_preference: Mapped[str] = mapped_column(
        String(40), default="review_first", nullable=False
    )
    additional_requests: Mapped[str] = mapped_column(Text, default="", nullable=False)

    consent: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    status: Mapped[str] = mapped_column(
        String(30), default="new", nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )


def database_uri() -> str:
    value = os.getenv("DATABASE_URL", "").strip()
    if value:
        if value.startswith("postgres://"):
            value = value.replace("postgres://", "postgresql+psycopg://", 1)
        elif value.startswith("postgresql://"):
            value = value.replace("postgresql://", "postgresql+psycopg://", 1)
        return value

    path = Path(
        os.getenv("DATABASE_PATH", "instance/memorial-platform.db")
    ).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{path.resolve()}"


def create_app() -> Flask:
    app = Flask(__name__)
    app.config.update(
        SECRET_KEY=os.getenv("SECRET_KEY") or secrets.token_hex(32),
        SQLALCHEMY_DATABASE_URI=database_uri(),
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        SQLALCHEMY_ENGINE_OPTIONS={"pool_pre_ping": True},
        MAX_CONTENT_LENGTH=25 * 1024 * 1024,
    )

    app.wsgi_app = ProxyFix(
        app.wsgi_app,
        x_for=1,
        x_proto=1,
        x_host=1,
    )

    db.init_app(app)
    register_helpers(app)
    register_routes(app)

    with app.app_context():
        db.create_all()

    return app


def normalize_text(value: str | None, length: int) -> str:
    return " ".join((value or "").split())[:length]


def slugify(value: str | None) -> str:
    return re.sub(
        r"[^a-z0-9]+",
        "-",
        (value or "").lower(),
    ).strip("-")[:80]


def safe_https(value: str | None) -> str:
    candidate = (value or "").strip()
    return candidate if candidate.lower().startswith("https://") else ""


def csrf_token() -> str:
    token = session.get("_csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        session["_csrf_token"] = token
    return str(token)


def validate_csrf() -> None:
    expected = str(session.get("_csrf_token", ""))
    supplied = request.form.get("_csrf_token", "")
    if not expected or not hmac.compare_digest(expected, supplied):
        abort(
            400,
            description="The form expired. Refresh the page and try again.",
        )


def client_ip_hash(app: Flask) -> str:
    raw_ip = request.remote_addr or "unknown"
    return hmac.new(
        str(app.config["SECRET_KEY"]).encode(),
        raw_ip.encode(),
        hashlib.sha256,
    ).hexdigest()


def memorial_by_slug(slug: str) -> Memorial:
    memorial = db.session.scalar(
        select(Memorial).where(Memorial.slug == slug)
    )
    if not memorial:
        abort(404)
    return memorial


def family_memorial_ids() -> set[int]:
    return {
        int(item)
        for item in session.get("family_memorial_ids", [])
    }


def platform_required(
    view: Callable[..., Any]
) -> Callable[..., Any]:

    @wraps(view)
    def wrapped(*args: Any, **kwargs: Any) -> Any:
        if not session.get("platform_admin"):
            return redirect(
                url_for(
                    "platform_login",
                    next=request.path,
                )
            )
        return view(*args, **kwargs)

    return wrapped


def family_required(
    view: Callable[..., Any]
) -> Callable[..., Any]:

    @wraps(view)
    def wrapped(
        slug: str,
        *args: Any,
        **kwargs: Any,
    ) -> Any:

        memorial = memorial_by_slug(slug)

        if (
            memorial.id not in family_memorial_ids()
            and not session.get("platform_admin")
        ):
            return redirect(
                url_for(
                    "family_login",
                    slug=slug,
                    next=request.path,
                )
            )

        return view(
            slug,
            memorial,
            *args,
            **kwargs,
        )

    return wrapped


def valid_image_upload(
    file,
) -> tuple[bytes, str, str] | None:

    if not file or not file.filename:
        return None

    allowed = {
        "image/jpeg",
        "image/png",
        "image/webp",
    }

    content_type = (
        file.mimetype or ""
    ).lower()

    if content_type not in allowed:
        return None

    data = file.read()

    if (
        not data
        or len(data) > 5 * 1024 * 1024
    ):
        return None

    filename = (
        normalize_text(file.filename, 255)
        or "photo"
    )

    return (
        data,
        content_type,
        filename,
    )


def valid_pdf_upload(
    file,
) -> tuple[bytes, str, str] | None:

    if not file or not file.filename:
        return None

    filename = (
        normalize_text(file.filename, 255)
        or "document.pdf"
    )

    data = file.read()

    if (
        not data
        or len(data) > 20 * 1024 * 1024
        or not data.startswith(b"%PDF")
    ):
        return None

    if not filename.lower().endswith(".pdf"):
        filename += ".pdf"

    return (
        data,
        "application/pdf",
        filename,
    )


def get_document(
    memorial_id: int,
    kind: str,
) -> MediaAsset | None:

    return db.session.scalar(
        select(MediaAsset)
        .where(
            MediaAsset.memorial_id
            == memorial_id,
            MediaAsset.kind == kind,
        )
        .order_by(
            MediaAsset.created_at.desc()
        )
        .limit(1)
    )


def whatsapp_share_url(
    memorial: Memorial,
) -> str:

    public_url = url_for(
        "public_memorial",
        slug=memorial.slug,
        _external=True,
    )

    text = (
        f"In loving memory of "
        f"{memorial.memorial_name}. "
        f"{public_url}"
    )

    return (
        "https://wa.me/?text="
        + quote(text)
    )


def tribute_rate_limited(
    memorial_id: int,
    ip_hash: str,
) -> bool:

    cutoff = (
        datetime.now(timezone.utc)
        - timedelta(
            seconds=max(
                10,
                int(
                    os.getenv(
                        "TRIBUTE_COOLDOWN_SECONDS",
                        "30",
                    )
                ),
            )
        )
    )

    recent = db.session.scalar(
        select(Tribute.id)
        .where(
            Tribute.memorial_id
            == memorial_id,
            Tribute.ip_hash
            == ip_hash,
            Tribute.created_at
            >= cutoff,
        )
        .limit(1)
    )

    return recent is not None


def unique_memorial_slug(
    preferred: str,
    name: str,
) -> str:

    base = (
        slugify(preferred)
        or slugify(name)
        or "memorial"
    )

    base = base[:70]
    candidate = base
    counter = 2

    while db.session.scalar(
        select(Memorial.id).where(
            Memorial.slug == candidate
        )
    ):
        suffix = f"-{counter}"
        candidate = (
            base[: 80 - len(suffix)]
            + suffix
        )
        counter += 1

    return candidate


def register_helpers(app: Flask) -> None:

    @app.context_processor
    def inject_common():
        return {
            "csrf_token": csrf_token,
            "current_year": (
                datetime.now(
                    timezone.utc
                ).year
            ),
        }


def register_routes(app: Flask) -> None:

    # =========================================
    # PUBLIC HOME
    # =========================================

    @app.get("/")
    def home():
        return render_template(
            "home.html"
        )

    # =========================================
    # PUBLIC MEMORIAL REQUEST
    # =========================================

    @app.route(
        "/request",
        methods=["GET", "POST"],
    )
    def memorial_request():

        if request.method == "POST":
            validate_csrf()

            # Honeypot spam trap
            if request.form.get("website"):
                return redirect(
                    url_for("home")
                )

            requester_name = normalize_text(
                request.form.get(
                    "requester_name"
                ),
                160,
            )

            phone = normalize_text(
                request.form.get("phone"),
                60,
            )

            memorial_name = normalize_text(
                request.form.get(
                    "memorial_name"
                ),
                160,
            )

            consent = (
                request.form.get("consent")
                == "yes"
            )

            if not requester_name:
                flash(
                    "Please enter your name.",
                    "warning",
                )
                return redirect(
                    url_for(
                        "memorial_request"
                    )
                )

            if not phone:
                flash(
                    "Please provide a phone or WhatsApp number.",
                    "warning",
                )
                return redirect(
                    url_for(
                        "memorial_request"
                    )
                )

            if not memorial_name:
                flash(
                    "Please enter the name of your loved one.",
                    "warning",
                )
                return redirect(
                    url_for(
                        "memorial_request"
                    )
                )

            if not consent:
                flash(
                    "Please confirm that you have permission to provide this information.",
                    "warning",
                )
                return redirect(
                    url_for(
                        "memorial_request"
                    )
                )

            preferred_contact = (
                request.form.get(
                    "preferred_contact",
                    "whatsapp",
                )
            )

            if preferred_contact not in {
                "whatsapp",
                "phone",
                "email",
            }:
                preferred_contact = (
                    "whatsapp"
                )

            preferred_theme = (
                request.form.get(
                    "preferred_theme",
                    "classic",
                )
            )

            if preferred_theme not in {
                "classic",
                "warm",
                "serene",
                "choose",
            }:
                preferred_theme = (
                    "classic"
                )

            publishing_preference = (
                request.form.get(
                    "publishing_preference",
                    "review_first",
                )
            )

            if publishing_preference not in {
                "review_first",
                "publish_ready",
                "specific_date",
            }:
                publishing_preference = (
                    "review_first"
                )

            timezone_offset = (
                request.form.get(
                    "timezone_offset",
                    "+03:00",
                )
            )

            allowed_offsets = {
                "-05:00",
                "-04:00",
                "-03:00",
                "-02:00",
                "-01:00",
                "+00:00",
                "+01:00",
                "+02:00",
                "+03:00",
                "+04:00",
                "+05:00",
            }

            if (
                timezone_offset
                not in allowed_offsets
            ):
                timezone_offset = "+03:00"

            lead = MemorialRequest(
                requester_name=requester_name,
                relationship=normalize_text(
                    request.form.get(
                        "relationship"
                    ),
                    120,
                ),
                phone=phone,
                email=normalize_text(
                    request.form.get("email"),
                    180,
                ),
                preferred_contact=(
                    preferred_contact
                ),
                memorial_name=(
                    memorial_name
                ),
                display_name=normalize_text(
                    request.form.get(
                        "display_name"
                    ),
                    160,
                ),
                birth_date=normalize_text(
                    request.form.get(
                        "birth_date"
                    ),
                    60,
                ),
                death_date=normalize_text(
                    request.form.get(
                        "death_date"
                    ),
                    60,
                ),
                place_of_birth=normalize_text(
                    request.form.get(
                        "place_of_birth"
                    ),
                    160,
                ),
                memorial_message=normalize_text(
                    request.form.get(
                        "memorial_message"
                    ),
                    320,
                ),
                biography=(
                    request.form.get(
                        "biography"
                    )
                    or ""
                ).strip()[:8000],
                has_portrait=(
                    request.form.get(
                        "has_portrait"
                    )
                    == "yes"
                ),
                has_gallery=(
                    request.form.get(
                        "has_gallery"
                    )
                    == "yes"
                ),
                has_eulogy=(
                    request.form.get(
                        "has_eulogy"
                    )
                    == "yes"
                ),
                has_programme=(
                    request.form.get(
                        "has_programme"
                    )
                    == "yes"
                ),
                funeral_date=normalize_text(
                    request.form.get(
                        "funeral_date"
                    ),
                    160,
                ),
                service_datetime=normalize_text(
                    request.form.get(
                        "service_datetime"
                    ),
                    40,
                ),
                timezone_offset=(
                    timezone_offset
                ),
                burial_venue=normalize_text(
                    request.form.get(
                        "burial_venue"
                    ),
                    260,
                ),
                burial_map_url=safe_https(
                    request.form.get(
                        "burial_map_url"
                    )
                ),
                livestream_url=safe_https(
                    request.form.get(
                        "livestream_url"
                    )
                ),
                mpesa_number=normalize_text(
                    request.form.get(
                        "mpesa_number"
                    ),
                    50,
                ),
                mpesa_name=normalize_text(
                    request.form.get(
                        "mpesa_name"
                    ),
                    140,
                ),
                contribution_purpose=normalize_text(
                    request.form.get(
                        "contribution_purpose"
                    ),
                    220,
                ),
                whatsapp_url=safe_https(
                    request.form.get(
                        "whatsapp_url"
                    )
                ),
                family_acknowledgement=(
                    request.form.get(
                        "family_acknowledgement"
                    )
                    or ""
                ).strip()[:5000],
                preferred_theme=(
                    preferred_theme
                ),
                preferred_slug=slugify(
                    request.form.get(
                        "preferred_slug"
                    )
                ),
                publishing_preference=(
                    publishing_preference
                ),
                additional_requests=(
                    request.form.get(
                        "additional_requests"
                    )
                    or ""
                ).strip()[:5000],
                consent=True,
                status="new",
            )

            db.session.add(lead)
            db.session.commit()

            return redirect(
                url_for(
                    "memorial_request_received",
                    reference_code=(
                        lead.reference_code
                    ),
                )
            )

        return render_template(
            "memorial_request.html"
        )

    @app.get(
        "/request/received/<reference_code>"
    )
    def memorial_request_received(
        reference_code: str,
    ):

        lead = db.session.scalar(
            select(MemorialRequest).where(
                MemorialRequest.reference_code
                == reference_code
            )
        )

        if not lead:
            abort(404)

        whatsapp_message = (
            "Hello Elimara Technologies. "
            f"I have submitted memorial request "
            f"{lead.reference_code} "
            f"for {lead.memorial_name} "
            "and would like to discuss the next steps."
        )

        whatsapp_followup_url = (
            "https://wa.me/254763941520"
            "?text="
            + quote(whatsapp_message)
        )

        return render_template(
            "memorial_request_received.html",
            lead=lead,
            whatsapp_followup_url=(
                whatsapp_followup_url
            ),
        )

    # =========================================
    # PLATFORM ADMIN
    # =========================================

    @app.route(
        "/platform/login",
        methods=["GET", "POST"],
    )
    def platform_login():

        configured = os.getenv(
            "PLATFORM_ADMIN_PASSWORD",
            "",
        ).strip()

        if not configured:
            abort(
                503,
                description=(
                    "Set PLATFORM_ADMIN_PASSWORD "
                    "in your environment variables."
                ),
            )

        if request.method == "POST":
            validate_csrf()

            supplied = request.form.get(
                "password",
                "",
            )

            if hmac.compare_digest(
                configured,
                supplied,
            ):
                session[
                    "platform_admin"
                ] = True

                flash(
                    "Platform dashboard unlocked.",
                    "success",
                )

                return redirect(
                    url_for(
                        "platform_dashboard"
                    )
                )

            flash(
                "Incorrect platform password.",
                "error",
            )

        return render_template(
            "platform_login.html"
        )

    @app.get("/platform")
    @platform_required
    def platform_dashboard():

        memorials = db.session.scalars(
            select(Memorial)
            .order_by(
                Memorial.created_at.desc()
            )
        ).all()

        memorial_requests = (
            db.session.scalars(
                select(MemorialRequest)
                .order_by(
                    MemorialRequest.created_at.desc()
                )
            ).all()
        )

        tribute_counts = {
            item.id: (
                db.session.scalar(
                    select(
                        func.count(
                            Tribute.id
                        )
                    ).where(
                        Tribute.memorial_id
                        == item.id
                    )
                )
                or 0
            )
            for item in memorials
        }

        return render_template(
            "platform_dashboard.html",
            memorials=memorials,
            memorial_requests=(
                memorial_requests
            ),
            tribute_counts=tribute_counts,
        )

    @app.post(
        "/platform/requests/"
        "<int:request_id>/status"
    )
    @platform_required
    def platform_request_status(
        request_id: int,
    ):

        validate_csrf()

        lead = db.get_or_404(
            MemorialRequest,
            request_id,
        )

        status = request.form.get(
            "status",
            "new",
        )

        if status not in {
            "new",
            "contacted",
            "converted",
            "closed",
        }:
            flash(
                "Invalid request status.",
                "warning",
            )
            return redirect(
                url_for(
                    "platform_dashboard"
                )
            )

        lead.status = status
        db.session.commit()

        flash(
            f"{lead.reference_code} "
            f"marked as {status}.",
            "success",
        )

        return redirect(
            url_for(
                "platform_dashboard"
            )
        )

    @app.post(
        "/platform/requests/"
        "<int:request_id>/convert"
    )
    @platform_required
    def platform_convert_request(
        request_id: int,
    ):

        validate_csrf()

        lead = db.get_or_404(
            MemorialRequest,
            request_id,
        )

        family_password = (
            request.form.get(
                "family_password",
                "",
            )
        )

        if len(family_password) < 6:
            flash(
                "The family password must contain at least 6 characters.",
                "warning",
            )
            return redirect(
                url_for(
                    "platform_dashboard"
                )
            )

        name = (
            lead.display_name
            or lead.memorial_name
        )

        slug = unique_memorial_slug(
            lead.preferred_slug,
            name,
        )

        theme = lead.preferred_theme
        if theme not in {
            "classic",
            "warm",
            "serene",
        }:
            theme = "classic"

        memorial = Memorial(
            memorial_name=name,
            slug=slug,
            birth_date=lead.birth_date,
            death_date=lead.death_date,
            hero_message=(
                lead.memorial_message
                or (
                    "Forever loved, "
                    "forever remembered, "
                    "forever in our hearts."
                )
            ),
            biography=lead.biography,
            burial_date=lead.funeral_date,
            burial_venue=(
                lead.burial_venue
            ),
            burial_map_url=(
                lead.burial_map_url
            ),
            livestream_url=(
                lead.livestream_url
            ),
            mpesa_number=(
                lead.mpesa_number
            ),
            mpesa_name=lead.mpesa_name,
            contribution_purpose=(
                lead.contribution_purpose
            ),
            whatsapp_url=(
                lead.whatsapp_url
            ),
            family_acknowledgement=(
                lead.family_acknowledgement
                or (
                    "With heartfelt gratitude, "
                    "our family thanks everyone "
                    "who stood with us, shared "
                    "memories, prayed with us "
                    "and honoured this life "
                    "with love."
                )
            ),
            theme=theme,
            is_published=False,
            family_password_hash=(
                generate_password_hash(
                    family_password
                )
            ),
        )

        db.session.add(memorial)
        db.session.flush()

        if lead.service_datetime:
            db.session.add(
                MemorialEvent(
                    memorial_id=memorial.id,
                    service_datetime=(
                        lead.service_datetime
                    ),
                    timezone_offset=(
                        lead.timezone_offset
                    ),
                )
            )

        lead.status = "converted"

        db.session.commit()

        ids = family_memorial_ids()
        ids.add(memorial.id)

        session[
            "family_memorial_ids"
        ] = list(ids)

        flash(
            "Request converted into a draft memorial. "
            "Review the details and upload the family's files before publishing.",
            "success",
        )

        return redirect(
            url_for(
                "family_dashboard",
                slug=slug,
            )
        )

    @app.post(
        "/platform/requests/"
        "<int:request_id>/delete"
    )
    @platform_required
    def platform_delete_request(
        request_id: int,
    ):

        validate_csrf()

        lead = db.get_or_404(
            MemorialRequest,
            request_id,
        )

        reference = (
            lead.reference_code
        )

        db.session.delete(lead)
        db.session.commit()

        flash(
            f"Request {reference} deleted.",
            "success",
        )

        return redirect(
            url_for(
                "platform_dashboard"
            )
        )

    @app.post(
        "/platform/memorials/create"
    )
    @platform_required
    def create_memorial():

        validate_csrf()

        name = normalize_text(
            request.form.get(
                "memorial_name"
            ),
            160,
        )

        slug = slugify(
            request.form.get("slug")
            or name
        )

        family_password = (
            request.form.get(
                "family_password",
                "",
            )
        )

        if not name:
            flash(
                "Enter the person's full name.",
                "warning",
            )
            return redirect(
                url_for(
                    "platform_dashboard"
                )
            )

        if len(slug) < 3:
            flash(
                "Use a memorial link of at least 3 characters.",
                "warning",
            )
            return redirect(
                url_for(
                    "platform_dashboard"
                )
            )

        if db.session.scalar(
            select(Memorial.id).where(
                Memorial.slug == slug
            )
        ):
            flash(
                "That memorial link is already in use.",
                "warning",
            )
            return redirect(
                url_for(
                    "platform_dashboard"
                )
            )

        if len(family_password) < 6:
            flash(
                "The family password must contain at least 6 characters.",
                "warning",
            )
            return redirect(
                url_for(
                    "platform_dashboard"
                )
            )

        memorial = Memorial(
            memorial_name=name,
            slug=slug,
            family_password_hash=(
                generate_password_hash(
                    family_password
                )
            ),
            family_acknowledgement=(
                "With heartfelt gratitude, "
                "our family thanks everyone "
                "who stood with us, shared "
                "memories, prayed with us "
                "and honoured this life "
                "with love."
            ),
            theme="classic",
            is_published=False,
        )

        db.session.add(memorial)
        db.session.commit()

        ids = family_memorial_ids()
        ids.add(memorial.id)

        session[
            "family_memorial_ids"
        ] = list(ids)

        flash(
            "Memorial created. Complete the family settings before publishing.",
            "success",
        )

        return redirect(
            url_for(
                "family_dashboard",
                slug=slug,
            )
        )

    @app.post(
        "/platform/memorials/"
        "<int:memorial_id>/toggle-publish"
    )
    @platform_required
    def platform_toggle_publish(
        memorial_id: int,
    ):

        validate_csrf()

        memorial = db.get_or_404(
            Memorial,
            memorial_id,
        )

        memorial.is_published = (
            not memorial.is_published
        )

        db.session.commit()

        flash(
            "Publishing status updated.",
            "success",
        )

        return redirect(
            url_for(
                "platform_dashboard"
            )
        )

    @app.post(
        "/platform/memorials/"
        "<int:memorial_id>/reset-password"
    )
    @platform_required
    def platform_reset_family_password(
        memorial_id: int,
    ):

        validate_csrf()

        memorial = db.get_or_404(
            Memorial,
            memorial_id,
        )

        password = request.form.get(
            "new_password",
            "",
        )

        if len(password) < 6:
            flash(
                "New family password must contain at least 6 characters.",
                "warning",
            )
            return redirect(
                url_for(
                    "platform_dashboard"
                )
            )

        memorial.family_password_hash = (
            generate_password_hash(
                password
            )
        )

        db.session.commit()

        flash(
            "Family password reset for "
            f"{memorial.memorial_name}.",
            "success",
        )

        return redirect(
            url_for(
                "platform_dashboard"
            )
        )

    @app.post(
        "/platform/memorials/"
        "<int:memorial_id>/delete"
    )
    @platform_required
    def platform_delete_memorial(
        memorial_id: int,
    ):

        validate_csrf()

        memorial = db.get_or_404(
            Memorial,
            memorial_id,
        )

        db.session.execute(
            MediaAsset.__table__
            .delete()
            .where(
                MediaAsset.memorial_id
                == memorial.id
            )
        )

        db.session.execute(
            Tribute.__table__
            .delete()
            .where(
                Tribute.memorial_id
                == memorial.id
            )
        )

        db.session.delete(memorial)
        db.session.commit()

        flash(
            "Memorial deleted.",
            "success",
        )

        return redirect(
            url_for(
                "platform_dashboard"
            )
        )

    @app.post("/platform/logout")
    @platform_required
    def platform_logout():

        validate_csrf()

        session.pop(
            "platform_admin",
            None,
        )

        return redirect(
            url_for(
                "platform_login"
            )
        )

    # =========================================
    # PUBLIC MEMORIAL
    # =========================================

    @app.get("/m/<slug>")
    def public_memorial(
        slug: str,
    ):

        memorial = memorial_by_slug(
            slug
        )

        can_preview = (
            memorial.id
            in family_memorial_ids()
            or session.get(
                "platform_admin"
            )
        )

        if (
            not memorial.is_published
            and not can_preview
        ):
            abort(404)

        tributes = db.session.scalars(
            select(Tribute)
            .where(
                Tribute.memorial_id
                == memorial.id,
                Tribute.is_visible.is_(
                    True
                ),
            )
            .order_by(
                Tribute.created_at.desc()
            )
            .limit(300)
        ).all()

        gallery = db.session.scalars(
            select(MediaAsset)
            .where(
                MediaAsset.memorial_id
                == memorial.id,
                MediaAsset.kind
                == "gallery",
            )
            .order_by(
                MediaAsset.created_at.desc()
            )
        ).all()

        portrait = db.session.scalar(
            select(MediaAsset)
            .where(
                MediaAsset.memorial_id
                == memorial.id,
                MediaAsset.kind
                == "portrait",
            )
            .order_by(
                MediaAsset.created_at.desc()
            )
            .limit(1)
        )

        event = db.session.scalar(
            select(MemorialEvent).where(
                MemorialEvent.memorial_id
                == memorial.id
            )
        )

        eulogy = get_document(
            memorial.id,
            "eulogy",
        )

        programme = get_document(
            memorial.id,
            "programme",
        )

        return render_template(
            "memorial.html",
            memorial=memorial,
            tributes=tributes,
            gallery=gallery,
            portrait=portrait,
            event=event,
            eulogy=eulogy,
            programme=programme,
            whatsapp_share_url=(
                whatsapp_share_url(
                    memorial
                )
            ),
        )

    @app.get(
        "/m/<slug>/documents/<kind>"
    )
    def public_document(
        slug: str,
        kind: str,
    ):

        memorial = memorial_by_slug(
            slug
        )

        can_preview = (
            memorial.id
            in family_memorial_ids()
            or session.get(
                "platform_admin"
            )
        )

        if (
            not memorial.is_published
            and not can_preview
        ):
            abort(404)

        if kind not in {
            "eulogy",
            "programme",
        }:
            abort(404)

        asset = get_document(
            memorial.id,
            kind,
        )

        if not asset:
            abort(404)

        return send_file(
            BytesIO(asset.data),
            mimetype="application/pdf",
            as_attachment=(
                request.args.get(
                    "download"
                )
                == "1"
            ),
            download_name=(
                asset.filename
            ),
        )

    @app.post(
        "/m/<slug>/tributes"
    )
    def add_tribute(
        slug: str,
    ):

        memorial = memorial_by_slug(
            slug
        )

        if not memorial.is_published:
            abort(404)

        validate_csrf()

        if request.form.get(
            "website"
        ):
            return redirect(
                url_for(
                    "public_memorial",
                    slug=slug,
                )
            )

        name = (
            normalize_text(
                request.form.get(
                    "participant_name"
                ),
                90,
            )
            or "Anonymous"
        )

        message = normalize_text(
            request.form.get(
                "message"
            ),
            900,
        )

        if not message:
            flash(
                "Please write a tribute before submitting.",
                "warning",
            )

            return redirect(
                url_for(
                    "public_memorial",
                    slug=slug,
                )
                + "#tributes"
            )

        ip_hash = client_ip_hash(
            app
        )

        if tribute_rate_limited(
            memorial.id,
            ip_hash,
        ):
            flash(
                "Your previous tribute was received. "
                "Please wait before submitting another.",
                "warning",
            )

            return redirect(
                url_for(
                    "public_memorial",
                    slug=slug,
                )
                + "#tributes"
            )

        tribute = Tribute(
            memorial_id=memorial.id,
            participant_name=name,
            message=message,
            ip_hash=ip_hash,
        )

        db.session.add(tribute)
        db.session.commit()

        flash(
            "Your tribute has been added with love.",
            "success",
        )

        return redirect(
            url_for(
                "public_memorial",
                slug=slug,
            )
            + f"#tribute-{tribute.id}"
        )

    @app.get(
        "/media/<int:asset_id>"
    )
    def media_asset(
        asset_id: int,
    ):

        asset = db.get_or_404(
            MediaAsset,
            asset_id,
        )

        memorial = db.get_or_404(
            Memorial,
            asset.memorial_id,
        )

        can_preview = (
            memorial.id
            in family_memorial_ids()
            or session.get(
                "platform_admin"
            )
        )

        if (
            not memorial.is_published
            and not can_preview
        ):
            abort(404)

        return Response(
            asset.data,
            mimetype=asset.content_type,
            headers={
                "Cache-Control":
                "public, max-age=86400"
            },
        )

    # =========================================
    # FAMILY ACCESS
    # =========================================

    @app.route(
        "/m/<slug>/family/login",
        methods=["GET", "POST"],
    )
    def family_login(
        slug: str,
    ):

        memorial = memorial_by_slug(
            slug
        )

        if request.method == "POST":
            validate_csrf()

            if check_password_hash(
                memorial.family_password_hash,
                request.form.get(
                    "password",
                    "",
                ),
            ):
                ids = (
                    family_memorial_ids()
                )
                ids.add(memorial.id)

                session[
                    "family_memorial_ids"
                ] = list(ids)

                flash(
                    "Family dashboard unlocked.",
                    "success",
                )

                return redirect(
                    url_for(
                        "family_dashboard",
                        slug=slug,
                    )
                )

            flash(
                "Incorrect family password.",
                "error",
            )

        return render_template(
            "family_login.html",
            memorial=memorial,
        )

    @app.get(
        "/m/<slug>/family"
    )
    @family_required
    def family_dashboard(
        slug: str,
        memorial: Memorial,
    ):

        tributes = db.session.scalars(
            select(Tribute)
            .where(
                Tribute.memorial_id
                == memorial.id
            )
            .order_by(
                Tribute.created_at.desc()
            )
        ).all()

        gallery = db.session.scalars(
            select(MediaAsset)
            .where(
                MediaAsset.memorial_id
                == memorial.id,
                MediaAsset.kind
                == "gallery",
            )
            .order_by(
                MediaAsset.created_at.desc()
            )
        ).all()

        portrait = db.session.scalar(
            select(MediaAsset)
            .where(
                MediaAsset.memorial_id
                == memorial.id,
                MediaAsset.kind
                == "portrait",
            )
            .order_by(
                MediaAsset.created_at.desc()
            )
            .limit(1)
        )

        event = db.session.scalar(
            select(MemorialEvent).where(
                MemorialEvent.memorial_id
                == memorial.id
            )
        )

        return render_template(
            "family_dashboard.html",
            memorial=memorial,
            tributes=tributes,
            gallery=gallery,
            portrait=portrait,
            event=event,
            eulogy=get_document(
                memorial.id,
                "eulogy",
            ),
            programme=get_document(
                memorial.id,
                "programme",
            ),
        )

    @app.post(
        "/m/<slug>/family/settings/autosave"
    )
    @family_required
    def autosave_family_settings(
        slug: str,
        memorial: Memorial,
    ):
        """Autosave ordinary memorial content without changing access or publish state."""

        validate_csrf()

        memorial.memorial_name = (
            normalize_text(
                request.form.get("memorial_name"),
                160,
            )
            or memorial.memorial_name
        )
        memorial.birth_date = normalize_text(
            request.form.get("birth_date"),
            60,
        )
        memorial.death_date = normalize_text(
            request.form.get("death_date"),
            60,
        )
        memorial.hero_message = normalize_text(
            request.form.get("hero_message"),
            320,
        )
        memorial.biography = (
            request.form.get("biography") or ""
        ).strip()[:10000]

        memorial.burial_date = normalize_text(
            request.form.get("burial_date"),
            160,
        )
        memorial.burial_venue = normalize_text(
            request.form.get("burial_venue"),
            260,
        )
        memorial.burial_map_url = safe_https(
            request.form.get("burial_map_url")
        )
        memorial.livestream_url = safe_https(
            request.form.get("livestream_url")
        )

        memorial.mpesa_number = normalize_text(
            request.form.get("mpesa_number"),
            50,
        )
        memorial.mpesa_name = normalize_text(
            request.form.get("mpesa_name"),
            140,
        )
        memorial.contribution_purpose = normalize_text(
            request.form.get("contribution_purpose"),
            220,
        )
        memorial.whatsapp_url = safe_https(
            request.form.get("whatsapp_url")
        )
        memorial.family_acknowledgement = (
            request.form.get("family_acknowledgement") or ""
        ).strip()[:2500]

        theme = request.form.get("theme", memorial.theme)
        if theme in {"classic", "warm", "serene"}:
            memorial.theme = theme

        service_datetime = normalize_text(
            request.form.get("service_datetime"),
            40,
        )
        timezone_offset = request.form.get(
            "service_timezone",
            "+03:00",
        )
        allowed_offsets = {
            "-05:00",
            "-04:00",
            "-03:00",
            "-02:00",
            "-01:00",
            "+00:00",
            "+01:00",
            "+02:00",
            "+03:00",
            "+04:00",
            "+05:00",
        }
        if timezone_offset not in allowed_offsets:
            timezone_offset = "+03:00"

        event = db.session.scalar(
            select(MemorialEvent).where(
                MemorialEvent.memorial_id == memorial.id
            )
        )

        if service_datetime:
            if event is None:
                db.session.add(
                    MemorialEvent(
                        memorial_id=memorial.id,
                        service_datetime=service_datetime,
                        timezone_offset=timezone_offset,
                    )
                )
            else:
                event.service_datetime = service_datetime
                event.timezone_offset = timezone_offset
        elif event is not None:
            db.session.delete(event)

        db.session.commit()

        return {
            "ok": True,
            "saved_at": datetime.now(timezone.utc).isoformat(),
        }


    @app.post(
        "/m/<slug>/family/settings"
    )
    @family_required
    def save_family_settings(
        slug: str,
        memorial: Memorial,
    ):

        validate_csrf()

        memorial.memorial_name = (
            normalize_text(
                request.form.get(
                    "memorial_name"
                ),
                160,
            )
            or memorial.memorial_name
        )

        memorial.birth_date = (
            normalize_text(
                request.form.get(
                    "birth_date"
                ),
                60,
            )
        )

        memorial.death_date = (
            normalize_text(
                request.form.get(
                    "death_date"
                ),
                60,
            )
        )

        memorial.hero_message = (
            normalize_text(
                request.form.get(
                    "hero_message"
                ),
                320,
            )
        )

        memorial.biography = (
            request.form.get(
                "biography"
            )
            or ""
        ).strip()[:10000]

        memorial.burial_date = (
            normalize_text(
                request.form.get(
                    "burial_date"
                ),
                160,
            )
        )

        memorial.burial_venue = (
            normalize_text(
                request.form.get(
                    "burial_venue"
                ),
                260,
            )
        )

        memorial.burial_map_url = (
            safe_https(
                request.form.get(
                    "burial_map_url"
                )
            )
        )

        memorial.livestream_url = (
            safe_https(
                request.form.get(
                    "livestream_url"
                )
            )
        )

        memorial.mpesa_number = (
            normalize_text(
                request.form.get(
                    "mpesa_number"
                ),
                50,
            )
        )

        memorial.mpesa_name = (
            normalize_text(
                request.form.get(
                    "mpesa_name"
                ),
                140,
            )
        )

        memorial.contribution_purpose = (
            normalize_text(
                request.form.get(
                    "contribution_purpose"
                ),
                220,
            )
        )

        memorial.whatsapp_url = (
            safe_https(
                request.form.get(
                    "whatsapp_url"
                )
            )
        )

        memorial.family_acknowledgement = (
            request.form.get(
                "family_acknowledgement"
            )
            or ""
        ).strip()[:2500]

        theme = request.form.get(
            "theme",
            "classic",
        )

        memorial.theme = (
            theme
            if theme in {
                "classic",
                "warm",
                "serene",
            }
            else "classic"
        )

        memorial.is_published = (
            request.form.get(
                "is_published"
            )
            == "on"
        )

        service_datetime = (
            normalize_text(
                request.form.get(
                    "service_datetime"
                ),
                40,
            )
        )

        timezone_offset = (
            request.form.get(
                "service_timezone",
                "+03:00",
            )
        )

        allowed_offsets = {
            "-05:00",
            "-04:00",
            "-03:00",
            "-02:00",
            "-01:00",
            "+00:00",
            "+01:00",
            "+02:00",
            "+03:00",
            "+04:00",
            "+05:00",
        }

        if (
            timezone_offset
            not in allowed_offsets
        ):
            timezone_offset = (
                "+03:00"
            )

        event = db.session.scalar(
            select(MemorialEvent).where(
                MemorialEvent.memorial_id
                == memorial.id
            )
        )

        if service_datetime:

            if event is None:
                db.session.add(
                    MemorialEvent(
                        memorial_id=(
                            memorial.id
                        ),
                        service_datetime=(
                            service_datetime
                        ),
                        timezone_offset=(
                            timezone_offset
                        ),
                    )
                )

            else:
                event.service_datetime = (
                    service_datetime
                )
                event.timezone_offset = (
                    timezone_offset
                )

        elif event is not None:
            db.session.delete(event)

        new_password = (
            request.form.get(
                "new_family_password",
                "",
            )
        )

        if new_password:

            if len(new_password) < 6:
                flash(
                    "New family password must contain at least 6 characters.",
                    "warning",
                )

                return redirect(
                    url_for(
                        "family_dashboard",
                        slug=slug,
                    )
                )

            memorial.family_password_hash = (
                generate_password_hash(
                    new_password
                )
            )

        db.session.commit()

        flash(
            "Memorial settings saved.",
            "success",
        )

        return redirect(
            url_for(
                "family_dashboard",
                slug=slug,
            )
        )

    @app.post(
        "/m/<slug>/family/"
        "documents/<kind>/upload"
    )
    @family_required
    def upload_document(
        slug: str,
        memorial: Memorial,
        kind: str,
    ):

        validate_csrf()

        if kind not in {
            "eulogy",
            "programme",
        }:
            abort(404)

        upload = valid_pdf_upload(
            request.files.get(
                "document"
            )
        )

        if not upload:
            flash(
                "Upload a valid PDF smaller than 20 MB.",
                "warning",
            )
            return redirect(
                url_for(
                    "family_dashboard",
                    slug=slug,
                )
            )

        (
            data,
            content_type,
            filename,
        ) = upload

        db.session.execute(
            MediaAsset.__table__
            .delete()
            .where(
                MediaAsset.memorial_id
                == memorial.id,
                MediaAsset.kind == kind,
            )
        )

        db.session.add(
            MediaAsset(
                memorial_id=memorial.id,
                kind=kind,
                filename=filename,
                content_type=(
                    content_type
                ),
                data=data,
            )
        )

        db.session.commit()

        flash(
            (
                "Eulogy"
                if kind == "eulogy"
                else "Funeral programme"
            )
            + " uploaded successfully.",
            "success",
        )

        return redirect(
            url_for(
                "family_dashboard",
                slug=slug,
            )
        )

    @app.post(
        "/m/<slug>/family/"
        "documents/<kind>/delete"
    )
    @family_required
    def delete_document(
        slug: str,
        memorial: Memorial,
        kind: str,
    ):

        validate_csrf()

        if kind not in {
            "eulogy",
            "programme",
        }:
            abort(404)

        asset = get_document(
            memorial.id,
            kind,
        )

        if asset:
            db.session.delete(asset)
            db.session.commit()

            flash(
                "Document removed.",
                "success",
            )

        return redirect(
            url_for(
                "family_dashboard",
                slug=slug,
            )
        )

    @app.post(
        "/m/<slug>/family/"
        "upload-portrait"
    )
    @family_required
    def upload_portrait(
        slug: str,
        memorial: Memorial,
    ):

        validate_csrf()

        upload = valid_image_upload(
            request.files.get("photo")
        )

        if not upload:
            flash(
                "Upload a JPG, PNG or WebP image smaller than 5 MB.",
                "warning",
            )

            return redirect(
                url_for(
                    "family_dashboard",
                    slug=slug,
                )
            )

        (
            data,
            content_type,
            filename,
        ) = upload

        db.session.execute(
            MediaAsset.__table__
            .delete()
            .where(
                MediaAsset.memorial_id
                == memorial.id,
                MediaAsset.kind
                == "portrait",
            )
        )

        db.session.add(
            MediaAsset(
                memorial_id=memorial.id,
                kind="portrait",
                filename=filename,
                content_type=(
                    content_type
                ),
                data=data,
            )
        )

        db.session.commit()

        flash(
            "Main portrait updated.",
            "success",
        )

        return redirect(
            url_for(
                "family_dashboard",
                slug=slug,
            )
        )

    @app.post(
        "/m/<slug>/family/"
        "upload-gallery"
    )
    @family_required
    def upload_gallery(
        slug: str,
        memorial: Memorial,
    ):

        validate_csrf()

        files = request.files.getlist(
            "photos"
        )

        saved = 0

        for file in files[:12]:

            upload = valid_image_upload(
                file
            )

            if not upload:
                continue

            (
                data,
                content_type,
                filename,
            ) = upload

            db.session.add(
                MediaAsset(
                    memorial_id=(
                        memorial.id
                    ),
                    kind="gallery",
                    filename=filename,
                    content_type=(
                        content_type
                    ),
                    data=data,
                )
            )

            saved += 1

        db.session.commit()

        flash(
            (
                f"{saved} photo"
                f"{'s' if saved != 1 else ''} "
                "added to the gallery."
            )
            if saved
            else (
                "No valid photos were uploaded."
            ),
            (
                "success"
                if saved
                else "warning"
            ),
        )

        return redirect(
            url_for(
                "family_dashboard",
                slug=slug,
            )
        )

    @app.post(
        "/m/<slug>/family/"
        "media/<int:asset_id>/delete"
    )
    @family_required
    def delete_media(
        slug: str,
        memorial: Memorial,
        asset_id: int,
    ):

        validate_csrf()

        asset = db.session.scalar(
            select(MediaAsset).where(
                MediaAsset.id
                == asset_id,
                MediaAsset.memorial_id
                == memorial.id,
            )
        )

        if not asset:
            abort(404)

        db.session.delete(asset)
        db.session.commit()

        flash(
            "Photo removed.",
            "success",
        )

        return redirect(
            url_for(
                "family_dashboard",
                slug=slug,
            )
        )

    @app.post(
        "/m/<slug>/family/"
        "tributes/<int:tribute_id>/"
        "acknowledge"
    )
    @family_required
    def acknowledge_tribute(
        slug: str,
        memorial: Memorial,
        tribute_id: int,
    ):

        validate_csrf()

        tribute = db.session.scalar(
            select(Tribute).where(
                Tribute.id
                == tribute_id,
                Tribute.memorial_id
                == memorial.id,
            )
        )

        if not tribute:
            abort(404)

        tribute.is_acknowledged = (
            not tribute.is_acknowledged
        )

        db.session.commit()

        flash(
            "Family acknowledgement updated.",
            "success",
        )

        return redirect(
            url_for(
                "family_dashboard",
                slug=slug,
            )
            + f"#tribute-{tribute.id}"
        )

    @app.post(
        "/m/<slug>/family/"
        "tributes/<int:tribute_id>/toggle"
    )
    @family_required
    def toggle_tribute(
        slug: str,
        memorial: Memorial,
        tribute_id: int,
    ):

        validate_csrf()

        tribute = db.session.scalar(
            select(Tribute).where(
                Tribute.id
                == tribute_id,
                Tribute.memorial_id
                == memorial.id,
            )
        )

        if not tribute:
            abort(404)

        tribute.is_visible = (
            not tribute.is_visible
        )

        db.session.commit()

        flash(
            "Tribute visibility updated.",
            "success",
        )

        return redirect(
            url_for(
                "family_dashboard",
                slug=slug,
            )
            + f"#tribute-{tribute.id}"
        )

    @app.post(
        "/m/<slug>/family/"
        "tributes/<int:tribute_id>/delete"
    )
    @family_required
    def delete_tribute(
        slug: str,
        memorial: Memorial,
        tribute_id: int,
    ):

        validate_csrf()

        tribute = db.session.scalar(
            select(Tribute).where(
                Tribute.id
                == tribute_id,
                Tribute.memorial_id
                == memorial.id,
            )
        )

        if not tribute:
            abort(404)

        db.session.delete(tribute)
        db.session.commit()

        flash(
            "Tribute deleted.",
            "success",
        )

        return redirect(
            url_for(
                "family_dashboard",
                slug=slug,
            )
        )

    @app.post(
        "/m/<slug>/family/logout"
    )
    @family_required
    def family_logout(
        slug: str,
        memorial: Memorial,
    ):

        validate_csrf()

        ids = family_memorial_ids()
        ids.discard(memorial.id)

        session[
            "family_memorial_ids"
        ] = list(ids)

        return redirect(
            url_for(
                "public_memorial",
                slug=slug,
            )
        )

    # =========================================
    # HEALTH + ERROR HANDLERS
    # =========================================

    @app.get("/health")
    def health():
        return {
            "status": "ok"
        }

    @app.errorhandler(400)
    def bad_request(error):
        return render_template(
            "error.html",
            title=(
                "Request could not be completed"
            ),
            message=str(error),
        ), 400

    @app.errorhandler(403)
    def forbidden(error):
        return render_template(
            "error.html",
            title="Access denied",
            message=str(error),
        ), 403

    @app.errorhandler(404)
    def not_found(error):
        return render_template(
            "error.html",
            title="Page not found",
            message=(
                "The page or memorial "
                "you requested could "
                "not be found."
            ),
        ), 404

    @app.errorhandler(413)
    def too_large(error):
        return render_template(
            "error.html",
            title="Upload too large",
            message=(
                "Please upload smaller images. "
                "Each photo should be under 5 MB."
            ),
        ), 413

    @app.errorhandler(500)
    def server_error(error):
        db.session.rollback()

        app.logger.exception(
            "Unexpected application error: %s",
            error,
        )

        return render_template(
            "error.html",
            title="Temporary problem",
            message=(
                "Please refresh the page "
                "and try again."
            ),
        ), 500


app = create_app()


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(
            os.getenv(
                "PORT",
                "5000",
            )
        ),
        debug=(
            os.getenv(
                "FLASK_DEBUG"
            )
            == "1"
        ),
    )
