from datetime import date, datetime, timedelta
from typing import Dict, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
import math

from app.models.governance_module import TurnoverRateStats, SectorOperationalParameters
from app.models.data_lake import (
    FrontdeskEventsHourlyAgg, EventType,
    OccupancySnapshot
)

METHOD_VERSION = "1.0.0"

WEEKDAYS_PT = {
    0: "SEGUNDA-FEIRA",
    1: "TERÇA-FEIRA",
    2: "QUARTA-FEIRA",
    3: "QUINTA-FEIRA",
    4: "SEXTA-FEIRA",
    5: "SÁBADO",
    6: "DOMINGO"
}

DEFAULT_TURNOVER_RATES = {
    "DOMINGO": 0.55,
    "SEGUNDA-FEIRA": 0.35,
    "TERÇA-FEIRA": 0.25,
    "QUARTA-FEIRA": 0.25,
    "QUINTA-FEIRA": 0.30,
    "SEXTA-FEIRA": 0.35,
    "SÁBADO": 0.40
}

MIN_SAMPLES_THRESHOLD = 4


class TurnoverStatsService:
    
    def __init__(self, db: Session):
        self.db = db
    
    def compute_turnover_stats(
        self,
        sector_id: int = None,
        lookback_weeks: int = 12,
        min_samples: int = MIN_SAMPLES_THRESHOLD,
        alpha: float = 0.2
    ) -> Dict:
        """
        Calcula estatísticas de turnover por dia da semana usando histórico real.
        
        PROMPT 4: turnover_rate(weekday) = média de (checkouts_reais / rooms_occupied_real)
        
        Args:
            sector_id: ID do setor (opcional, calcula global se None)
            lookback_weeks: Semanas de histórico para análise
            min_samples: Mínimo de amostras para considerar estatística válida
            alpha: Parâmetro EWMA
        
        Returns:
            Dict com estatísticas por dia da semana
        """
        result = {
            "success": False,
            "sector_id": sector_id,
            "stats_by_weekday": {},
            "method": "EWMA",
            "alpha": alpha,
            "lookback_weeks": lookback_weeks,
            "total_samples": 0,
            "fallbacks_used": 0,
            "errors": []
        }
        
        try:
            end_date = date.today()
            start_date = end_date - timedelta(weeks=lookback_weeks)
            
            params = None
            total_rooms = 100
            if sector_id:
                params = self.db.query(SectorOperationalParameters).filter(
                    SectorOperationalParameters.sector_id == sector_id,
                    SectorOperationalParameters.is_current == True
                ).first()
                if params:
                    total_rooms = params.total_rooms or 100
            
            raw_data = self._collect_historical_data(start_date, end_date, total_rooms)
            
            for weekday_num in range(7):
                weekday_pt = WEEKDAYS_PT[weekday_num]
                weekday_data = [d for d in raw_data if d["weekday_num"] == weekday_num]
                
                stat = self._compute_weekday_stats(
                    weekday_pt=weekday_pt,
                    weekday_num=weekday_num,
                    data=weekday_data,
                    min_samples=min_samples,
                    alpha=alpha
                )
                
                existing = self.db.query(TurnoverRateStats).filter(
                    TurnoverRateStats.weekday_pt == weekday_pt,
                    TurnoverRateStats.sector_id == sector_id
                ).first()
                
                if existing:
                    existing.rate = stat["rate"]
                    existing.n = stat["n"]
                    existing.std = stat["std"]
                    existing.min_rate = stat["min_rate"]
                    existing.max_rate = stat["max_rate"]
                    existing.method = "EWMA"
                    existing.alpha = alpha
                    existing.fallback_used = stat["fallback_used"]
                    existing.fallback_reason = stat["fallback_reason"]
                    existing.last_updated_at = datetime.now()
                else:
                    new_stat = TurnoverRateStats(
                        sector_id=sector_id,
                        weekday_pt=weekday_pt,
                        weekday_num=weekday_num,
                        rate=stat["rate"],
                        n=stat["n"],
                        std=stat["std"],
                        min_rate=stat["min_rate"],
                        max_rate=stat["max_rate"],
                        method="EWMA",
                        alpha=alpha,
                        fallback_used=stat["fallback_used"],
                        fallback_reason=stat["fallback_reason"],
                        params_json={"lookback_weeks": lookback_weeks, "min_samples": min_samples}
                    )
                    self.db.add(new_stat)
                
                result["stats_by_weekday"][weekday_pt] = stat
                result["total_samples"] += stat["n"]
                if stat["fallback_used"]:
                    result["fallbacks_used"] += 1
            
            self.db.commit()
            result["success"] = True
            
        except Exception as e:
            self.db.rollback()
            result["errors"].append(str(e))
        
        return result
    
    def _collect_historical_data(
        self,
        start_date: date,
        end_date: date,
        total_rooms: int
    ) -> List[Dict]:
        """
        Coleta dados históricos de checkout e ocupação para calcular turnover.
        """
        data = []
        
        checkout_agg = self.db.query(
            FrontdeskEventsHourlyAgg.op_date,
            func.sum(FrontdeskEventsHourlyAgg.count_events).label("checkouts")
        ).filter(
            FrontdeskEventsHourlyAgg.op_date >= start_date,
            FrontdeskEventsHourlyAgg.op_date <= end_date,
            FrontdeskEventsHourlyAgg.event_type == EventType.CHECKOUT
        ).group_by(FrontdeskEventsHourlyAgg.op_date).all()
        
        checkout_by_date = {row.op_date: int(row.checkouts) for row in checkout_agg}
        
        occupancy_data = self.db.query(
            OccupancySnapshot.target_date,
            OccupancySnapshot.occupancy_pct
        ).filter(
            OccupancySnapshot.target_date >= start_date,
            OccupancySnapshot.target_date <= end_date,
            OccupancySnapshot.is_real == True
        ).order_by(
            OccupancySnapshot.target_date,
            OccupancySnapshot.generated_at.desc()
        ).all()
        
        occupancy_by_date = {}
        for row in occupancy_data:
            if row.target_date not in occupancy_by_date:
                occupancy_by_date[row.target_date] = row.occupancy_pct
        
        for op_date, checkouts in checkout_by_date.items():
            occ_pct = occupancy_by_date.get(op_date)
            if occ_pct and occ_pct > 0:
                rooms_occupied = round(total_rooms * occ_pct / 100)
                if rooms_occupied > 0:
                    turnover_rate = checkouts / rooms_occupied
                    turnover_rate = min(turnover_rate, 1.0)
                    
                    data.append({
                        "date": op_date,
                        "weekday_num": op_date.weekday(),
                        "weekday_pt": WEEKDAYS_PT[op_date.weekday()],
                        "checkouts": checkouts,
                        "rooms_occupied": rooms_occupied,
                        "occ_pct": occ_pct,
                        "turnover_rate": turnover_rate
                    })
        
        return data
    
    def _compute_weekday_stats(
        self,
        weekday_pt: str,
        weekday_num: int,
        data: List[Dict],
        min_samples: int,
        alpha: float
    ) -> Dict:
        """
        Calcula estatísticas para um dia da semana específico.
        """
        n = len(data)
        
        if n < min_samples:
            return {
                "weekday_pt": weekday_pt,
                "weekday_num": weekday_num,
                "rate": DEFAULT_TURNOVER_RATES.get(weekday_pt, 0.35),
                "n": n,
                "std": None,
                "min_rate": None,
                "max_rate": None,
                "fallback_used": True,
                "fallback_reason": f"Amostras insuficientes: {n} < {min_samples}"
            }
        
        rates = [d["turnover_rate"] for d in data]
        
        sorted_data = sorted(data, key=lambda x: x["date"])
        ewma_rate = sorted_data[0]["turnover_rate"]
        for d in sorted_data[1:]:
            ewma_rate = alpha * d["turnover_rate"] + (1 - alpha) * ewma_rate
        
        mean_rate = sum(rates) / n
        variance = sum((r - mean_rate) ** 2 for r in rates) / n
        std = math.sqrt(variance) if variance > 0 else 0
        
        return {
            "weekday_pt": weekday_pt,
            "weekday_num": weekday_num,
            "rate": round(ewma_rate, 4),
            "n": n,
            "std": round(std, 4),
            "min_rate": round(min(rates), 4),
            "max_rate": round(max(rates), 4),
            "fallback_used": False,
            "fallback_reason": None
        }
    
    def get_turnover_rate(
        self,
        weekday_pt: str,
        sector_id: int = None
    ) -> Dict:
        """
        Obtém taxa de turnover para um dia da semana.
        
        Retorna estatística persistida ou fallback se não existir.
        """
        stat = self.db.query(TurnoverRateStats).filter(
            TurnoverRateStats.weekday_pt == weekday_pt,
            TurnoverRateStats.sector_id == sector_id
        ).first()
        
        if stat:
            return {
                "rate": stat.rate,
                "n": stat.n,
                "std": stat.std,
                "fallback_used": stat.fallback_used,
                "fallback_reason": stat.fallback_reason,
                "last_updated_at": stat.last_updated_at.isoformat() if stat.last_updated_at else None
            }
        
        return {
            "rate": DEFAULT_TURNOVER_RATES.get(weekday_pt, 0.35),
            "n": 0,
            "std": None,
            "fallback_used": True,
            "fallback_reason": "Estatística não calculada, usando default",
            "last_updated_at": None
        }
    
    def get_all_turnover_rates(self, sector_id: int = None) -> List[Dict]:
        """
        Obtém todas as taxas de turnover por dia da semana.
        """
        stats = self.db.query(TurnoverRateStats).filter(
            TurnoverRateStats.sector_id == sector_id
        ).order_by(TurnoverRateStats.weekday_num).all()
        
        result = []
        for weekday_num in range(7):
            weekday_pt = WEEKDAYS_PT[weekday_num]
            stat = next((s for s in stats if s.weekday_pt == weekday_pt), None)
            
            if stat:
                result.append({
                    "weekday_pt": weekday_pt,
                    "weekday_num": weekday_num,
                    "rate": stat.rate,
                    "n": stat.n,
                    "std": stat.std,
                    "fallback_used": stat.fallback_used,
                    "fallback_reason": stat.fallback_reason,
                    "last_updated_at": stat.last_updated_at.isoformat() if stat.last_updated_at else None
                })
            else:
                result.append({
                    "weekday_pt": weekday_pt,
                    "weekday_num": weekday_num,
                    "rate": DEFAULT_TURNOVER_RATES.get(weekday_pt, 0.35),
                    "n": 0,
                    "std": None,
                    "fallback_used": True,
                    "fallback_reason": "Estatística não calculada",
                    "last_updated_at": None
                })
        
        return result
    
    def bootstrap_from_defaults(self, sector_id: int = None) -> Dict:
        """
        Inicializa estatísticas com valores default para bootstrap.
        
        Útil quando não há histórico suficiente.
        """
        result = {
            "success": False,
            "created": 0,
            "errors": []
        }
        
        try:
            for weekday_num in range(7):
                weekday_pt = WEEKDAYS_PT[weekday_num]
                
                existing = self.db.query(TurnoverRateStats).filter(
                    TurnoverRateStats.weekday_pt == weekday_pt,
                    TurnoverRateStats.sector_id == sector_id
                ).first()
                
                if not existing:
                    new_stat = TurnoverRateStats(
                        sector_id=sector_id,
                        weekday_pt=weekday_pt,
                        weekday_num=weekday_num,
                        rate=DEFAULT_TURNOVER_RATES.get(weekday_pt, 0.35),
                        n=0,
                        method="BOOTSTRAP",
                        fallback_used=True,
                        fallback_reason="Bootstrap com valores default"
                    )
                    self.db.add(new_stat)
                    result["created"] += 1
            
            self.db.commit()
            result["success"] = True
            
        except Exception as e:
            self.db.rollback()
            result["errors"].append(str(e))
        
        return result
