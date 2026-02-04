"""
Client API endpoints
"""
from fastapi import APIRouter, HTTPException, status
from sqlmodel import select

from ..models import Client
from ..schemas.client import ClientCreate, ClientUpdate, ClientResponse
from .deps import DBSession, ManagerUser

router = APIRouter()


@router.get("/", response_model=list[ClientResponse])
def list_clients(
    session: DBSession,
    current_user: ManagerUser,
):
    """List all clients (manager only)"""
    statement = select(Client).order_by(Client.name)
    clients = session.exec(statement).all()
    return clients


@router.post("/", response_model=ClientResponse, status_code=status.HTTP_201_CREATED)
def create_client(
    data: ClientCreate,
    session: DBSession,
    current_user: ManagerUser,
):
    """Create a new client (manager only)"""
    client = Client(**data.model_dump())
    session.add(client)
    session.commit()
    session.refresh(client)
    return client


@router.get("/{client_id}", response_model=ClientResponse)
def get_client(
    client_id: int,
    session: DBSession,
    current_user: ManagerUser,
):
    """Get a specific client (manager only)"""
    client = session.get(Client, client_id)

    if not client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Client not found",
        )

    return client


@router.put("/{client_id}", response_model=ClientResponse)
def update_client(
    client_id: int,
    data: ClientUpdate,
    session: DBSession,
    current_user: ManagerUser,
):
    """Update a client (manager only)"""
    client = session.get(Client, client_id)

    if not client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Client not found",
        )

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(client, key, value)

    session.add(client)
    session.commit()
    session.refresh(client)

    return client


@router.delete("/{client_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_client(
    client_id: int,
    session: DBSession,
    current_user: ManagerUser,
):
    """Delete a client (manager only)"""
    client = session.get(Client, client_id)

    if not client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Client not found",
        )

    session.delete(client)
    session.commit()
