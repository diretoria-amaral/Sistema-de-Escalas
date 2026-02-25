from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import case
from typing import Optional, List
from datetime import date, datetime

from app.database import get_db
from app.models import Sector, SectorRule, TipoRegra, NivelRigidez
from app.schemas.rule_engine import (
    RuleCreate, RuleUpdate, RuleResponse, RuleListResponse,
    ReorderPayload, GroupedRulesResponse, LaborConstraintsResponse,
    ConsistencyCheckResponse
)
from app.services.rule_engine import RuleEngine

router = APIRouter(prefix="/api/rule-engine", tags=["Rule Engine"])


def get_tipo_order_expr():
    return case(
        (SectorRule.tipo_regra == TipoRegra.LABOR, 1),
        (SectorRule.tipo_regra == TipoRegra.OPERATIONAL, 2),
        (SectorRule.tipo_regra == TipoRegra.CALCULATION, 3),
        else_=99
    )


def get_rigidez_order_expr():
    return case(
        (SectorRule.nivel_rigidez == NivelRigidez.MANDATORY, 1),
        (SectorRule.nivel_rigidez == NivelRigidez.DESIRABLE, 2),
        (SectorRule.nivel_rigidez == NivelRigidez.FLEXIBLE, 3),
        else_=99
    )


@router.get("/rules", response_model=RuleListResponse)
def list_rules(
    sector_id: Optional[int] = Query(None, description="Filtrar por setor"),
    type: Optional[TipoRegra] = Query(None, alias="type", description="Filtrar por tipo de regra"),
    active_only: bool = Query(True, description="Retornar apenas regras ativas"),
    reference_date: Optional[date] = Query(None, description="Data de referencia para validade"),
    db: Session = Depends(get_db)
):
    if reference_date is None:
        reference_date = date.today()

    query = db.query(SectorRule).filter(SectorRule.deleted_at.is_(None))

    if sector_id:
        query = query.filter(SectorRule.setor_id == sector_id)
    if type:
        query = query.filter(SectorRule.tipo_regra == type)

    if active_only:
        query = query.filter(SectorRule.regra_ativa == True)
        from sqlalchemy import or_
        query = query.filter(
            or_(
                SectorRule.validade_inicio.is_(None),
                SectorRule.validade_inicio <= reference_date
            )
        )
        query = query.filter(
            or_(
                SectorRule.validade_fim.is_(None),
                SectorRule.validade_fim >= reference_date
            )
        )

    query = query.order_by(
        SectorRule.setor_id,
        get_tipo_order_expr(),
        get_rigidez_order_expr(),
        SectorRule.prioridade
    )

    rules = query.all()
    return RuleListResponse(items=rules, total=len(rules))


@router.get("/rules/grouped/{sector_id}", response_model=GroupedRulesResponse)
def get_grouped_rules(
    sector_id: int,
    reference_date: Optional[date] = Query(None),
    active_only: bool = Query(True, description="Default: retornar apenas regras ativas"),
    db: Session = Depends(get_db)
):
    sector = db.query(Sector).filter(Sector.id == sector_id).first()
    if not sector:
        raise HTTPException(status_code=404, detail="Setor nao encontrado")

    engine = RuleEngine(db)
    grouped = engine.fetch_rules(sector_id, reference_date, active_only=active_only)

    def rules_to_response(rules_list):
        return [RuleResponse.model_validate(r) for r in rules_list]

    return GroupedRulesResponse(
        labor={k: rules_to_response(v) for k, v in grouped.labor.items()},
        operational={k: rules_to_response(v) for k, v in grouped.operational.items()},
        calculation={k: rules_to_response(v) for k, v in grouped.calculation.items()}
    )


@router.get("/labor-constraints/{sector_id}", response_model=LaborConstraintsResponse)
def get_labor_constraints(sector_id: int, db: Session = Depends(get_db)):
    sector = db.query(Sector).filter(Sector.id == sector_id).first()
    if not sector:
        raise HTTPException(status_code=404, detail="Setor nao encontrado")

    engine = RuleEngine(db)
    constraints = engine.get_labor_constraints(sector_id)
    return LaborConstraintsResponse(**constraints)


@router.get("/consistency/{sector_id}/{tipo_regra}", response_model=ConsistencyCheckResponse)
def check_consistency(
    sector_id: int,
    tipo_regra: TipoRegra,
    db: Session = Depends(get_db)
):
    sector = db.query(Sector).filter(Sector.id == sector_id).first()
    if not sector:
        raise HTTPException(status_code=404, detail="Setor nao encontrado")

    engine = RuleEngine(db)
    is_valid, errors = engine.validate_rule_consistency(sector_id, tipo_regra)
    return ConsistencyCheckResponse(is_valid=is_valid, errors=errors)


