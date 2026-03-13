"""
Database seeding for initial data
"""
from sqlmodel import Session, select
from .database import engine
from .models import Role

# Initial roles to seed
ROLES = [
    {"name": "worker", "description": "Can submit timesheets, view assigned jobs"},
    {"name": "manager", "description": "Can view all timesheets, create invoices, manage jobs"},
    {"name": "admin", "description": "Full system access"},
]


def seed_roles():
    """Seed initial roles if they don't exist"""
    with Session(engine) as session:
        for role_data in ROLES:
            # Check if role already exists
            statement = select(Role).where(Role.name == role_data["name"])
            existing = session.exec(statement).first()

            if not existing:
                role = Role(**role_data)
                session.add(role)
                print(f"Created role: {role_data['name']}")

        session.commit()


def get_role_by_name(session: Session, name: str) -> Role | None:
    """Helper to get a role by name"""
    statement = select(Role).where(Role.name == name)
    return session.exec(statement).first()
