
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..db import get_db, Base, engine
from .. import models, schemas

router = APIRouter(prefix="/machines", tags=["machines"]) 

# Zorg dat tabellen bestaan bij eerste start
Base.metadata.create_all(bind=engine)

@router.get("", response_model=list[schemas.MachineOut])
def list_machines(db: Session = Depends(get_db)):
    return db.query(models.Machine).all()

@router.post("", response_model=schemas.MachineOut)
def create_machine(payload: schemas.MachineIn, db: Session = Depends(get_db)):
    m = models.Machine(**payload.model_dump())
    db.add(m)
    db.commit()
    db.refresh(m)
    return m
