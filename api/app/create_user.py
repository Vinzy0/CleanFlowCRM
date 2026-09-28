import argparse
from getpass import getpass

from sqlalchemy import select

from .auth import password_hash
from .db import SessionLocal
from .models import User


def main():
    parser = argparse.ArgumentParser(description="Create a CleanFlow CRM business user")
    parser.add_argument("email")
    parser.add_argument("name")
    args = parser.parse_args()
    password = getpass("Password: ")
    if len(password) < 12:
        raise SystemExit("Password must be at least 12 characters")
    with SessionLocal() as db:
        if db.scalar(select(User).where(User.email == args.email.lower())):
            raise SystemExit("User already exists")
        db.add(User(email=args.email.lower(), name=args.name, password_hash=password_hash.hash(password)))
        db.commit()
    print("User created")


if __name__ == "__main__":
    main()
