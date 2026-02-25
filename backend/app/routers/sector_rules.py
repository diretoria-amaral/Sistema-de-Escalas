from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, case
from typing import Optional, List
from datetime import date

from app.database import get_db
from app.models import Sector, SectorRule, TipoRegra, NivelRigidez
from app.schemas.sector_rule import (
    SectorRuleCreate, SectorRuleUpdate, SectorRuleResponse,
    SectorRuleListResponse, ReorderRequest, CloneRequest,
    RuleHierarchyResponse, RuleHierarchyItem
)
from app.services.rule_metadata_builder import build_metadata, generate_codigo_from_title

router = APIRouter(prefix="/api/sector-rules", tags=["Sector Rules"])


def get_tipo_order_expr():
    return case(
        (SectorRule.tipo_regra == TipoRegra.LABOR, 1),
        (SectorRule.tipo_regra == TipoRegra.SYSTEM, 2),
        (SectorRule.tipo_regra == TipoRegra.OPERATIONAL, 3),
        (SectorRule.tipo_regra == TipoRegra.CALCULATION, 4),
        else_=99
    )


def get_rigidez_order_expr():
    return case(
        (SectorRule.nivel_rigidez == NivelRigidez.MANDATORY, 1),
        (SectorRule.nivel_rigidez == NivelRigidez.DESIRABLE, 2),
        (SectorRule.nivel_rigidez == NivelRigidez.FLEXIBLE, 3),
        else_=99
    )


@router.get("", response_model=SectorRuleListResponse)
def list_sector_rules(
    setor_id: Optional[int] = Query(None, description="Filtrar por setor"),
    tipo_regra: Optional[TipoRegra] = Query(None, description="Filtrar por tipo de regra"),
    nivel_rigidez: Optional[NivelRigidez] = Query(None, description="Filtrar por nivel de rigidez"),
    regra_ativa: Optional[bool] = Query(None, description="Filtrar por status ativo"),
    include_deleted: bool = Query(False, description="Incluir regras deletadas"),
    db: Session = Depends(get_db)
):
    query = db.query(SectorRule)

    if not include_deleted:
        query = query.filter(SectorRule.deleted_at.is_(None))

    if setor_id:
        query = query.filter(SectorRule.setor_id == setor_id)
    if tipo_regra:
        query = query.filter(SectorRule.tipo_regra == tipo_regra)
    if nivel_rigidez:
        query = query.filter(SectorRule.nivel_rigidez == nivel_rigidez)
    if regra_ativa is not None:
        query = query.filter(SectorRule.regra_ativa == regra_ativa)

    query = query.order_by(
        SectorRule.setor_id,
        get_tipo_order_expr(),
        get_rigidez_order_expr(),
        SectorRule.prioridade
    )

    rules = query.all()
    return SectorRuleListResponse(items=rules, total=len(rules))


@router.get("/global", response_model=List[SectorRuleResponse])
def list_global_rules(
    tipo_regra: TipoRegra = Query(..., description="Tipo de regra global (LABOR ou SYSTEM)"),
    nivel_rigidez: Optional[NivelRigidez] = Query(None, description="Filtrar por nivel de rigidez"),
    regra_ativa: Optional[bool] = Query(None, description="Filtrar por status ativo (None = todas)"),
    db: Session = Depends(get_db)
):
    """Lista regras globais (LABOR ou SYSTEM) que nao estao vinculadas a um setor."""
    if tipo_regra not in [TipoRegra.LABOR, TipoRegra.SYSTEM]:
        raise HTTPException(status_code=400, detail="Apenas regras LABOR e SYSTEM podem ser globais")
    
    query = db.query(SectorRule).filter(
        SectorRule.is_global == True,
        SectorRule.tipo_regra == tipo_regra,
        SectorRule.deleted_at.is_(None)
    )
    
    if nivel_rigidez:
        query = query.filter(SectorRule.nivel_rigidez == nivel_rigidez)
    if regra_ativa is not None:
        query = query.filter(SectorRule.regra_ativa == regra_ativa)
    
    query = query.order_by(get_rigidez_order_expr(), SectorRule.prioridade)
    return query.all()


