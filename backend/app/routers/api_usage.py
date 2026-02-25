from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.database import get_db
from app.models.api_usage import ApiUsage
from app.schemas.api_usage import ApiUsage as ApiUsageSchema, ApiUsageStats, ApiUsageCreate
from typing import List

router = APIRouter(prefix="/api-usage", tags=["api-usage"])

@router.post("/record", response_model=ApiUsageSchema)
def record_usage(usage: ApiUsageCreate, db: Session = Depends(get_db)):
    db_usage = ApiUsage(**usage.dict())
    db.add(db_usage)
    db.commit()
    db.refresh(db_usage)
    return db_usage

@router.get("/stats", response_model=ApiUsageStats)
def get_stats(db: Session = Depends(get_db)):
    total_calls = db.query(func.count(ApiUsage.id)).scalar() or 0
    total_tokens = db.query(func.sum(ApiUsage.tokens_total)).scalar() or 0
    
    # Simple aggregation by provider
    providers = db.query(ApiUsage.provider, func.count(ApiUsage.id), func.sum(ApiUsage.tokens_total)).group_by(ApiUsage.provider).all()
    
    by_provider = {
        p[0]: {"calls": p[1], "tokens": p[2] or 0} for p in providers
    }
    
    return {
        "total_calls": total_calls,
        "total_tokens": total_tokens,
        "by_provider": by_provider
    }

@router.get("/history", response_model=List[ApiUsageSchema])
def get_history(limit: int = 100, db: Session = Depends(get_db)):
    return db.query(ApiUsage).order_by(ApiUsage.created_at.desc()).limit(limit).all()
