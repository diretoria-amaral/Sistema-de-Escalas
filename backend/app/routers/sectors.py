from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app.models.sector import Sector
from app.schemas.sector import SectorCreate, SectorUpdate, SectorResponse

router = APIRouter(prefix="/sectors", tags=["Sectors"])


@router.get("/", response_model=List[SectorResponse])
def list_sectors(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    sectors = db.query(Sector).offset(skip).limit(limit).all()
    return sectors


@router.get("/{sector_id}", response_model=SectorResponse)
def get_sector(sector_id: int, db: Session = Depends(get_db)):
    sector = db.query(Sector).filter(Sector.id == sector_id).first()
    if not sector:
        raise HTTPException(status_code=404, detail="Sector not found")
    return sector


@router.post("/", response_model=SectorResponse)
def create_sector(sector: SectorCreate, db: Session = Depends(get_db)):
    existing = db.query(Sector).filter(
        (Sector.name == sector.name) | (Sector.code == sector.code)
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Sector with this name or code already exists")
    
    db_sector = Sector(**sector.model_dump())
    db.add(db_sector)
    db.commit()
    db.refresh(db_sector)
    return db_sector


@router.put("/{sector_id}", response_model=SectorResponse)
def update_sector(sector_id: int, sector: SectorUpdate, db: Session = Depends(get_db)):
    db_sector = db.query(Sector).filter(Sector.id == sector_id).first()
    if not db_sector:
        raise HTTPException(status_code=404, detail="Sector not found")
    
    update_data = sector.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_sector, key, value)
    
    db.commit()
    db.refresh(db_sector)
    return db_sector


@router.delete("/{sector_id}")
def delete_sector(sector_id: int, db: Session = Depends(get_db)):
    db_sector = db.query(Sector).filter(Sector.id == sector_id).first()
    if not db_sector:
        raise HTTPException(status_code=404, detail="Sector not found")
    
    db.delete(db_sector)
    db.commit()
    return {"message": "Sector deleted successfully"}
