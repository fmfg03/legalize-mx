from __future__ import annotations

import argparse
import json

from sqlalchemy import select

from backend.app.audit import dumps_audit_details, record_audit_log
from backend.app.db import SessionLocal, engine
from backend.app.models import ApiKey, AppUser, Base
from backend.app.models.enums import UserRole
from backend.app.security import generate_api_key


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Bootstrap expediente backend auth for legalize-mx.")
    parser.add_argument("--email", required=True, help="Unique user email.")
    parser.add_argument("--name", required=True, help="Display name.")
    parser.add_argument(
        "--role",
        default=UserRole.ADMIN.value,
        choices=[role.value for role in UserRole],
        help="User role to assign.",
    )
    parser.add_argument("--key-label", default="bootstrap-admin", help="Label for the created API key.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    try:
        email = args.email.strip().lower()
        user = session.scalar(select(AppUser).where(AppUser.email == email))
        if user is None:
            user = AppUser(
                email=email,
                display_name=args.name.strip(),
                role=UserRole(args.role),
                is_active=True,
            )
            session.add(user)
            session.flush()
            record_audit_log(
                db=session,
                actor_user_id=None,
                action="bootstrap_user",
                entity_type="app_user",
                entity_id=user.id,
                details=dumps_audit_details({"email": user.email, "role": user.role}),
            )

        plaintext_api_key, key_prefix, secret_hash = generate_api_key()
        api_key = ApiKey(
            user_id=user.id,
            label=args.key_label.strip(),
            key_prefix=key_prefix,
            secret_hash=secret_hash,
            is_active=True,
        )
        session.add(api_key)
        session.flush()
        record_audit_log(
            db=session,
            actor_user_id=None,
            action="bootstrap_api_key",
            entity_type="api_key",
            entity_id=api_key.id,
            details=dumps_audit_details({"user_id": str(user.id), "label": api_key.label, "key_prefix": key_prefix}),
        )
        session.commit()
        print(
            json.dumps(
                {
                    "user_id": str(user.id),
                    "email": user.email,
                    "role": user.role,
                    "api_key_id": str(api_key.id),
                    "api_key_label": api_key.label,
                    "plaintext_api_key": plaintext_api_key,
                },
                ensure_ascii=True,
            )
        )
    finally:
        session.close()


if __name__ == "__main__":
    main()
