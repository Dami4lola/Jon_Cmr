"""
Client API endpoints
"""
import logging
from fastapi import APIRouter, HTTPException, status
from sqlmodel import select

from ..models import Client, Job
from ..schemas.client import ClientCreate, ClientUpdate, ClientResponse
from ..services.distance import calculate_distance
from .deps import DBSession, ManagerUser, EstimatorUser

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/", response_model=list[ClientResponse])
def list_clients(
    session: DBSession,
    current_user: EstimatorUser,
    skip: int = 0,
    limit: int = 1000,
):
    """List all clients (manager, admin, or estimator)"""
    statement = select(Client).order_by(Client.name).offset(skip).limit(limit)
    clients = session.exec(statement).all()
    return clients


@router.post("/", response_model=ClientResponse, status_code=status.HTTP_201_CREATED)
def create_client(
    data: ClientCreate,
    session: DBSession,
    current_user: EstimatorUser,
):
    """Create a new client (manager, admin, or estimator - e.g. a new prospect on an estimate)"""
    client = Client(**data.model_dump())
    session.add(client)
    session.commit()
    session.refresh(client)
    return client


@router.get("/{client_id}", response_model=ClientResponse)
def get_client(
    client_id: int,
    session: DBSession,
    current_user: EstimatorUser,
):
    """Get a specific client (manager, admin, or estimator)"""
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
    current_user: EstimatorUser,
):
    """
    Update a client (manager, admin, or estimator).

    An estimator who can add a client can correct one - a wrong address would otherwise
    block them mid-estimate. Deleting stays manager-only: it is destructive and
    estimators are a wider group.
    """
    client = session.get(Client, client_id)

    if not client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Client not found",
        )

    old_address = client.address
    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(client, key, value)

    session.add(client)
    session.commit()
    session.refresh(client)

    # Recalculate distance for jobs using this client's address (no override)
    if "address" in update_data and client.address != old_address:
        jobs = session.exec(
            select(Job).where(Job.client_id == client_id, Job.address_override == None)
        ).all()
        for job in jobs:
            distance = calculate_distance(client.address)
            if distance is not None:
                job.calculated_distance_km = distance
                session.add(job)
        if jobs:
            session.commit()

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
