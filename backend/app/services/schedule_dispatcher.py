"""
PROMPT 8: Schedule Generator Dispatcher / Registry

Interface para geradores de escala por setor.
Permite plugar diferentes geradores para diferentes setores
sem alterar a lógica central.

Fluxo:
1. Dispatcher recebe sector_id/sector_code
2. Identifica qual gerador usar para aquele setor
3. Executa o gerador com os parâmetros corretos
4. Retorna resultado padronizado
"""
from typing import Dict, Any, Optional, Protocol
from datetime import date
from sqlalchemy.orm import Session

from app.models.sector import Sector
from app.models.rules import LaborRules, SectorOperationalRules


class SectorScheduleGenerator(Protocol):
    """Interface que todos os geradores de setor devem implementar."""
    
    def generate_schedule(
        self,
        db: Session,
        sector_id: int,
        week_start: date,
        forecast_run_id: Optional[int] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Gera escala para o setor."""
        ...
    
    def validate_schedule(
        self,
        db: Session,
        schedule_plan_id: int
    ) -> Dict[str, Any]:
        """Valida escala gerada."""
        ...


class ScheduleDispatcher:
    """
    Dispatcher central para geradores de escala por setor.
    
    Uso:
        dispatcher = ScheduleDispatcher()
        result = dispatcher.generate_schedule(db, sector_id, week_start, ...)
    """
    
    SECTOR_CODE_GOVERNANCE = "governanca"
    SECTOR_CODE_RECEPTION = "recepcao"
    SECTOR_CODE_MAINTENANCE = "manutencao"
    SECTOR_CODE_FB = "ab"
    
    def __init__(self):
        self._generators: Dict[str, SectorScheduleGenerator] = {}
        self._register_default_generators()
    
    def _register_default_generators(self):
        """Registra geradores padrão disponíveis."""
        pass
    
    def register_generator(self, sector_code: str, generator: SectorScheduleGenerator):
        """Registra um gerador para um setor específico."""
        self._generators[sector_code.lower()] = generator
    
    def get_sector_code(self, db: Session, sector_id: int) -> Optional[str]:
        """Obtém código do setor pelo ID."""
        sector = db.query(Sector).filter(Sector.id == sector_id).first()
        if not sector:
            return None
        return self._normalize_sector_code(sector.nome)
    
    def _normalize_sector_code(self, sector_name: str) -> str:
        """Normaliza nome do setor para código padronizado."""
        name_lower = sector_name.lower().strip()
        
        mappings = {
            "governança": self.SECTOR_CODE_GOVERNANCE,
            "governanca": self.SECTOR_CODE_GOVERNANCE,
            "housekeeping": self.SECTOR_CODE_GOVERNANCE,
            "recepção": self.SECTOR_CODE_RECEPTION,
            "recepcao": self.SECTOR_CODE_RECEPTION,
            "reception": self.SECTOR_CODE_RECEPTION,
            "front desk": self.SECTOR_CODE_RECEPTION,
            "manutenção": self.SECTOR_CODE_MAINTENANCE,
            "manutencao": self.SECTOR_CODE_MAINTENANCE,
            "maintenance": self.SECTOR_CODE_MAINTENANCE,
            "a&b": self.SECTOR_CODE_FB,
            "alimentos e bebidas": self.SECTOR_CODE_FB,
            "f&b": self.SECTOR_CODE_FB,
        }
        
        return mappings.get(name_lower, name_lower)
    
    def get_labor_rules(self, db: Session) -> Optional[LaborRules]:
        """Obtém regras trabalhistas globais ativas."""
        return db.query(LaborRules).filter(
            LaborRules.is_active == True
        ).first()
    
    def get_sector_operational_rules(
        self, 
        db: Session, 
        sector_id: int
    ) -> Optional[SectorOperationalRules]:
        """Obtém regras operacionais do setor."""
        return db.query(SectorOperationalRules).filter(
            SectorOperationalRules.sector_id == sector_id,
            SectorOperationalRules.is_active == True
        ).first()
    
    def generate_schedule(
        self,
        db: Session,
        sector_id: int,
        week_start: date,
        forecast_run_id: Optional[int] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Gera escala para um setor usando o gerador apropriado.
        
        Args:
            db: Sessão do banco de dados
            sector_id: ID do setor
            week_start: Data de início da semana (segunda-feira)
            forecast_run_id: ID do forecast run (opcional)
            **kwargs: Parâmetros adicionais específicos do setor
        
        Returns:
            Dict com resultado da geração:
            - success: bool
            - schedule_plan_id: int (se sucesso)
            - message: str
            - warnings: List[str]
            - sector_code: str
        """
        sector_code = self.get_sector_code(db, sector_id)
        if not sector_code:
            return {
                "success": False,
                "message": f"Setor com ID {sector_id} não encontrado",
                "sector_code": None
            }
        
        labor_rules = self.get_labor_rules(db)
        operational_rules = self.get_sector_operational_rules(db, sector_id)
        
        generator = self._generators.get(sector_code)
        if not generator:
            return {
                "success": False,
                "message": f"Gerador não disponível para setor '{sector_code}'",
                "sector_code": sector_code,
                "available_generators": list(self._generators.keys())
            }
        
        return generator.generate_schedule(
            db=db,
            sector_id=sector_id,
            week_start=week_start,
            forecast_run_id=forecast_run_id,
            labor_rules=labor_rules,
            operational_rules=operational_rules,
            **kwargs
        )
    
    def validate_schedule(
        self,
        db: Session,
        sector_id: int,
        schedule_plan_id: int
    ) -> Dict[str, Any]:
        """Valida uma escala existente."""
        sector_code = self.get_sector_code(db, sector_id)
        if not sector_code:
            return {
                "success": False,
                "message": f"Setor com ID {sector_id} não encontrado"
            }
        
        generator = self._generators.get(sector_code)
        if not generator:
            return {
                "success": False,
                "message": f"Validador não disponível para setor '{sector_code}'"
            }
        
        return generator.validate_schedule(db, schedule_plan_id)
    
    def list_available_sectors(self) -> Dict[str, bool]:
        """Lista setores com geradores disponíveis."""
        all_sectors = [
            self.SECTOR_CODE_GOVERNANCE,
            self.SECTOR_CODE_RECEPTION,
            self.SECTOR_CODE_MAINTENANCE,
            self.SECTOR_CODE_FB
        ]
        return {
            sector: sector in self._generators
            for sector in all_sectors
        }


schedule_dispatcher = ScheduleDispatcher()
