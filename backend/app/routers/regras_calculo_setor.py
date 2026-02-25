from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional

from app.database import get_db
from app.models.regra_calculo_setor import RegraCalculoSetor, RegraEscopo
from app.models.sector import Sector
from app.models.governance_activity import GovernanceActivity
from app.schemas.regra_calculo_setor import (
    RegraCalculoSetorCreate,
    RegraCalculoSetorUpdate,
    RegraCalculoSetorResponse,
    RegraCalculoSetorListResponse,
    validar_acao_json
)

router = APIRouter(prefix="/api/regras-calculo-setor", tags=["Regras de Cálculo por Setor"])


@router.get("", response_model=RegraCalculoSetorListResponse)
def listar_regras(
    setor_id: int = Query(..., description="ID do setor (obrigatório)"),
    escopo: Optional[str] = Query(None, description="Filtrar por escopo"),
    apenas_ativas: bool = Query(False, description="Retornar apenas regras ativas"),
    db: Session = Depends(get_db)
):
    """Lista regras de cálculo de um setor, ordenadas por prioridade."""
    setor = db.query(Sector).filter(Sector.id == setor_id).first()
    if not setor:
        raise HTTPException(status_code=404, detail="Setor não encontrado.")
    
    query = db.query(RegraCalculoSetor).filter(RegraCalculoSetor.setor_id == setor_id)
    
    if escopo:
        try:
            escopo_enum = RegraEscopo(escopo)
            query = query.filter(RegraCalculoSetor.escopo == escopo_enum)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Escopo inválido: {escopo}. Valores válidos: DEMANDA, PROGRAMACAO, AJUSTES"
            )
    
    if apenas_ativas:
        query = query.filter(RegraCalculoSetor.ativo == True)
    
    regras = query.order_by(RegraCalculoSetor.prioridade.asc()).all()
    
    return {"regras": regras, "total": len(regras)}


@router.get("/{regra_id}", response_model=RegraCalculoSetorResponse)
def obter_regra(regra_id: int, db: Session = Depends(get_db)):
    """Obtém uma regra específica por ID."""
    regra = db.query(RegraCalculoSetor).filter(RegraCalculoSetor.id == regra_id).first()
    if not regra:
        raise HTTPException(status_code=404, detail="Regra não encontrada.")
    return regra


@router.post("", response_model=RegraCalculoSetorResponse, status_code=201)
def criar_regra(regra: RegraCalculoSetorCreate, db: Session = Depends(get_db)):
    """Cria uma nova regra de cálculo para um setor."""
    setor = db.query(Sector).filter(Sector.id == regra.setor_id).first()
    if not setor:
        raise HTTPException(status_code=404, detail="Setor não encontrado.")
    
    if regra.acao_json.get("tipo") == "inserir_atividade":
        atividade_id = regra.acao_json.get("atividade_id")
        atividade = db.query(GovernanceActivity).filter(
            GovernanceActivity.id == atividade_id,
            GovernanceActivity.sector_id == regra.setor_id
        ).first()
        if not atividade:
            raise HTTPException(
                status_code=400,
                detail=f"Atividade {atividade_id} não encontrada ou não pertence ao setor."
            )
    
    db_regra = RegraCalculoSetor(
        setor_id=regra.setor_id,
        nome=regra.nome,
        descricao=regra.descricao,
        prioridade=regra.prioridade,
        escopo=regra.escopo,
        condicao_json=regra.condicao_json,
        acao_json=regra.acao_json,
        ativo=regra.ativo
    )
    
    db.add(db_regra)
    db.commit()
    db.refresh(db_regra)
    return db_regra


@router.put("/{regra_id}", response_model=RegraCalculoSetorResponse)
def atualizar_regra(regra_id: int, regra: RegraCalculoSetorUpdate, db: Session = Depends(get_db)):
    """Atualiza uma regra existente."""
    db_regra = db.query(RegraCalculoSetor).filter(RegraCalculoSetor.id == regra_id).first()
    if not db_regra:
        raise HTTPException(status_code=404, detail="Regra não encontrada.")
    
    update_data = regra.model_dump(exclude_unset=True)
    
    if "acao_json" in update_data:
        escopo = update_data.get("escopo", db_regra.escopo)
        if hasattr(escopo, 'value'):
            escopo = escopo.value
        try:
            validar_acao_json(update_data["acao_json"], escopo)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        
        if update_data["acao_json"].get("tipo") == "inserir_atividade":
            atividade_id = update_data["acao_json"].get("atividade_id")
            atividade = db.query(GovernanceActivity).filter(
                GovernanceActivity.id == atividade_id,
                GovernanceActivity.sector_id == db_regra.setor_id
            ).first()
            if not atividade:
                raise HTTPException(
                    status_code=400,
                    detail=f"Atividade {atividade_id} não encontrada ou não pertence ao setor."
                )
    
    for key, value in update_data.items():
        setattr(db_regra, key, value)
    
    db.commit()
    db.refresh(db_regra)
    return db_regra