@router.post("/reorder-global/{tipo_regra}")
def reorder_global_rules(
    tipo_regra: TipoRegra,
    data: ReorderRequest,
    db: Session = Depends(get_db)
):
    """Reordena regras globais dentro de um bloco de rigidez."""
    if tipo_regra not in [TipoRegra.LABOR, TipoRegra.SYSTEM]:
        raise HTTPException(status_code=400, detail="Apenas regras LABOR e SYSTEM podem ser globais")
    
    if not data.rule_ids:
        raise HTTPException(status_code=400, detail="Lista de IDs vazia")
    
    first_rule = db.query(SectorRule).filter(
        SectorRule.id == data.rule_ids[0],
        SectorRule.deleted_at.is_(None)
    ).first()
    
    if not first_rule:
        raise HTTPException(status_code=404, detail="Regra nao encontrada")
    
    rigidity = first_rule.nivel_rigidez
    
    rules = db.query(SectorRule).filter(
        SectorRule.is_global == True,
        SectorRule.tipo_regra == tipo_regra,
        SectorRule.nivel_rigidez == rigidity,
        SectorRule.deleted_at.is_(None)
    ).all()

    rule_ids_set = {r.id for r in rules}
    provided_ids_set = set(data.rule_ids)

    if rule_ids_set != provided_ids_set:
        raise HTTPException(
            status_code=400,
            detail="Lista de IDs nao corresponde as regras existentes do bloco de rigidez"
        )

    rule_map = {r.id: r for r in rules}
    for new_priority, rule_id in enumerate(data.rule_ids, start=1):
        rule_map[rule_id].prioridade = new_priority

    db.commit()
    return {"message": "Ordem das regras globais atualizada com sucesso", "new_order": data.rule_ids}


@router.get("/hierarchy/{setor_id}", response_model=RuleHierarchyResponse)
def get_rule_hierarchy(setor_id: int, db: Session = Depends(get_db)):
    sector = db.query(Sector).filter(Sector.id == setor_id).first()
    if not sector:
        raise HTTPException(status_code=404, detail="Setor nao encontrado")

    global_rules = db.query(SectorRule).filter(
        SectorRule.is_global == True,
        SectorRule.deleted_at.is_(None),
        SectorRule.regra_ativa == True
    ).order_by(get_tipo_order_expr(), get_rigidez_order_expr(), SectorRule.prioridade).all()

    sector_rules = db.query(SectorRule).filter(
        SectorRule.setor_id == setor_id,
        SectorRule.is_global == False,
        SectorRule.deleted_at.is_(None),
        SectorRule.regra_ativa == True
    ).order_by(get_tipo_order_expr(), get_rigidez_order_expr(), SectorRule.prioridade).all()

    all_rules = global_rules + sector_rules

    labor_rules = []
    system_rules = []
    operational_rules = []
    calculation_rules = []

    for rule in all_rules:
        item = RuleHierarchyItem(
            codigo_regra=rule.codigo_regra,
            title=rule.title,
            tipo_regra=rule.tipo_regra,
            nivel_rigidez=rule.nivel_rigidez,
            prioridade=rule.prioridade,
            pergunta=rule.pergunta,
            resposta=rule.resposta,
            regra_ativa=rule.regra_ativa
        )
        if rule.tipo_regra == TipoRegra.LABOR:
            labor_rules.append(item)
        elif rule.tipo_regra == TipoRegra.SYSTEM:
            system_rules.append(item)
        elif rule.tipo_regra == TipoRegra.OPERATIONAL:
            operational_rules.append(item)
        else:
            calculation_rules.append(item)

    return RuleHierarchyResponse(
        setor_id=setor_id,
        setor_name=sector.name,
        labor_rules=labor_rules,
        system_rules=system_rules,
        operational_rules=operational_rules,
        calculation_rules=calculation_rules,
        total_rules=len(all_rules)
    )


