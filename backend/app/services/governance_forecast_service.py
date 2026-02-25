from datetime import date, datetime, timedelta
from typing import Dict, List, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import func, and_

from app.models.governance_module import (
    SectorOperationalParameters, ForecastRun, ForecastDaily,
    ForecastRunStatus
)
from app.models.data_lake import OccupancyLatest, OccupancySnapshot, WeekdayBiasStats

METHOD_VERSION = "1.0.1"

WEEKDAYS_PT = {
    0: "SEGUNDA-FEIRA",
    1: "TERÇA-FEIRA",
    2: "QUARTA-FEIRA",
    3: "QUINTA-FEIRA",
    4: "SEXTA-FEIRA",
    5: "SÁBADO",
    6: "DOMINGO"
}


class GovernanceForecastService:
    
    def __init__(self, db: Session):
        self.db = db
    
    def generate_weekly_forecast(
        self,
        sector_id: int,
        run_date: date = None,
        week_start: date = None,
        activity_ids: List[int] = None
    ) -> Dict:
        """
        Gera forecast semanal para governança.
        
        Args:
            sector_id: ID do setor (governança)
            run_date: Data de execução (default: hoje).
            week_start: Inicio da semana para o forecast (se None, calcula automaticamente).
            activity_ids: Lista de IDs de atividades selecionadas (opcional, para rastreabilidade).
        
        Returns:
            Dict com resultado da execução
        """
        if run_date is None:
            run_date = date.today()
        
        result = {
            "success": False,
            "forecast_run_id": None,
            "horizon_start": None,
            "horizon_end": None,
            "daily_forecasts": [],
            "selected_activity_ids": activity_ids or [],
            "errors": []
        }
        
        try:
            params = self._get_sector_parameters(sector_id)
            if not params:
                result["errors"].append(f"Parâmetros não encontrados para setor {sector_id}")
                return result
            
            if week_start is not None:
                days_since_monday = week_start.weekday()
                horizon_start = week_start - timedelta(days=days_since_monday)
                horizon_end = horizon_start + timedelta(days=6)
            else:
                horizon_start, horizon_end = self._calculate_horizon(run_date)
            result["horizon_start"] = horizon_start.isoformat()
            result["horizon_end"] = horizon_end.isoformat()
            
            forecast_run = ForecastRun(
                sector_id=sector_id,
                run_date=run_date,
                horizon_start=horizon_start,
                horizon_end=horizon_end,
                status=ForecastRunStatus.RUNNING,
                method_version=METHOD_VERSION,
                params_json={
                    "target_utilization_pct": params.target_utilization_pct,
                    "buffer_pct": params.buffer_pct,
                    "safety_pp_by_weekday": params.safety_pp_by_weekday,
                    "total_rooms": params.total_rooms,
                    "selected_activity_ids": activity_ids or [],
                    "week_start_explicit": week_start.isoformat() if week_start else None
                }
            )
            self.db.add(forecast_run)
            self.db.flush()
            
            result["forecast_run_id"] = forecast_run.id
            
            bias_stats = self._get_weekday_bias_stats()
            
            current_date = horizon_start
            while current_date <= horizon_end:
                weekday_idx = current_date.weekday()
                weekday_pt = WEEKDAYS_PT[weekday_idx]
                
                occ_raw = self._get_occ_raw(current_date, run_date)
                
                bias_pp = bias_stats.get(weekday_pt, 0.0)
                
                safety_pp = params.safety_pp_by_weekday.get(weekday_pt, 0.0) if params.safety_pp_by_weekday else 0.0
                
                occ_adj = self._clamp(occ_raw + bias_pp + safety_pp, 0, 100) if occ_raw is not None else None
                
                source_generated_at = self._get_source_generated_at(current_date, run_date)
                
                forecast_daily = ForecastDaily(
                    forecast_run_id=forecast_run.id,
                    target_date=current_date,
                    weekday_pt=weekday_pt,
                    occ_raw=occ_raw,
                    bias_pp_used=bias_pp,
                    safety_pp_used=safety_pp,
                    occ_adj=occ_adj,
                    data_source="occupancy_latest",
                    source_generated_at=source_generated_at
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
            if result["forecast_run_id"]:
                try:
                    run = self.db.query(ForecastRun).filter(ForecastRun.id == result["forecast_run_id"]).first()
                    if run:
                        run.status = ForecastRunStatus.FAILED
                        run.error_message = str(e)
                        self.db.commit()
                except:
                    pass
        
        return result
    
    def _get_sector_parameters(self, sector_id: int) -> Optional[SectorOperationalParameters]:
        """Obtém parâmetros operacionais vigentes do setor."""
        return self.db.query(SectorOperationalParameters).filter(
            SectorOperationalParameters.sector_id == sector_id,
            SectorOperationalParameters.is_current == True
        ).first()
    
    def _calculate_horizon(self, run_date: date) -> Tuple[date, date]:
        """
        Calcula horizonte do forecast (segunda a domingo da semana seguinte).
        """
        days_until_monday = (7 - run_date.weekday()) % 7
        if days_until_monday == 0:
            days_until_monday = 7
        
        horizon_start = run_date + timedelta(days=days_until_monday)
        horizon_end = horizon_start + timedelta(days=6)
        
        return horizon_start, horizon_end
    
    def _get_weekday_bias_stats(self) -> Dict[str, float]:
        """Obtém estatísticas de bias por dia da semana."""
        stats = self.db.query(WeekdayBiasStats).filter(
            WeekdayBiasStats.metric_name == "OCCUPANCY_BIAS_PP"
        ).all()
        
        return {s.weekday_pt: s.bias_pp for s in stats}
    
    def _get_friday_snapshot_date(self, run_date: date) -> date:
        """
        Calcula a sexta-feira de referência para o forecast.
        Se run_date é sexta, usa ela mesma. Caso contrário, busca a sexta anterior.
        """
        days_since_friday = (run_date.weekday() - 4) % 7
        if days_since_friday == 0:
            return run_date
        return run_date - timedelta(days=days_since_friday)
    
    def _get_occ_raw_from_friday_snapshot(
        self, 
        target_date: date, 
        friday_date: date
    ) -> Tuple[Optional[float], Optional[datetime]]:
        """
        Obtém ocupação do snapshot gerado na sexta-feira de referência.
        
        Regra: Busca o snapshot com generated_at mais próximo (e <= fim do dia) da sexta.
        Para garantir consistência, usa o mesmo "corte" de dados para toda a semana.
        """
        friday_end_of_day = datetime.combine(friday_date, datetime.max.time())
        
        snapshot = self.db.query(OccupancySnapshot).filter(
            OccupancySnapshot.target_date == target_date,
            OccupancySnapshot.generated_at <= friday_end_of_day
        ).order_by(OccupancySnapshot.generated_at.desc()).first()
        
        if snapshot:
            return snapshot.occupancy_pct, snapshot.generated_at
        
        return None, None
    
    def _get_occ_raw(self, target_date: date, run_date: date) -> Optional[float]:
        """
        Obtém ocupação raw usando o snapshot da sexta-feira de referência.
        Garante que toda a semana use dados do mesmo corte.
        Fallback para OccupancyLatest se não houver snapshot.
        """
        friday = self._get_friday_snapshot_date(run_date)
        occ_pct, _ = self._get_occ_raw_from_friday_snapshot(target_date, friday)
        
        if occ_pct is not None:
            return occ_pct
        
        latest = self.db.query(OccupancyLatest).filter(
            OccupancyLatest.target_date == target_date
        ).first()
        
        if latest:
            if latest.latest_forecast_occupancy_pct is not None:
                return latest.latest_forecast_occupancy_pct
            if latest.latest_real_occupancy_pct is not None:
                return latest.latest_real_occupancy_pct
            return latest.occupancy_pct
        
        return None
    
    def _get_source_generated_at(self, target_date: date, run_date: date) -> Optional[datetime]:
        """Obtém timestamp da fonte de dados (snapshot da sexta ou fallback)."""
        friday = self._get_friday_snapshot_date(run_date)
        occ_pct, generated_at = self._get_occ_raw_from_friday_snapshot(target_date, friday)
        
        if generated_at is not None:
            return generated_at
        
        latest = self.db.query(OccupancyLatest).filter(
            OccupancyLatest.target_date == target_date
        ).first()
        
        if latest:
            return latest.latest_forecast_generated_at or latest.latest_real_generated_at
        
        return None
    
    def _clamp(self, value: float, min_val: float, max_val: float) -> float:
        """Limita valor entre min e max."""
        return max(min_val, min(max_val, value))
    
    def get_forecast_run(self, run_id: int) -> Optional[Dict]:
        """Obtém detalhes de uma execução de forecast."""
        run = self.db.query(ForecastRun).filter(ForecastRun.id == run_id).first()
        if not run:
            return None
        
        daily = self.db.query(ForecastDaily).filter(
            ForecastDaily.forecast_run_id == run_id
        ).order_by(ForecastDaily.target_date).all()
        
        return {
            "id": run.id,
            "sector_id": run.sector_id,
            "run_date": run.run_date.isoformat(),
            "horizon_start": run.horizon_start.isoformat(),
            "horizon_end": run.horizon_end.isoformat(),
            "status": run.status.value,
            "method_version": run.method_version,
            "params": run.params_json,
            "created_at": run.created_at.isoformat() if run.created_at else None,
            "daily_forecasts": [
                {
                    "target_date": d.target_date.isoformat(),
                    "weekday_pt": d.weekday_pt,
                    "occ_raw": round(d.occ_raw, 2) if d.occ_raw else None,
                    "bias_pp": round(d.bias_pp_used, 2),
                    "safety_pp": round(d.safety_pp_used, 2),
                    "occ_adj": round(d.occ_adj, 2) if d.occ_adj else None
                }
                for d in daily
            ]
        }
    
    def list_forecast_runs(self, sector_id: int, limit: int = 10) -> List[Dict]:
        """Lista execuções de forecast do setor."""
        runs = self.db.query(ForecastRun).filter(
            ForecastRun.sector_id == sector_id
        ).order_by(ForecastRun.run_date.desc()).limit(limit).all()
        
        return [
            {
                "id": r.id,
                "run_date": r.run_date.isoformat(),
                "horizon_start": r.horizon_start.isoformat(),
                "horizon_end": r.horizon_end.isoformat(),
                "status": r.status.value,
                "created_at": r.created_at.isoformat() if r.created_at else None
            }
            for r in runs
        ]