@router.delete("/{regra_id}")
def excluir_regra(regra_id: int, db: Session = Depends(get_db)):
    """Exclui uma regra."""
    db_regra = db.query(RegraCalculoSetor).filter(RegraCalculoSetor.id == regra_id).first()
    if not db_regra:
        raise HTTPException(status_code=404, detail="Regra não encontrada.")
    
    db.delete(db_regra)
    db.commit()
    return {"message": "Regra excluída com sucesso."}


@router.post("/{regra_id}/duplicar", response_model=RegraCalculoSetorResponse, status_code=201)
def duplicar_regra(regra_id: int, db: Session = Depends(get_db)):
    """Duplica uma regra existente com novo nome e prioridade."""
    regra_original = db.query(RegraCalculoSetor).filter(RegraCalculoSetor.id == regra_id).first()
    if not regra_original:
        raise HTTPException(status_code=404, detail="Regra não encontrada.")
    
    max_prioridade = db.query(RegraCalculoSetor).filter(
        RegraCalculoSetor.setor_id == regra_original.setor_id
    ).order_by(RegraCalculoSetor.prioridade.desc()).first()
    
    nova_prioridade = (max_prioridade.prioridade + 10) if max_prioridade else 100
    
    nova_regra = RegraCalculoSetor(
        setor_id=regra_original.setor_id,
        nome=f"{regra_original.nome} (Cópia)",
        descricao=regra_original.descricao,
        prioridade=nova_prioridade,
        escopo=regra_original.escopo,
        condicao_json=regra_original.condicao_json,
        acao_json=regra_original.acao_json,
        ativo=False
    )
    
    db.add(nova_regra)
    db.commit()
    db.refresh(nova_regra)
    return nova_regra


@router.get("/validar/setor/{setor_id}")
def validar_regras_setor(setor_id: int, db: Session = Depends(get_db)):
    """
    Valida se o setor tem regras configuradas para atividades CALCULADAS_PELO_AGENTE.
    Retorna erros se houver atividades sem regras correspondentes.
    """
    setor = db.query(Sector).filter(Sector.id == setor_id).first()
    if not setor:
        raise HTTPException(status_code=404, detail="Setor não encontrado.")
    
    from app.models.governance_activity import ActivityClassification
    
    atividades_calculadas = db.query(GovernanceActivity).filter(
        GovernanceActivity.sector_id == setor_id,
        GovernanceActivity.classificacao_atividade == ActivityClassification.CALCULADA_PELO_AGENTE,
        GovernanceActivity.is_active == True
    ).all()
    
    regras_programacao = db.query(RegraCalculoSetor).filter(
        RegraCalculoSetor.setor_id == setor_id,
        RegraCalculoSetor.escopo == RegraEscopo.PROGRAMACAO,
        RegraCalculoSetor.ativo == True
    ).all()
    
    regras_demanda = db.query(RegraCalculoSetor).filter(
        RegraCalculoSetor.setor_id == setor_id,
        RegraCalculoSetor.escopo == RegraEscopo.DEMANDA,
        RegraCalculoSetor.ativo == True
    ).all()
    
    atividades_cobertas = set()
    for regra in regras_programacao:
        acao = regra.acao_json or {}
        if acao.get("tipo") == "inserir_atividade":
            atividades_cobertas.add(acao.get("atividade_id"))
    
    atividades_sem_regra = []
    for ativ in atividades_calculadas:
        if ativ.id not in atividades_cobertas:
            atividades_sem_regra.append({
                "id": ativ.id,
                "nome": ativ.name,
                "codigo": ativ.code
            })
    
    erros = []
    if atividades_sem_regra:
        erros.append({
            "tipo": "ATIVIDADES_SEM_REGRA",
            "mensagem": f"Existem {len(atividades_sem_regra)} atividades CALCULADAS_PELO_AGENTE sem regras de programação.",
            "detalhes": atividades_sem_regra
        })
    
    if atividades_calculadas and not regras_demanda:
        erros.append({
            "tipo": "SEM_REGRAS_DEMANDA",
            "mensagem": "Nenhuma regra de DEMANDA configurada para o setor."
        })
    
    return {
        "setor_id": setor_id,
        "setor_nome": setor.name,
        "total_atividades_calculadas": len(atividades_calculadas),
        "total_regras_programacao": len(regras_programacao),
        "total_regras_demanda": len(regras_demanda),
        "pode_usar_modo_auto": len(erros) == 0,
        "erros": erros
    }