@router.get("/{rule_id}", response_model=SectorRuleResponse)
def get_sector_rule(rule_id: int, db: Session = Depends(get_db)):
    rule = db.query(SectorRule).filter(SectorRule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Regra nao encontrada")
    return rule


@router.post("", response_model=SectorRuleResponse, status_code=201)
def create_sector_rule(data: SectorRuleCreate, db: Session = Depends(get_db)):
    is_global_rule = data.is_global or data.tipo_regra in [TipoRegra.LABOR, TipoRegra.SYSTEM]
    
    if is_global_rule:
        if data.tipo_regra not in [TipoRegra.LABOR, TipoRegra.SYSTEM]:
            raise HTTPException(status_code=400, detail="Regras globais devem ser do tipo LABOR ou SYSTEM")
        
        existing_codes = db.query(SectorRule.codigo_regra).filter(
            SectorRule.is_global == True,
            SectorRule.tipo_regra == data.tipo_regra,
            SectorRule.deleted_at.is_(None)
        ).all()
    else:
        if not data.setor_id:
            raise HTTPException(status_code=400, detail="Regras de setor requerem setor_id")
        
        sector = db.query(Sector).filter(Sector.id == data.setor_id).first()
        if not sector:
            raise HTTPException(status_code=404, detail="Setor nao encontrado")
        
        existing_codes = db.query(SectorRule.codigo_regra).filter(
            SectorRule.setor_id == data.setor_id,
            SectorRule.tipo_regra == data.tipo_regra,
            SectorRule.deleted_at.is_(None)
        ).all()

    existing_codes_list = [c[0] for c in existing_codes]
    
    codigo_regra = generate_codigo_from_title(data.title, data.tipo_regra.value, existing_codes_list)
    
    metadados_json = build_metadata(data.pergunta, data.resposta)
    
    rule_data = data.model_dump()
    rule_data["codigo_regra"] = codigo_regra
    rule_data["metadados_json"] = metadados_json
    rule_data["is_global"] = is_global_rule
    if is_global_rule:
        rule_data["setor_id"] = None
    
    rule = SectorRule(**rule_data)
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule


@router.put("/{rule_id}", response_model=SectorRuleResponse)
def update_sector_rule(rule_id: int, data: SectorRuleUpdate, db: Session = Depends(get_db)):
    rule = db.query(SectorRule).filter(
        SectorRule.id == rule_id,
        SectorRule.deleted_at.is_(None)
    ).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Regra nao encontrada")

    update_data = data.model_dump(exclude_unset=True)

    new_pergunta = update_data.get("pergunta", rule.pergunta)
    new_resposta = update_data.get("resposta", rule.resposta)
    
    if "pergunta" in update_data or "resposta" in update_data:
        update_data["metadados_json"] = build_metadata(new_pergunta, new_resposta)

    for key, value in update_data.items():
        setattr(rule, key, value)

    db.commit()
    db.refresh(rule)
    return rule


@router.delete("/{rule_id}")
def delete_sector_rule(rule_id: int, hard_delete: bool = False, db: Session = Depends(get_db)):
    rule = db.query(SectorRule).filter(SectorRule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Regra nao encontrada")

    if hard_delete:
        db.delete(rule)
    else:
        from datetime import datetime, timezone
        rule.deleted_at = datetime.now(timezone.utc)

    db.commit()
    return {"message": "Regra excluida com sucesso", "id": rule_id}


@router.post("/{rule_id}/toggle")
def toggle_sector_rule(rule_id: int, db: Session = Depends(get_db)):
    rule = db.query(SectorRule).filter(
        SectorRule.id == rule_id,
        SectorRule.deleted_at.is_(None)
    ).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Regra nao encontrada")

    rule.regra_ativa = not rule.regra_ativa
    db.commit()
    db.refresh(rule)
    return {"message": f"Regra {'ativada' if rule.regra_ativa else 'desativada'}", "regra_ativa": rule.regra_ativa}


@router.post("/reorder/{setor_id}/{tipo_regra}")
def reorder_rules(
    setor_id: int,
    tipo_regra: TipoRegra,
    data: ReorderRequest,
    db: Session = Depends(get_db)
):
    """
    Reordena regras dentro de um bloco de rigidez.
    Recebe uma lista de IDs na nova ordem desejada.
    A rigidez e inferida da primeira regra da lista.
    Garante atomicidade e consistencia de prioridades.
    """
    sector = db.query(Sector).filter(Sector.id == setor_id).first()
    if not sector:
        raise HTTPException(status_code=404, detail="Setor nao encontrado")
    
    if not data.rule_ids:
        raise HTTPException(status_code=400, detail="Lista de IDs vazia")
    
    first_rule = db.query(SectorRule).filter(
        SectorRule.id == data.rule_ids[0],
        SectorRule.deleted_at.is_(None)
    ).first()
    
    if not first_rule:
        raise HTTPException(status_code=404, detail="Regra nao encontrada")
    
    rigidity = first_rule.nivel_rigidez
    
    rules = db.query(SectorRule).filter(
        SectorRule.setor_id == setor_id,
        SectorRule.tipo_regra == tipo_regra,
        SectorRule.nivel_rigidez == rigidity,
        SectorRule.deleted_at.is_(None)
    ).all()

    rule_ids_set = {r.id for r in rules}
    provided_ids_set = set(data.rule_ids)

    if rule_ids_set != provided_ids_set:
        raise HTTPException(
            status_code=400,
            detail="Lista de IDs nao corresponde as regras existentes do bloco de rigidez"
        )
    
    all_same_rigidity = all(r.nivel_rigidez == rigidity for r in rules if r.id in provided_ids_set)
    if not all_same_rigidity:
        raise HTTPException(
            status_code=400,
            detail="Nao e permitido reordenar regras entre diferentes niveis de rigidez"
        )

    rule_map = {r.id: r for r in rules}
    for new_priority, rule_id in enumerate(data.rule_ids, start=1):
        rule_map[rule_id].prioridade = new_priority

    db.commit()
    return {"message": "Ordem das regras atualizada com sucesso", "new_order": data.rule_ids}


@router.post("/{rule_id}/clone", response_model=SectorRuleResponse, status_code=201)
def clone_sector_rule(rule_id: int, data: CloneRequest, db: Session = Depends(get_db)):
    rule = db.query(SectorRule).filter(
        SectorRule.id == rule_id,
        SectorRule.deleted_at.is_(None)
    ).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Regra nao encontrada")

    if rule.is_global:
        existing_codes = db.query(SectorRule.codigo_regra).filter(
            SectorRule.is_global == True,
            SectorRule.tipo_regra == rule.tipo_regra,
            SectorRule.deleted_at.is_(None)
        ).all()
    else:
        existing_codes = db.query(SectorRule.codigo_regra).filter(
            SectorRule.setor_id == rule.setor_id,
            SectorRule.tipo_regra == rule.tipo_regra,
            SectorRule.deleted_at.is_(None)
        ).all()
    existing_codes_list = [c[0] for c in existing_codes]
    
    new_codigo = generate_codigo_from_title(data.new_title, rule.tipo_regra.value, existing_codes_list)

    if rule.is_global:
        max_priority = db.query(SectorRule).filter(
            SectorRule.is_global == True,
            SectorRule.tipo_regra == rule.tipo_regra,
            SectorRule.nivel_rigidez == rule.nivel_rigidez,
            SectorRule.deleted_at.is_(None)
        ).count()
    else:
        max_priority = db.query(SectorRule).filter(
            SectorRule.setor_id == rule.setor_id,
            SectorRule.tipo_regra == rule.tipo_regra,
            SectorRule.nivel_rigidez == rule.nivel_rigidez,
            SectorRule.deleted_at.is_(None)
        ).count()

    new_rule = SectorRule(
        setor_id=rule.setor_id,
        is_global=rule.is_global,
        tipo_regra=rule.tipo_regra,
        nivel_rigidez=rule.nivel_rigidez,
        prioridade=max_priority + 1,
        codigo_regra=new_codigo,
        title=data.new_title,
        pergunta=rule.pergunta,
        resposta=rule.resposta,
        regra_ativa=False,
        validade_inicio=rule.validade_inicio,
        validade_fim=rule.validade_fim,
        metadados_json=rule.metadados_json
    )
    db.add(new_rule)
    db.commit()
    db.refresh(new_rule)
    return new_rule


@router.get("/active/{setor_id}", response_model=List[SectorRuleResponse])
def get_active_rules_for_date(
    setor_id: int,
    reference_date: Optional[date] = Query(None, description="Data de referencia (default: hoje)"),
    db: Session = Depends(get_db)
):
    if not reference_date:
        reference_date = date.today()

    query = db.query(SectorRule).filter(
        SectorRule.setor_id == setor_id,
        SectorRule.deleted_at.is_(None),
        SectorRule.regra_ativa == True
    )

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
        get_tipo_order_expr(),
        get_rigidez_order_expr(),
        SectorRule.prioridade
    )

    return query.all()
