"""
ForecastRunService - Serviço para gerenciar rodadas de forecast (Baseline + Updates).

Fase 2: Implementa conceito formal de Forecast Run com:
- BASELINE: Gerado na sexta-feira, pode ser travado (locked)
- DAILY_UPDATE: Atualização diária para comparar com baseline
- Comparação Planejado x Atualizado x Real
"""
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_

from app.models.governance_module import (
    SectorOperationalParameters, ForecastRun, ForecastDaily,
    ForecastRunStatus, ForecastRunType
)
from app.models.governance_activity import GovernanceActivity
from app.models.data_lake import (
    OccupancyLatest, OccupancySnapshot, WeekdayBiasStats
)
from app.models.activity_program import ActivityProgramWeek, ActivityProgramItem, ProgramWeekStatus
from app.models.sector import Sector

METHOD_VERSION = "2.0.0"

WEEKDAYS_PT = {
    0: "SEGUNDA-FEIRA",
    1: "TERÇA-FEIRA",
    2: "QUARTA-FEIRA",
    3: "QUINTA-FEIRA",
    4: "SEXTA-FEIRA",
    5: "SÁBADO",
    6: "DOMINGO"
}


class ForecastRunService:
    
    def __init__(self, db: Session):
        self.db = db
    
    def check_prerequisites(
        self,
        sector_id: int,
        week_start: date = None
    ) -> Dict:
        """
        Verifica pré-requisitos obrigatórios para geração de Baseline.
        
        Validações:
        1. Setor existe
        2. Parâmetros operacionais do setor estão configurados
        3. Atividades de governança estão cadastradas para o setor
        4. Dados históricos de ocupação (HP) estão disponíveis
        
        Returns:
            Dict com status de cada pré-requisito e bloqueio se inválido
        """
        run_date = date.today()
        
        if week_start is None:
            week_start = self._next_monday(run_date)
        
        week_end = week_start + timedelta(days=6)
        
        result = {
            "can_generate": True,
            "sector_id": sector_id,
            "week_start": week_start.isoformat(),
            "week_end": week_end.isoformat(),
            "prerequisites": {
                "sector": {"valid": False, "message": "", "details": None},
                "parameters": {"valid": False, "message": "", "details": None},
                "activities": {"valid": False, "message": "", "details": None},
                "historical_data": {"valid": False, "message": "", "details": None}
            },
            "blocking_errors": [],
            "warnings": []
        }
        
        sector = self.db.query(Sector).filter(Sector.id == sector_id).first()
        if sector:
            result["prerequisites"]["sector"] = {
                "valid": True,
                "message": f"Setor '{sector.name}' encontrado.",
                "details": {"id": sector.id, "name": sector.name}
            }
        else:
            result["prerequisites"]["sector"] = {
                "valid": False,
                "message": f"Setor ID {sector_id} não encontrado no sistema.",
                "details": None
            }
            result["blocking_errors"].append(
                f"Setor ID {sector_id} não existe. Cadastre o setor antes de gerar o planejamento."
            )
            result["can_generate"] = False
        
        params = self._get_sector_parameters(sector_id)
        if params:
            result["prerequisites"]["parameters"] = {
                "valid": True,
                "message": "Parâmetros operacionais configurados.",
                "details": {
                    "total_rooms": params.total_rooms,
                    "target_utilization_pct": params.target_utilization_pct,
                    "buffer_pct": params.buffer_pct,
                    "has_safety_margins": bool(params.safety_pp_by_weekday)
                }
            }
        else:
            result["prerequisites"]["parameters"] = {
                "valid": False,
                "message": f"Parâmetros operacionais não encontrados para o setor {sector_id}.",
                "details": None
            }
            result["blocking_errors"].append(
                "Parâmetros operacionais não configurados. "
                "Acesse 'Governança → Parâmetros' e configure: total de quartos, utilização alvo, buffer e margens de segurança."
            )
            result["can_generate"] = False
        
        activities = self.db.query(GovernanceActivity).filter(
            GovernanceActivity.sector_id == sector_id,
            GovernanceActivity.is_active == True
        ).all()
        
        if activities and len(activities) > 0:
            result["prerequisites"]["activities"] = {
                "valid": True,
                "message": f"{len(activities)} atividade(s) de governança cadastrada(s).",
                "details": {
                    "count": len(activities),
                    "activities": [{"id": a.id, "name": a.name, "code": a.code} for a in activities[:5]]
                }
            }
        else:
            result["prerequisites"]["activities"] = {
                "valid": False,
                "message": "Nenhuma atividade de governança ativa cadastrada para este setor.",
                "details": None
            }
            result["blocking_errors"].append(
                "Nenhuma atividade de governança cadastrada. "
                "Acesse 'Governança → Atividades' e cadastre as atividades de limpeza (ex: LVS, LET)."
            )
            result["can_generate"] = False
        
        snapshot_count = self.db.query(func.count(OccupancySnapshot.id)).scalar() or 0
        latest_count = self.db.query(func.count(OccupancyLatest.target_date)).scalar() or 0
        
        has_week_data = False
        week_dates = [week_start + timedelta(days=i) for i in range(7)]
        week_snapshots = self.db.query(OccupancySnapshot).filter(
            OccupancySnapshot.target_date.in_(week_dates)
        ).count()
        week_latest = self.db.query(OccupancyLatest).filter(
            OccupancyLatest.target_date.in_(week_dates)
        ).count()
        
        has_week_data = week_snapshots > 0 or week_latest > 0
        
        if snapshot_count > 0 or latest_count > 0:
            result["prerequisites"]["historical_data"] = {
                "valid": True,
                "message": f"Dados históricos disponíveis: {snapshot_count} snapshots, {latest_count} registros latest.",
                "details": {
                    "total_snapshots": snapshot_count,
                    "total_latest": latest_count,
                    "has_week_data": has_week_data,
                    "week_snapshots": week_snapshots,
                    "week_latest": week_latest
                }
            }
            if not has_week_data:
                result["warnings"].append(
                    f"Nenhum dado de ocupação encontrado para a semana {week_start.isoformat()} a {week_end.isoformat()}. "
                    "O forecast usará valores históricos disponíveis."
                )
        else:
            result["prerequisites"]["historical_data"] = {
                "valid": False,
                "message": "Nenhum dado histórico de ocupação (HP) encontrado.",
                "details": None
            }
            result["blocking_errors"].append(
                "Nenhum dado de ocupação (HP) importado. "
                "Acesse 'Data Lake → Uploads' e importe pelo menos um relatório HP do sistema hoteleiro."
            )
            result["can_generate"] = False
        
        return result
    
    def create_baseline(
        self,
        sector_id: int,
        week_start: date = None,
        as_of_datetime: datetime = None,
        safety_pp_by_weekday: Dict[str, float] = None,
        alpha: float = 0.2,
        created_by: str = None,
        notes: str = None
    ) -> Dict:
        """
        Cria um Forecast Run do tipo BASELINE para a semana especificada.
        
        Args:
            sector_id: ID do setor
            week_start: Segunda-feira da semana alvo (se None, calcula próxima semana)
            as_of_datetime: Data/hora de corte para buscar forecasts (default: agora)
            safety_pp_by_weekday: Margem de segurança por dia (opcional, usa params do setor)
            alpha: Parâmetro do EWMA para bias
            created_by: Usuário que criou
            notes: Observações
        
        Returns:
            Dict com resultado da criação
        """
        result = {
            "success": False,
            "run_id": None,
            "run_type": "BASELINE",
            "horizon_start": None,
            "horizon_end": None,
            "daily_forecasts": [],
            "errors": []
        }
        
        try:
            run_date = date.today()
            
            if week_start is None:
                week_start = self._next_monday(run_date)
            
            week_end = week_start + timedelta(days=6)
            
            if as_of_datetime is None:
                as_of_datetime = datetime.now()
            
            result["horizon_start"] = week_start.isoformat()
            result["horizon_end"] = week_end.isoformat()
            
            params = self._get_sector_parameters(sector_id)
            if not params:
                result["errors"].append(f"Parâmetros não encontrados para setor {sector_id}")
                return result
            
            if safety_pp_by_weekday is None:
                safety_pp_by_weekday = params.safety_pp_by_weekday or {}
            
            bias_stats = self._get_weekday_bias_stats()
            
            forecast_run = ForecastRun(
                sector_id=sector_id,
                run_type=ForecastRunType.BASELINE,
                run_date=run_date,
                run_datetime=as_of_datetime,
                horizon_start=week_start,
                horizon_end=week_end,
                as_of_datetime=as_of_datetime,
                status=ForecastRunStatus.RUNNING,
                is_locked=False,
                method_version=METHOD_VERSION,
                bias_method="EWMA",
                bias_params_json={"alpha": alpha},
                params_json={
                    "safety_pp_by_weekday": safety_pp_by_weekday,
                    "total_rooms": params.total_rooms
                },
                created_by=created_by,
                notes=notes
            )
            self.db.add(forecast_run)
            self.db.flush()
            
            result["run_id"] = forecast_run.id
            
            current_date = week_start
            while current_date <= week_end:
                weekday_idx = current_date.weekday()
                weekday_pt = WEEKDAYS_PT[weekday_idx]
                
                occ_raw, source_snapshot_id, source_generated_at = self._get_occ_raw_with_source(
                    current_date, as_of_datetime
                )
                
                bias_pp = bias_stats.get(weekday_pt, 0.0)
                safety_pp = safety_pp_by_weekday.get(weekday_pt, 0.0)
                
                occ_adj = self._clamp(occ_raw + bias_pp + safety_pp, 0, 100) if occ_raw is not None else None
                
                forecast_daily = ForecastDaily(
                    forecast_run_id=forecast_run.id,
                    target_date=current_date,
                    weekday_pt=weekday_pt,
                    occ_raw=occ_raw,
                    bias_pp_used=bias_pp,
                    safety_pp_used=safety_pp,
                    occ_adj=occ_adj,
                    data_source="occupancy_snapshot" if source_snapshot_id else "occupancy_latest",
                    source_generated_at=source_generated_at,
                    source_snapshot_id=source_snapshot_id
                )
                self.db.add(forecast_daily)
                
                result["daily_forecasts"].append({
                    "target_date": current_date.isoformat(),
                    "weekday_pt": weekday_pt,
                    "occ_raw": round(occ_raw, 2) if occ_raw else None,
                    "bias_pp": round(bias_pp, 2),
                    "safety_pp": round(safety_pp, 2),
                    "occ_adj": round(occ_adj, 2) if occ_adj else None,
                    "source": "snapshot" if source_snapshot_id else "latest"
                })
                
                current_date += timedelta(days=1)
            
            forecast_run.status = ForecastRunStatus.COMPLETED
            self.db.commit()
            
            result["success"] = True
            
        except Exception as e:
            self.db.rollback()
            result["errors"].append(str(e))
            
        return result
    
    def create_daily_update(
        self,
        sector_id: int,
        week_start: date = None,
        as_of_datetime: datetime = None,
        created_by: str = None
    ) -> Dict:
        """
        Cria um Forecast Run do tipo DAILY_UPDATE para a semana especificada.
        Usa baseline ativo como referência de parâmetros.
        """
        result = {
            "success": False,
            "run_id": None,
            "run_type": "DAILY_UPDATE",
            "baseline_id": None,
            "horizon_start": None,
            "horizon_end": None,
            "daily_forecasts": [],
            "errors": []
        }
        
        try:
            run_date = date.today()
            
            if week_start is None:
                active_baseline = self._get_active_baseline_for_date(sector_id, run_date)
                if active_baseline:
                    week_start = active_baseline.horizon_start
                    result["baseline_id"] = active_baseline.id
                else:
                    week_start = self._get_current_week_monday(run_date)
            
            week_end = week_start + timedelta(days=6)
            
            if as_of_datetime is None:
                as_of_datetime = datetime.now()
            
            result["horizon_start"] = week_start.isoformat()
            result["horizon_end"] = week_end.isoformat()
            
            params = self._get_sector_parameters(sector_id)
            if not params:
                result["errors"].append(f"Parâmetros não encontrados para setor {sector_id}")
                return result
            
            safety_pp_by_weekday = params.safety_pp_by_weekday or {}
            bias_stats = self._get_weekday_bias_stats()
            
            forecast_run = ForecastRun(
                sector_id=sector_id,
                run_type=ForecastRunType.DAILY_UPDATE,
                run_date=run_date,
                run_datetime=as_of_datetime,
                horizon_start=week_start,
                horizon_end=week_end,
                as_of_datetime=as_of_datetime,
                status=ForecastRunStatus.RUNNING,
                is_locked=False,
                method_version=METHOD_VERSION,
                bias_method="EWMA",
                bias_params_json={"alpha": 0.2},
                params_json={
                    "safety_pp_by_weekday": safety_pp_by_weekday,
                    "total_rooms": params.total_rooms
                },
                created_by=created_by
            )
            self.db.add(forecast_run)
            self.db.flush()
            
            result["run_id"] = forecast_run.id
            
            current_date = week_start
            while current_date <= week_end:
                weekday_idx = current_date.weekday()
                weekday_pt = WEEKDAYS_PT[weekday_idx]
                
                occ_raw, source_snapshot_id, source_generated_at = self._get_occ_raw_with_source(
                    current_date, as_of_datetime
                )
                
                bias_pp = bias_stats.get(weekday_pt, 0.0)
                safety_pp = safety_pp_by_weekday.get(weekday_pt, 0.0)
                
                occ_adj = self._clamp(occ_raw + bias_pp + safety_pp, 0, 100) if occ_raw is not None else None
                
                forecast_daily = ForecastDaily(
                    forecast_run_id=forecast_run.id,
                    target_date=current_date,
                    weekday_pt=weekday_pt,
                    occ_raw=occ_raw,
                    bias_pp_used=bias_pp,
                    safety_pp_used=safety_pp,
                    occ_adj=occ_adj,
                    data_source="occupancy_snapshot" if source_snapshot_id else "occupancy_latest",
                    source_generated_at=source_generated_at,
                    source_snapshot_id=source_snapshot_id
                )
                self.db.add(forecast_daily)
                
                result["daily_forecasts"].append({
                    "target_date": current_date.isoformat(),
                    "weekday_pt": weekday_pt,
                    "occ_raw": round(occ_raw, 2) if occ_raw else None,
                    "bias_pp": round(bias_pp, 2),
                    "safety_pp": round(safety_pp, 2),
                    "occ_adj": round(occ_adj, 2) if occ_adj else None
                })
                
                current_date += timedelta(days=1)
            
            forecast_run.status = ForecastRunStatus.COMPLETED
            self.db.commit()
            
            result["success"] = True
            
        except Exception as e:
            self.db.rollback()
            result["errors"].append(str(e))
            
        return result
    
    def lock_run(self, run_id: int) -> Dict:
        """
        Trava um Forecast Run do tipo BASELINE.
        Após travado, não pode ser alterado.
        """
        result = {"success": False, "errors": []}
        
        try:
            run = self.db.query(ForecastRun).filter(ForecastRun.id == run_id).first()
            
            if not run:
                result["errors"].append(f"Forecast Run {run_id} não encontrado")
                return result
            
            if run.run_type != ForecastRunType.BASELINE:
                result["errors"].append("Apenas BASELINE pode ser travado")
                return result
            
            if run.is_locked:
                result["errors"].append("Forecast Run já está travado")
                return result
            
            existing_locked = self.db.query(ForecastRun).filter(
                ForecastRun.sector_id == run.sector_id,
                ForecastRun.horizon_start == run.horizon_start,
                ForecastRun.run_type == ForecastRunType.BASELINE,
                ForecastRun.is_locked == True,
                ForecastRun.id != run_id
            ).first()
            
            if existing_locked:
                existing_locked.superseded_by_run_id = run_id
            
            run.is_locked = True
            run.locked_at = datetime.now()
            self.db.commit()
            
            result["success"] = True
            result["locked_at"] = run.locked_at.isoformat()
            
        except Exception as e:
            self.db.rollback()
            result["errors"].append(str(e))
            
        return result
    
    def get_active_baseline(self, sector_id: int, week_start: date) -> Optional[Dict]:
        """
        Retorna o baseline ativo (locked) para a semana especificada.
        """
        run = self.db.query(ForecastRun).filter(
            ForecastRun.sector_id == sector_id,
            ForecastRun.horizon_start == week_start,
            ForecastRun.run_type == ForecastRunType.BASELINE,
            ForecastRun.is_locked == True,
            ForecastRun.superseded_by_run_id == None
        ).order_by(ForecastRun.locked_at.desc()).first()
        
        if not run:
            return None
        
        return self._format_run_detail(run)
    
    def compare_runs(self, run_id_a: int, run_id_b: int) -> Dict:
        """
        Compara dois Forecast Runs e retorna diffs por dia.
        """
        result = {
            "success": False,
            "run_a": None,
            "run_b": None,
            "comparison": [],
            "summary": {},
            "errors": []
        }
        
        try:
            run_a = self.db.query(ForecastRun).filter(ForecastRun.id == run_id_a).first()
            run_b = self.db.query(ForecastRun).filter(ForecastRun.id == run_id_b).first()
            
            if not run_a:
                result["errors"].append(f"Run A ({run_id_a}) não encontrado")
                return result
            if not run_b:
                result["errors"].append(f"Run B ({run_id_b}) não encontrado")
                return result
            
            result["run_a"] = {
                "id": run_a.id,
                "run_type": run_a.run_type.value,
                "run_date": run_a.run_date.isoformat(),
                "is_locked": run_a.is_locked
            }
            result["run_b"] = {
                "id": run_b.id,
                "run_type": run_b.run_type.value,
                "run_date": run_b.run_date.isoformat(),
                "is_locked": run_b.is_locked
            }
            
            daily_a = {d.target_date: d for d in self.db.query(ForecastDaily).filter(
                ForecastDaily.forecast_run_id == run_id_a
            ).all()}
            
            daily_b = {d.target_date: d for d in self.db.query(ForecastDaily).filter(
                ForecastDaily.forecast_run_id == run_id_b
            ).all()}
            
            all_dates = sorted(set(daily_a.keys()) | set(daily_b.keys()))
            
            total_delta_raw = 0.0
            total_delta_adj = 0.0
            count = 0
            
            for target_date in all_dates:
                a = daily_a.get(target_date)
                b = daily_b.get(target_date)
                
                occ_raw_a = a.occ_raw if a else None
                occ_raw_b = b.occ_raw if b else None
                occ_adj_a = a.occ_adj if a else None
                occ_adj_b = b.occ_adj if b else None
                
                delta_raw = None
                delta_adj = None
                
                if occ_raw_a is not None and occ_raw_b is not None:
                    delta_raw = round(occ_raw_b - occ_raw_a, 2)
                    total_delta_raw += abs(delta_raw)
                    
                if occ_adj_a is not None and occ_adj_b is not None:
                    delta_adj = round(occ_adj_b - occ_adj_a, 2)
                    total_delta_adj += abs(delta_adj)
                    count += 1
                
                result["comparison"].append({
                    "target_date": target_date.isoformat(),
                    "weekday_pt": a.weekday_pt if a else (b.weekday_pt if b else None),
                    "occ_raw_a": round(occ_raw_a, 2) if occ_raw_a else None,
                    "occ_raw_b": round(occ_raw_b, 2) if occ_raw_b else None,
                    "delta_raw_pp": delta_raw,
                    "occ_adj_a": round(occ_adj_a, 2) if occ_adj_a else None,
                    "occ_adj_b": round(occ_adj_b, 2) if occ_adj_b else None,
                    "delta_adj_pp": delta_adj
                })
            
            result["summary"] = {
                "avg_delta_raw_pp": round(total_delta_raw / count, 2) if count > 0 else 0,
                "avg_delta_adj_pp": round(total_delta_adj / count, 2) if count > 0 else 0,
                "days_compared": count
            }
            
            result["success"] = True
            
        except Exception as e:
            result["errors"].append(str(e))
            
        return result
    
    def compute_forecast_errors(self, baseline_run_id: int) -> Dict:
        """
        Calcula erros do forecast comparando baseline com valores reais (occupancy_latest).
        Apenas para dias já passados.
        """
        result = {
            "success": False,
            "baseline_id": baseline_run_id,
            "errors_by_day": [],
            "summary": {},
            "errors": []
        }
        
        try:
            run = self.db.query(ForecastRun).filter(ForecastRun.id == baseline_run_id).first()
            if not run:
                result["errors"].append(f"Baseline {baseline_run_id} não encontrado")
                return result
            
            daily_forecasts = self.db.query(ForecastDaily).filter(
                ForecastDaily.forecast_run_id == baseline_run_id
            ).all()
            
            today = date.today()
            total_error_raw = 0.0
            total_error_adj = 0.0
            count_with_real = 0
            
            for fd in daily_forecasts:
                target = fd.target_date
                
                is_past = target < today
                
                real_occ = None
                latest = self.db.query(OccupancyLatest).filter(
                    OccupancyLatest.target_date == target
                ).first()
                
                if latest and latest.is_real:
                    real_occ = latest.occupancy_pct
                
                error_raw = None
                error_adj = None
                
                if real_occ is not None and fd.occ_raw is not None:
                    error_raw = round(real_occ - fd.occ_raw, 2)
                    total_error_raw += error_raw
                    
                if real_occ is not None and fd.occ_adj is not None:
                    error_adj = round(real_occ - fd.occ_adj, 2)
                    total_error_adj += error_adj
                    count_with_real += 1
                
                result["errors_by_day"].append({
                    "target_date": target.isoformat(),
                    "weekday_pt": fd.weekday_pt,
                    "is_past": is_past,
                    "has_real": real_occ is not None,
                    "occ_raw_forecast": round(fd.occ_raw, 2) if fd.occ_raw else None,
                    "occ_adj_forecast": round(fd.occ_adj, 2) if fd.occ_adj else None,
                    "occ_real": round(real_occ, 2) if real_occ else None,
                    "error_raw_pp": error_raw,
                    "error_adj_pp": error_adj
                })
            
            result["summary"] = {
                "days_total": len(daily_forecasts),
                "days_with_real": count_with_real,
                "avg_error_raw_pp": round(total_error_raw / count_with_real, 2) if count_with_real > 0 else None,
                "avg_error_adj_pp": round(total_error_adj / count_with_real, 2) if count_with_real > 0 else None
            }
            
            result["success"] = True
            
        except Exception as e:
            result["errors"].append(str(e))
            
        return result
    
    def list_runs(
        self,
        sector_id: int,
        week_start: date = None,
        run_type: str = None,
        limit: int = 20
    ) -> List[Dict]:
        """Lista forecast runs com filtros opcionais."""
        query = self.db.query(ForecastRun).filter(
            ForecastRun.sector_id == sector_id
        )
        
        if week_start:
            query = query.filter(ForecastRun.horizon_start == week_start)
        
        if run_type:
            query = query.filter(ForecastRun.run_type == ForecastRunType(run_type))
        
        runs = query.order_by(ForecastRun.run_datetime.desc()).limit(limit).all()
        
        return [self._format_run_summary(r) for r in runs]
    
    def get_run_detail(self, run_id: int) -> Optional[Dict]:
        """Obtém detalhes completos de um forecast run."""
        run = self.db.query(ForecastRun).filter(ForecastRun.id == run_id).first()
        if not run:
            return None
        return self._format_run_detail(run)
    
    def get_comparison_with_latest(self, baseline_id: int) -> Dict:
        """
        Compara baseline locked com o daily_update mais recente da mesma semana.
        """
        baseline = self.db.query(ForecastRun).filter(ForecastRun.id == baseline_id).first()
        if not baseline:
            return {"success": False, "errors": ["Baseline não encontrado"]}
        
        latest_update = self.db.query(ForecastRun).filter(
            ForecastRun.sector_id == baseline.sector_id,
            ForecastRun.horizon_start == baseline.horizon_start,
            ForecastRun.run_type == ForecastRunType.DAILY_UPDATE,
            ForecastRun.status == ForecastRunStatus.COMPLETED
        ).order_by(ForecastRun.run_datetime.desc()).first()
        
        if not latest_update:
            return {
                "success": True,
                "baseline_id": baseline_id,
                "latest_update_id": None,
                "message": "Nenhuma atualização diária encontrada para esta semana"
            }
        
        return self.compare_runs(baseline_id, latest_update.id)
    
    def get_executive_summary(
        self,
        baseline_id: int,
        threshold_pp: float = 2.0
    ) -> Dict:
        """
        Gera resumo executivo do forecast run com recomendações textuais.
        
        PROMPT 2 - Seção 3.3: Resumo executivo do run com:
        - Tabela com dias (SEG..DOM), baseline_adj, daily_adj, delta_pp
        - Flags: "mudança relevante" se abs(delta_pp) > limiar
        - Recomendação textual simples
        """
        result = {
            "success": False,
            "baseline_id": baseline_id,
            "has_comparison": False,
            "latest_update_id": None,
            "summary_table": [],
            "flags": [],
            "recommendations": [],
            "errors": []
        }
        
        try:
            comparison = self.get_comparison_with_latest(baseline_id)
            
            if not comparison.get("success"):
                result["errors"] = comparison.get("errors", ["Erro ao comparar runs"])
                return result
            
            if comparison.get("latest_update_id") is None:
                baseline = self.db.query(ForecastRun).filter(ForecastRun.id == baseline_id).first()
                if baseline:
                    daily = self.db.query(ForecastDaily).filter(
                        ForecastDaily.forecast_run_id == baseline_id
                    ).order_by(ForecastDaily.target_date).all()
                    
                    for d in daily:
                        result["summary_table"].append({
                            "weekday_pt": d.weekday_pt,
                            "target_date": d.target_date.isoformat(),
                            "baseline_adj": round(d.occ_adj, 1) if d.occ_adj else None,
                            "daily_adj": None,
                            "delta_pp": None,
                            "is_significant": False
                        })
                    
                    result["flags"].append({
                        "type": "SEM_ATUALIZACAO",
                        "message": "Nenhuma atualização diária disponível para comparação"
                    })
                    result["recommendations"].append(
                        "Execute uma atualização diária (POST /api/forecast-runs/daily-update) para gerar comparativo baseline vs atualizado."
                    )
                    result["success"] = True
                    return result
            
            result["has_comparison"] = True
            result["latest_update_id"] = comparison.get("run_b", {}).get("id")
            
            days_with_significant_change = []
            
            for day in comparison.get("comparison", []):
                weekday_pt = day.get("weekday_pt")
                delta = day.get("delta_adj_pp")
                is_significant = delta is not None and abs(delta) > threshold_pp
                
                result["summary_table"].append({
                    "weekday_pt": weekday_pt,
                    "target_date": day.get("target_date"),
                    "baseline_adj": day.get("occ_adj_a"),
                    "daily_adj": day.get("occ_adj_b"),
                    "delta_pp": delta,
                    "is_significant": is_significant
                })
                
                if is_significant:
                    days_with_significant_change.append({
                        "weekday_pt": weekday_pt,
                        "delta": delta,
                        "direction": "aumento" if delta > 0 else "redução"
                    })
            
            if days_with_significant_change:
                result["flags"].append({
                    "type": "MUDANCA_RELEVANTE",
                    "message": f"{len(days_with_significant_change)} dia(s) com variação > {threshold_pp}pp",
                    "days": [d["weekday_pt"] for d in days_with_significant_change]
                })
                
                day_names = ", ".join([d["weekday_pt"].split("-")[0].title() for d in days_with_significant_change[:3]])
                
                if days_with_significant_change[0]["delta"] > 0:
                    result["recommendations"].append(
                        f"Rever escala de governança em {day_names}: ocupação aumentou, considere adicionar camareiras."
                    )
                else:
                    result["recommendations"].append(
                        f"Rever escala de governança em {day_names}: ocupação diminuiu, ajuste possível redução de turnos."
                    )
            else:
                result["recommendations"].append(
                    "Forecast estável. Nenhum ajuste de escala necessário no momento."
                )
            
            avg_delta = comparison.get("summary", {}).get("avg_delta_adj_pp", 0)
            if abs(avg_delta) > threshold_pp * 2:
                result["flags"].append({
                    "type": "TENDENCIA_SEMANAL",
                    "message": f"Tendência semanal: {'alta' if avg_delta > 0 else 'baixa'} de {abs(avg_delta):.1f}pp em média"
                })
            
            result["success"] = True
            
        except Exception as e:
            result["errors"].append(str(e))
        
        return result
    
    def _get_sector_parameters(self, sector_id: int) -> Optional[SectorOperationalParameters]:
        return self.db.query(SectorOperationalParameters).filter(
            SectorOperationalParameters.sector_id == sector_id,
            SectorOperationalParameters.is_current == True
        ).first()
    
    def _get_weekday_bias_stats(self) -> Dict[str, float]:
        stats = self.db.query(WeekdayBiasStats).filter(
            WeekdayBiasStats.metric_name == "OCCUPANCY_BIAS_PP"
        ).all()
        return {s.weekday_pt: s.bias_pp for s in stats}
    
    def _get_occ_raw_with_source(
        self,
        target_date: date,
        as_of_datetime: datetime
    ) -> Tuple[Optional[float], Optional[int], Optional[datetime]]:
        """
        Obtém ocupação raw com referência à fonte para auditoria.
        Busca snapshot FORECAST mais recente com generated_at <= as_of_datetime.
        """
        snapshot = self.db.query(OccupancySnapshot).filter(
            OccupancySnapshot.target_date == target_date,
            OccupancySnapshot.is_real == False,
            OccupancySnapshot.generated_at <= as_of_datetime
        ).order_by(OccupancySnapshot.generated_at.desc()).first()
        
        if snapshot:
            return snapshot.occupancy_pct, snapshot.id, snapshot.generated_at
        
        latest = self.db.query(OccupancyLatest).filter(
            OccupancyLatest.target_date == target_date
        ).first()
        
        if latest:
            occ_pct = None
            gen_at = None
            
            if latest.latest_forecast_occupancy_pct is not None:
                occ_pct = latest.latest_forecast_occupancy_pct
                gen_at = latest.latest_forecast_generated_at
            elif latest.occupancy_pct is not None:
                occ_pct = latest.occupancy_pct
                gen_at = latest.latest_real_generated_at or latest.latest_forecast_generated_at
            
            return occ_pct, None, gen_at
        
        return None, None, None
    
    def _next_monday(self, from_date: date) -> date:
        """Calcula próxima segunda-feira."""
        days_ahead = (7 - from_date.weekday()) % 7
        if days_ahead == 0:
            days_ahead = 7
        return from_date + timedelta(days=days_ahead)
    
    def _get_current_week_monday(self, from_date: date) -> date:
        """Obtém segunda-feira da semana atual."""
        return from_date - timedelta(days=from_date.weekday())
    
    def _get_active_baseline_for_date(self, sector_id: int, target_date: date) -> Optional[ForecastRun]:
        """Obtém baseline ativo que cobre a data especificada."""
        return self.db.query(ForecastRun).filter(
            ForecastRun.sector_id == sector_id,
            ForecastRun.horizon_start <= target_date,
            ForecastRun.horizon_end >= target_date,
            ForecastRun.run_type == ForecastRunType.BASELINE,
            ForecastRun.is_locked == True,
            ForecastRun.superseded_by_run_id == None
        ).order_by(ForecastRun.locked_at.desc()).first()
    
    def _clamp(self, value: float, min_val: float, max_val: float) -> float:
        return max(min_val, min(max_val, value))
    
    def _format_run_summary(self, run: ForecastRun) -> Dict:
        return {
            "id": run.id,
            "run_type": run.run_type.value,
            "run_date": run.run_date.isoformat(),
            "run_datetime": run.run_datetime.isoformat() if run.run_datetime else None,
            "horizon_start": run.horizon_start.isoformat(),
            "horizon_end": run.horizon_end.isoformat(),
            "status": run.status.value,
            "is_locked": run.is_locked,
            "locked_at": run.locked_at.isoformat() if run.locked_at else None,
            "method_version": run.method_version
        }
    
    def _format_run_detail(self, run: ForecastRun) -> Dict:
        daily = self.db.query(ForecastDaily).filter(
            ForecastDaily.forecast_run_id == run.id
        ).order_by(ForecastDaily.target_date).all()
        
        return {
            "id": run.id,
            "sector_id": run.sector_id,
            "run_type": run.run_type.value,
            "run_date": run.run_date.isoformat(),
            "run_datetime": run.run_datetime.isoformat() if run.run_datetime else None,
            "horizon_start": run.horizon_start.isoformat(),
            "horizon_end": run.horizon_end.isoformat(),
            "as_of_datetime": run.as_of_datetime.isoformat() if run.as_of_datetime else None,
            "status": run.status.value,
            "is_locked": run.is_locked,
            "locked_at": run.locked_at.isoformat() if run.locked_at else None,
            "method_version": run.method_version,
            "bias_method": run.bias_method,
            "bias_params": run.bias_params_json,
            "params": run.params_json,
            "notes": run.notes,
            "created_by": run.created_by,
            "created_at": run.created_at.isoformat() if run.created_at else None,
            "daily_forecasts": [
                {
                    "target_date": d.target_date.isoformat(),
                    "weekday_pt": d.weekday_pt,
                    "occ_raw": round(d.occ_raw, 2) if d.occ_raw else None,
                    "bias_pp": round(d.bias_pp_used, 2),
                    "safety_pp": round(d.safety_pp_used, 2),
                    "occ_adj": round(d.occ_adj, 2) if d.occ_adj else None,
                    "data_source": d.data_source,
                    "source_snapshot_id": d.source_snapshot_id
                }
                for d in daily
            ]
        }
