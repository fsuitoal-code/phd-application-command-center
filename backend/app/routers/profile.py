"""Applicant profile — the single research-identity row (get-or-create)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_session
from app.models import ApplicantProfile
from app.schemas import ProfileOut, ProfileUpdate

router = APIRouter(prefix="/api/profile", tags=["profile"])


def get_or_create_profile(session: Session) -> ApplicantProfile:
    profile = session.scalars(
        select(ApplicantProfile).order_by(ApplicantProfile.id).limit(1)
    ).first()
    if profile is None:
        profile = ApplicantProfile()
        session.add(profile)
        session.commit()
        session.refresh(profile)
    return profile


@router.get("", response_model=ProfileOut)
def read_profile(session: Session = Depends(get_session)) -> ApplicantProfile:
    return get_or_create_profile(session)


@router.put("", response_model=ProfileOut)
def update_profile(
    payload: ProfileUpdate, session: Session = Depends(get_session)
) -> ApplicantProfile:
    profile = get_or_create_profile(session)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(profile, field, value)
    session.commit()
    session.refresh(profile)
    return profile
