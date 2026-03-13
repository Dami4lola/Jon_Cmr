"""
Purchase List API endpoints
"""
from fastapi import APIRouter, HTTPException, status
from sqlmodel import select
from datetime import datetime

from ..models import PurchaseListItem, User
from ..models.purchase_item import PurchaseStatus
from ..schemas.purchase import PurchaseItemCreate, PurchaseItemResponse
from .deps import DBSession, CurrentUser

router = APIRouter()


def item_to_response(item: PurchaseListItem, session) -> PurchaseItemResponse:
    """Convert PurchaseListItem to response with user names"""
    added_by_name = None
    purchased_by_name = None

    if item.added_by_id:
        user = session.get(User, item.added_by_id)
        added_by_name = user.username if user else None

    if item.purchased_by_id:
        user = session.get(User, item.purchased_by_id)
        purchased_by_name = user.username if user else None

    return PurchaseItemResponse(
        id=item.id,
        name=item.name,
        quantity=item.quantity,
        priority=item.priority,
        status=item.status,
        notes=item.notes,
        added_by_id=item.added_by_id,
        added_by_name=added_by_name,
        added_at=item.added_at,
        purchased_by_id=item.purchased_by_id,
        purchased_by_name=purchased_by_name,
        purchased_at=item.purchased_at,
    )


@router.get("/", response_model=dict)
def list_purchase_items(
    session: DBSession,
    current_user: CurrentUser,
):
    """List purchase items (needed + recent purchased)"""
    # Get needed items
    needed_statement = (
        select(PurchaseListItem)
        .where(PurchaseListItem.status == PurchaseStatus.NEEDED.value)
        .order_by(PurchaseListItem.priority, PurchaseListItem.added_at.desc())
    )
    needed_items = session.exec(needed_statement).all()

    # Get recent purchased items (last 20)
    purchased_statement = (
        select(PurchaseListItem)
        .where(PurchaseListItem.status == PurchaseStatus.PURCHASED.value)
        .order_by(PurchaseListItem.purchased_at.desc())
        .limit(20)
    )
    purchased_items = session.exec(purchased_statement).all()

    return {
        "needed": [item_to_response(item, session) for item in needed_items],
        "purchased": [item_to_response(item, session) for item in purchased_items],
    }


@router.post("/", response_model=PurchaseItemResponse, status_code=status.HTTP_201_CREATED)
def create_purchase_item(
    data: PurchaseItemCreate,
    session: DBSession,
    current_user: CurrentUser,
):
    """Add item to purchase list"""
    item = PurchaseListItem(
        name=data.name,
        quantity=data.quantity,
        priority=data.priority,
        notes=data.notes,
        added_by_id=current_user.id,
        status=PurchaseStatus.NEEDED.value,
    )

    session.add(item)
    session.commit()
    session.refresh(item)

    return item_to_response(item, session)


@router.get("/{item_id}", response_model=PurchaseItemResponse)
def get_purchase_item(
    item_id: int,
    session: DBSession,
    current_user: CurrentUser,
):
    """Get a specific purchase item"""
    item = session.get(PurchaseListItem, item_id)

    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Item not found",
        )

    return item_to_response(item, session)


@router.put("/{item_id}/purchased", response_model=PurchaseItemResponse)
def mark_item_purchased(
    item_id: int,
    session: DBSession,
    current_user: CurrentUser,
):
    """Mark an item as purchased"""
    item = session.get(PurchaseListItem, item_id)

    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Item not found",
        )

    item.status = PurchaseStatus.PURCHASED.value
    item.purchased_by_id = current_user.id
    item.purchased_at = datetime.utcnow()

    session.add(item)
    session.commit()
    session.refresh(item)

    return item_to_response(item, session)


@router.put("/{item_id}/needed", response_model=PurchaseItemResponse)
def mark_item_needed(
    item_id: int,
    session: DBSession,
    current_user: CurrentUser,
):
    """Mark an item as needed again"""
    item = session.get(PurchaseListItem, item_id)

    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Item not found",
        )

    item.status = PurchaseStatus.NEEDED.value
    item.purchased_by_id = None
    item.purchased_at = None

    session.add(item)
    session.commit()
    session.refresh(item)

    return item_to_response(item, session)


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_purchase_item(
    item_id: int,
    session: DBSession,
    current_user: CurrentUser,
):
    """Delete a purchase item"""
    item = session.get(PurchaseListItem, item_id)

    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Item not found",
        )

    session.delete(item)
    session.commit()
