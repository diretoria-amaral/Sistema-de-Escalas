import re
from datetime import datetime, date, timezone
from typing import Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo
import pdfplumber
from sqlalchemy.orm import Session

from app.models.data_lake import OccupancySnapshot, OccupancyLatest, ReportExtractLog, ExtractStep, LogSeverity
from app.models.report_upload import ReportUpload

PARSER_VERSION = "1.0.4"

BRAZIL_TZ = ZoneInfo("America/Manaus")

MESES_PT = {
    "janeiro": 1, "fevereiro": 2, "março": 3, "marco": 3, "abril": 4,
    "maio": 5, "junho": 6, "julho": 7, "agosto": 8, "setembro": 9,
    "outubro": 10, "novembro": 11, "dezembro": 12
}


class HPParser:
    
    def __init__(self, db: Session):
        self.db = db
    
    def parse(self, upload: ReportUpload) -> Dict:
        result = {
            "success": False,
            "generated_at": None,
            "period_start": None,
            "period_end": None,
            "snapshots_created": 0,
            "skipped": 0,
            "errors": []
        }
        
        try:
            with pdfplumber.open(upload.file_path) as pdf:
                full_text = ""
                for page in pdf.pages:
                    page_text = page.extract_text() or ""
                    full_text += page_text + "\n"
            
            self._log(upload.id, ExtractStep.EXTRACT, LogSeverity.INFO, 
                     "Texto extraído do PDF", {"length": len(full_text)})
            
            generated_at = self._extract_generated_at(full_text)
            if not generated_at:
                self._log(upload.id, ExtractStep.EXTRACT, LogSeverity.ERROR,
                         "Não foi possível extrair data de emissão")
                result["errors"].append("Data de emissão não encontrada")
                return result
            
            result["generated_at"] = generated_at
            as_of_date = generated_at.date()
            
            period_start, period_end = self._extract_period(full_text)
            result["period_start"] = period_start
            result["period_end"] = period_end
            
            self._log(upload.id, ExtractStep.EXTRACT, LogSeverity.INFO,
                     f"Período: {period_start} - {period_end}, Emissão: {generated_at}")
            
            daily_data = self._extract_daily_occupancy(full_text, period_start, period_end)
            
            self._log(upload.id, ExtractStep.NORMALIZE, LogSeverity.INFO,
                     f"Dados diários extraídos: {len(daily_data)} dias")
            
            upload_id = upload.id
            skipped = 0
            for target_date, occupancy_pct in daily_data.items():
                is_real = target_date < as_of_date
                is_forecast = target_date >= as_of_date
                
                existing = self.db.query(OccupancySnapshot).filter(
                    OccupancySnapshot.target_date == target_date,
                    OccupancySnapshot.generated_at == generated_at
                ).first()
                
                if existing:
                    skipped += 1
                    continue
                
                snapshot = OccupancySnapshot(
                    target_date=target_date,
                    generated_at=generated_at,
                    period_start=period_start,
                    period_end=period_end,
                    occupancy_pct=occupancy_pct,
                    is_real=is_real,
                    is_forecast=is_forecast,
                    source_upload_id=upload_id
                )
                self.db.add(snapshot)
                result["snapshots_created"] += 1
                
                self._update_occupancy_latest(target_date, generated_at, occupancy_pct, is_real, upload_id)
            
            result["skipped"] = skipped
            
            if skipped > 0:
                self._log(upload.id, ExtractStep.PERSIST, LogSeverity.WARN,
                         f"Deduplicação: {skipped} snapshots já existentes ignorados",
                         {"skipped": skipped})
            
            self.db.commit()
            
            self._log(upload.id, ExtractStep.PERSIST, LogSeverity.INFO,
                     f"Persistidos {result['snapshots_created']} snapshots",
                     {"snapshots_created": result["snapshots_created"], "skipped": skipped})
            self.db.commit()
            
            result["success"] = True
            
        except Exception as e:
            self._log(upload.id, ExtractStep.EXTRACT, LogSeverity.ERROR,
                     f"Erro no parsing: {str(e)}")
            result["errors"].append(str(e))
            self.db.rollback()
        
        return result
    
    def _extract_generated_at(self, text: str) -> Optional[datetime]:
        """
        Extrai data/hora de emissão do relatório HP.
        Formatos suportados:
        - "Quinta-feira, 21 de dezembro de 2025 às 14:05"
        - "segunda-feira, 2 de dezembro de 2025 14:30"
        - "21 de dezembro de 2025 às 14:05"
        
        IMPORTANTE: O horário no PDF é local do Brasil (America/Sao_Paulo).
        Convertemos para UTC para armazenamento consistente.
        """
        patterns = [
            r"(\w+-feira),?\s+(\d{1,2})\s+de\s+(\w+)\s+de\s+(\d{4})\s+[àa]s?\s*(\d{2}):(\d{2})",
            r"(\w+-feira),?\s+(\d{1,2})\s+de\s+(\w+)\s+de\s+(\d{4})\s+(\d{2}):(\d{2})",
            r"(\d{1,2})\s+de\s+(\w+)\s+de\s+(\d{4})\s+[àa]s?\s*(\d{2}):(\d{2})",
            r"(\d{1,2})\s+de\s+(\w+)\s+de\s+(\d{4})\s+(\d{2}):(\d{2})"
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                groups = match.groups()
                try:
                    if len(groups) == 6:
                        day = int(groups[1])
                        month_name = groups[2].lower()
                        year = int(groups[3])
                        hour = int(groups[4])
                        minute = int(groups[5])
                    else:
                        day = int(groups[0])
                        month_name = groups[1].lower()
                        year = int(groups[2])
                        hour = int(groups[3])
                        minute = int(groups[4])
                    
                    month = MESES_PT.get(month_name)
                    if month:
                        local_dt = datetime(year, month, day, hour, minute, tzinfo=BRAZIL_TZ)
                        utc_dt = local_dt.astimezone(timezone.utc)
                        return utc_dt
                except (ValueError, KeyError):
                    continue
        
        return None
    
    def _extract_period(self, text: str) -> Tuple[Optional[date], Optional[date]]:
        """
        Extrai período do relatório HP.
        Suporta separadores: hífen (-), en dash (–) e em dash (—)
        """
        pattern = r"Per[ií]odo:\s*(\d{2}/\d{2}/\d{4})\s*[-–—]\s*(\d{2}/\d{2}/\d{4})"
        match = re.search(pattern, text, re.IGNORECASE)
        
        if match:
            try:
                start = datetime.strptime(match.group(1), "%d/%m/%Y").date()
                end = datetime.strptime(match.group(2), "%d/%m/%Y").date()
                return start, end
            except ValueError:
                pass
        
        return None, None
    
    def _extract_daily_occupancy(self, text: str, period_start: date = None, period_end: date = None) -> Dict[date, float]:
        """
        Extrai dados de ocupação diária do HP.
        Usa o período do relatório para inferir o ano correto quando não especificado.
        """
        daily_data = {}
        
        patterns = [
            r"(\d{2}/\d{2}/\d{4})\s+[\w\-]+\s+(\d{1,3}[,\.]\d{2})\s*%",
            r"(\d{2}/\d{2}/\d{4})\s+.*?(\d{1,3}[,\.]\d{2})\s*%",
            r"(\d{2}/\d{2})\s+[\w\-]+\s+(\d{1,3}[,\.]\d{2})\s*%"
        ]
        
        context_years = set()
        if period_start:
            context_years.add(period_start.year)
        if period_end:
            context_years.add(period_end.year)
        if not context_years:
            context_years.add(datetime.now().year)
        
        for pattern in patterns:
            matches = re.findall(pattern, text)
            for match in matches:
                try:
                    date_str = match[0]
                    
                    if len(date_str) == 5:
                        day_month = date_str
                        day = int(date_str.split('/')[0])
                        month = int(date_str.split('/')[1])
                        
                        best_year = None
                        for year in context_years:
                            candidate = date(year, month, day)
                            if period_start and period_end:
                                if period_start <= candidate <= period_end:
                                    best_year = year
                                    break
                            elif period_start:
                                diff = abs((candidate - period_start).days)
                                if diff <= 62:
                                    best_year = year
                                    break
                        
                        if not best_year:
                            best_year = max(context_years)
                        
                        date_str = f"{day_month}/{best_year}"
                    
                    target_date = datetime.strptime(date_str, "%d/%m/%Y").date()
                    occupancy = float(match[1].replace(",", "."))
                    
                    if 0 <= occupancy <= 100:
                        daily_data[target_date] = occupancy
                except (ValueError, IndexError):
                    continue
        
        return daily_data
    
    def _update_occupancy_latest(self, target_date: date, generated_at: datetime, 
                                  occupancy_pct: float, is_real: bool, upload_id: int):
        latest = self.db.query(OccupancyLatest).filter(
            OccupancyLatest.target_date == target_date
        ).first()
        
        if not latest:
            latest = OccupancyLatest(target_date=target_date)
            self.db.add(latest)
        
        updated = False
        
        gen_at_aware = generated_at if generated_at.tzinfo else generated_at.replace(tzinfo=timezone.utc)
        
        if is_real:
            current_real_at = latest.latest_real_generated_at
            if current_real_at is None:
                latest.latest_real_generated_at = gen_at_aware
                latest.latest_real_occupancy_pct = occupancy_pct
                updated = True
            else:
                current_aware = current_real_at if current_real_at.tzinfo else current_real_at.replace(tzinfo=timezone.utc)
                if gen_at_aware > current_aware:
                    latest.latest_real_generated_at = gen_at_aware
                    latest.latest_real_occupancy_pct = occupancy_pct
                    updated = True
        else:
            current_forecast_at = latest.latest_forecast_generated_at
            if current_forecast_at is None:
                latest.latest_forecast_generated_at = gen_at_aware
                latest.latest_forecast_occupancy_pct = occupancy_pct
                updated = True
            else:
                current_aware = current_forecast_at if current_forecast_at.tzinfo else current_forecast_at.replace(tzinfo=timezone.utc)
                if gen_at_aware > current_aware:
                    latest.latest_forecast_generated_at = gen_at_aware
                    latest.latest_forecast_occupancy_pct = occupancy_pct
                    updated = True
        
        if updated:
            if latest.latest_real_occupancy_pct is not None:
                latest.occupancy_pct = latest.latest_real_occupancy_pct
                latest.is_real = True
            elif latest.latest_forecast_occupancy_pct is not None:
                latest.occupancy_pct = latest.latest_forecast_occupancy_pct
                latest.is_real = False
            
            latest.source_upload_id = upload_id
    
    def _log(self, upload_id: int, step: ExtractStep, severity: LogSeverity, 
             message: str, payload: dict = None):
        log = ReportExtractLog(
            report_upload_id=upload_id,
            step=step,
            severity=severity,
            message=message,
            payload_json=payload or {}
        )
        self.db.add(log)
