from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Dict, List, Any, Optional
from pathlib import Path
import json

from app.database import get_db
from app.models import SectorRule, Sector, TipoRegra, NivelRigidez
from app.services.rule_metadata_builder import build_metadata, generate_codigo_from_title

router = APIRouter(prefix="/api/admin/rules", tags=["Admin Rules"])

TEMPLATE_PATH = Path(__file__).parent.parent / "templates" / "rules_seed_template.json"


def load_template() -> Dict[str, Any]:
    """Load the rules template from JSON file."""
    if not TEMPLATE_PATH.exists():
        raise HTTPException(status_code=500, detail=f"Template file not found: {TEMPLATE_PATH}")
    
    with open(TEMPLATE_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def rule_exists(
    db: Session,
    tipo_regra: TipoRegra,
    title: str,
    is_global: bool,
    setor_id: Optional[int] = None
) -> bool:
    """Check if a rule with the same title or similar pergunta already exists."""
    query = db.query(SectorRule).filter(
        SectorRule.tipo_regra == tipo_regra,
        SectorRule.is_global == is_global,
        SectorRule.deleted_at.is_(None)
    )
    
    if is_global:
        query = query.filter(SectorRule.setor_id.is_(None))
    else:
        query = query.filter(SectorRule.setor_id == setor_id)
    
    matching_title = query.filter(SectorRule.title == title).first()
    return matching_title is not None


def get_next_priority(
    db: Session,
    tipo_regra: TipoRegra,
    nivel_rigidez: NivelRigidez,
    is_global: bool,
    setor_id: Optional[int] = None
) -> int:
    """Get the next priority number for a rule."""
    query = db.query(SectorRule).filter(
        SectorRule.tipo_regra == tipo_regra,
        SectorRule.nivel_rigidez == nivel_rigidez,
        SectorRule.is_global == is_global,
        SectorRule.deleted_at.is_(None)
    )
    
    if is_global:
        query = query.filter(SectorRule.setor_id.is_(None))
    else:
        query = query.filter(SectorRule.setor_id == setor_id)
    
    existing_count = query.count()
    return existing_count + 1


def create_rule(
    db: Session,
    tipo_regra: TipoRegra,
    nivel_rigidez: NivelRigidez,
    title: str,
    pergunta: str,
    resposta: str,
    is_global: bool,
    setor_id: Optional[int] = None,
    priority: int = 1
) -> SectorRule:
    """Create a new rule."""
    existing_codes = db.query(SectorRule.codigo_regra).filter(
        SectorRule.tipo_regra == tipo_regra,
        SectorRule.is_global == is_global,
        SectorRule.deleted_at.is_(None)
    )
    
    if is_global:
        existing_codes = existing_codes.filter(SectorRule.setor_id.is_(None))
    else:
        existing_codes = existing_codes.filter(SectorRule.setor_id == setor_id)
    
    existing_codes_list = [c[0] for c in existing_codes.all()]
    codigo_regra = generate_codigo_from_title(title, tipo_regra.value, existing_codes_list)
    metadados_json = build_metadata(pergunta, resposta)
    
    rule = SectorRule(
        setor_id=setor_id,
        is_global=is_global,
        tipo_regra=tipo_regra,
        nivel_rigidez=nivel_rigidez,
        prioridade=priority,
        codigo_regra=codigo_regra,
        title=title,
        pergunta=pergunta,
        resposta=resposta,
        regra_ativa=True,
        metadados_json=metadados_json
    )
    
    db.add(rule)
    db.flush()
    return rule


@router.post("/seed-from-template")
def seed_rules_from_template(db: Session = Depends(get_db)):
    """
    Seed the database with rules from the template.
    This is idempotent - rules that already exist will be skipped.
    
    Returns a report of created and skipped rules.
    """
    template = load_template()
    
    report = {
        "global_rules": {
            "created": [],
            "skipped": []
        },
        "sector_rules": {
            "created": [],
            "skipped": []
        },
        "summary": {
            "total_processed": 0,
            "total_created": 0,
            "total_skipped": 0
        }
    }
    
    sectors = db.query(Sector).all()
    if not sectors:
        raise HTTPException(
            status_code=400, 
            detail="Nenhum setor cadastrado. Cadastre setores antes de fazer seed das regras setoriais."
        )
    
    for tipo_str, rigidez_rules in template.get("global_rules", {}).items():
        tipo_regra = TipoRegra(tipo_str)
        
        for rigidez_str, rules_list in rigidez_rules.items():
            nivel_rigidez = NivelRigidez(rigidez_str)
            
            for rule_data in rules_list:
                report["summary"]["total_processed"] += 1
                title = rule_data["title"]
                
                if rule_exists(db, tipo_regra, title, is_global=True):
                    report["global_rules"]["skipped"].append({
                        "tipo": tipo_str,
                        "rigidez": rigidez_str,
                        "title": title,
                        "reason": "Ja existe"
                    })
                    report["summary"]["total_skipped"] += 1
                else:
                    priority = get_next_priority(db, tipo_regra, nivel_rigidez, is_global=True)
                    create_rule(
                        db=db,
                        tipo_regra=tipo_regra,
                        nivel_rigidez=nivel_rigidez,
                        title=title,
                        pergunta=rule_data["pergunta"],
                        resposta=rule_data["resposta"],
                        is_global=True,
                        priority=priority
                    )
                    report["global_rules"]["created"].append({
                        "tipo": tipo_str,
                        "rigidez": rigidez_str,
                        "title": title,
                        "prioridade": priority
                    })
                    report["summary"]["total_created"] += 1
    
    for tipo_str, rigidez_rules in template.get("sector_rules", {}).items():
        tipo_regra = TipoRegra(tipo_str)
        
        for rigidez_str, rules_list in rigidez_rules.items():
            nivel_rigidez = NivelRigidez(rigidez_str)
            
            for rule_data in rules_list:
                title = rule_data["title"]
                
                for sector in sectors:
                    report["summary"]["total_processed"] += 1
                    
                    if rule_exists(db, tipo_regra, title, is_global=False, setor_id=sector.id):
                        report["sector_rules"]["skipped"].append({
                            "setor": sector.name,
                            "tipo": tipo_str,
                            "rigidez": rigidez_str,
                            "title": title,
                            "reason": "Ja existe"
                        })
                        report["summary"]["total_skipped"] += 1
                    else:
                        priority = get_next_priority(
                            db, tipo_regra, nivel_rigidez, 
                            is_global=False, setor_id=sector.id
                        )
                        create_rule(
                            db=db,
                            tipo_regra=tipo_regra,
                            nivel_rigidez=nivel_rigidez,
                            title=title,
                            pergunta=rule_data["pergunta"],
                            resposta=rule_data["resposta"],
                            is_global=False,
                            setor_id=sector.id,
                            priority=priority
                        )
                        report["sector_rules"]["created"].append({
                            "setor": sector.name,
                            "tipo": tipo_str,
                            "rigidez": rigidez_str,
                            "title": title,
                            "prioridade": priority
                        })
                        report["summary"]["total_created"] += 1
    
    db.commit()
    
    return {
        "success": True,
        "message": f"Seed concluido: {report['summary']['total_created']} regras criadas, {report['summary']['total_skipped']} ignoradas.",
        "report": report
    }


@router.get("/template")
def get_template():
    """Return the current rules template for inspection."""
    return load_template()


@router.delete("/clear-all")
def clear_all_rules(confirm: bool = False, db: Session = Depends(get_db)):
    """
    Clear all rules from the database. Requires confirm=true.
    This is a destructive operation - use with caution!
    """
    if not confirm:
        raise HTTPException(
            status_code=400,
            detail="Operacao destrutiva. Passe confirm=true para confirmar a exclusao de todas as regras."
        )
    
    deleted_count = db.query(SectorRule).filter(
        SectorRule.deleted_at.is_(None)
    ).count()
    
    from datetime import datetime
    db.query(SectorRule).filter(
        SectorRule.deleted_at.is_(None)
    ).update({"deleted_at": datetime.utcnow()})
    
    db.commit()
    
    return {
        "success": True,
        "message": f"{deleted_count} regras marcadas como excluidas.",
        "deleted_count": deleted_count
    }