@router.get("/rules/{rule_id}", response_model=RuleResponse)
def get_rule(rule_id: int, db: Session = Depends(get_db)):
    rule = db.query(SectorRule).filter(
        SectorRule.id == rule_id,
        SectorRule.deleted_at.is_(None)
    ).first()

    if not rule:
        raise HTTPException(status_code=404, detail="Regra nao encontrada")

    return rule


@router.post("/rules", response_model=RuleResponse, status_code=201)
def create_rule(payload: RuleCreate, db: Session = Depends(get_db)):
    sector = db.query(Sector).filter(Sector.id == payload.setor_id).first()
    if not sector:
        raise HTTPException(status_code=404, detail="Setor nao encontrado")

    existing = db.query(SectorRule).filter(
        SectorRule.setor_id == payload.setor_id,
        SectorRule.tipo_regra == payload.tipo_regra,
        SectorRule.codigo_regra == payload.codigo_regra,
        SectorRule.deleted_at.is_(None)
    ).first()

    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"Codigo de regra '{payload.codigo_regra}' ja existe para este setor e tipo"
        )

    rule = SectorRule(
        setor_id=payload.setor_id,
        tipo_regra=payload.tipo_regra,
        nivel_rigidez=payload.nivel_rigidez,
        prioridade=payload.prioridade,
        codigo_regra=payload.codigo_regra,
        pergunta=payload.pergunta,
        resposta=payload.resposta,
        regra_ativa=payload.regra_ativa,
        validade_inicio=payload.validade_inicio,
        validade_fim=payload.validade_fim,
        metadados_json=payload.metadados_json
    )

    db.add(rule)
    db.commit()
    db.refresh(rule)

    return rule


@router.put("/rules/{rule_id}", response_model=RuleResponse)
def update_rule(rule_id: int, payload: RuleUpdate, db: Session = Depends(get_db)):
    rule = db.query(SectorRule).filter(
        SectorRule.id == rule_id,
        SectorRule.deleted_at.is_(None)
    ).first()

    if not rule:
        raise HTTPException(status_code=404, detail="Regra nao encontrada")

    update_data = payload.model_dump(exclude_unset=True)

    for field, value in update_data.items():
        setattr(rule, field, value)

    db.commit()
    db.refresh(rule)

    return rule


@router.delete("/rules/{rule_id}")
def delete_rule(
    rule_id: int,
    hard_delete: bool = Query(False, description="Deletar permanentemente"),
    db: Session = Depends(get_db)
):
    rule = db.query(SectorRule).filter(SectorRule.id == rule_id).first()

    if not rule:
        raise HTTPException(status_code=404, detail="Regra nao encontrada")

    if hard_delete:
        db.delete(rule)
        db.commit()
        return {"message": "Regra deletada permanentemente", "id": rule_id}
    else:
        rule.regra_ativa = False
        rule.deleted_at = datetime.utcnow()
        db.commit()
        return {"message": "Regra desativada (soft delete)", "id": rule_id}


@router.post("/rules/reorder")
def reorder_rules(payload: ReorderPayload, db: Session = Depends(get_db)):
    sector = db.query(Sector).filter(Sector.id == payload.sector_id).first()
    if not sector:
        raise HTTPException(status_code=404, detail="Setor nao encontrado")

    rules = db.query(SectorRule).filter(
        SectorRule.id.in_(payload.ordered_rule_ids),
        SectorRule.setor_id == payload.sector_id,
        SectorRule.tipo_regra == payload.tipo_regra,
        SectorRule.nivel_rigidez == payload.nivel_rigidez,
        SectorRule.deleted_at.is_(None)
    ).all()

    if len(rules) != len(payload.ordered_rule_ids):
        raise HTTPException(
            status_code=400,
            detail="Algumas regras nao pertencem ao setor/tipo/nivel especificado"
        )

    rule_map = {r.id: r for r in rules}

    for idx, rule_id in enumerate(payload.ordered_rule_ids, start=1):
        if rule_id in rule_map:
            rule_map[rule_id].prioridade = idx

    db.commit()

    return {
        "message": "Prioridades atualizadas com sucesso",
        "sector_id": payload.sector_id,
        "tipo_regra": payload.tipo_regra.value,
        "nivel_rigidez": payload.nivel_rigidez.value,
        "updated_count": len(rules)
    }
