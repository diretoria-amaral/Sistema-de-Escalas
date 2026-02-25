import re
from datetime import datetime, date, time, timedelta
from typing import Dict, List, Optional, Tuple
import pdfplumber
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.data_lake import (
    FrontdeskEvent, FrontdeskEventsHourlyAgg, EventType,
    ReportExtractLog, ExtractStep, LogSeverity
)
from app.models.report_upload import ReportUpload

PARSER_VERSION = "1.0.0"

WEEKDAYS_PT = ["SEGUNDA-FEIRA", "TERÇA-FEIRA", "QUARTA-FEIRA", "QUINTA-FEIRA", 
               "SEXTA-FEIRA", "SÁBADO", "DOMINGO"]


class FrontdeskParser:
    
    def __init__(self, db: Session):
        self.db = db
    
    def parse_checkin(self, upload: ReportUpload) -> Dict:
        return self._parse(upload, EventType.CHECKIN)
    
    def parse_checkout(self, upload: ReportUpload) -> Dict:
        return self._parse(upload, EventType.CHECKOUT)
    
    def _parse(self, upload: ReportUpload, event_type: EventType) -> Dict:
        result = {
            "success": False,
            "anchor_date": None,
            "events_created": 0,
            "aggregations_updated": 0,
            "errors": []
        }
        
        try:
            with pdfplumber.open(upload.file_path) as pdf:
                full_text = ""
                for page in pdf.pages:
                    page_text = page.extract_text() or ""
                    full_text += page_text + "\n"
            
            self._log(upload.id, ExtractStep.EXTRACT, LogSeverity.INFO,
                     f"Texto extraído do PDF ({event_type.value})", {"length": len(full_text)})
            
            anchor_date = self._extract_anchor_date(full_text, event_type)
            if not anchor_date:
                self._log(upload.id, ExtractStep.EXTRACT, LogSeverity.ERROR,
                         f"Não foi possível extrair data âncora ({event_type.value})")
                result["errors"].append("Data âncora não encontrada")
                return result
            
            result["anchor_date"] = anchor_date
            
            events = self._extract_events(full_text, event_type, anchor_date, upload.id)
            
            self._log(upload.id, ExtractStep.NORMALIZE, LogSeverity.INFO,
                     f"Eventos extraídos: {len(events)}")
            
            for event in events:
                self.db.add(event)
                result["events_created"] += 1
            
            self.db.flush()
            
            agg_count = self._update_hourly_aggregations(events, event_type)
            result["aggregations_updated"] = agg_count
            
            self.db.commit()
            
            self._log(upload.id, ExtractStep.PERSIST, LogSeverity.INFO,
                     f"Persistidos {result['events_created']} eventos, {agg_count} agregações")
            
            result["success"] = True
            
        except Exception as e:
            self._log(upload.id, ExtractStep.EXTRACT, LogSeverity.ERROR,
                     f"Erro no parsing: {str(e)}")
            result["errors"].append(str(e))
            self.db.rollback()
        
        return result
    
    def _extract_anchor_date(self, text: str, event_type: EventType) -> Optional[date]:
        if event_type == EventType.CHECKIN:
            pattern = r"Entrada\s+(\d{2}/\d{2}/\d{4})"
        else:
            pattern = r"Sa[ií]da\s+(\d{2}/\d{2}/\d{4})"
        
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            try:
                return datetime.strptime(match.group(1), "%d/%m/%Y").date()
            except ValueError:
                pass
        
        return None
    
    def _extract_events(self, text: str, event_type: EventType, 
                        anchor_date: date, upload_id: int) -> List[FrontdeskEvent]:
        events = []
        
        pattern = r'^(\d{3})\s+(\S+)\s+(\d{2}/\d{2}/\d{4})\s+(\d{2}:\d{2})\s+(\d{2}:\d{2})'
        
        lines = text.split('\n')
        for line in lines:
            match = re.match(pattern, line.strip())
            if match:
                try:
                    uh = match.group(1)
                    room_type = match.group(2)
                    other_date_str = match.group(3)
                    time_a_str = match.group(4)
                    time_b_str = match.group(5)
                    
                    other_date = datetime.strptime(other_date_str, "%d/%m/%Y").date()
                    time_a = datetime.strptime(time_a_str, "%H:%M").time()
                    time_b = datetime.strptime(time_b_str, "%H:%M").time()
                    
                    event_time = time_b
                    
                    event = FrontdeskEvent(
                        event_type=event_type,
                        anchor_date=anchor_date,
                        event_time=event_time,
                        uh=uh,
                        room_type=room_type,
                        other_date=other_date,
                        time_a=time_a,
                        time_b=time_b,
                        source_upload_id=upload_id
                    )
                    events.append(event)
                except (ValueError, IndexError):
                    continue
        
        return events
    
    def _normalize_to_op_date_and_timeline(self, event_type: EventType, 
                                            anchor_date: date, 
                                            event_time: time) -> Tuple[date, int, str]:
        """
        Normaliza evento para dia operacional e hour_timeline.
        
        CHECKOUT: janela 00–12 do próprio dia. hour_timeline = 0..11 (eventos após 12h são tardios)
        CHECKIN: janela operacional 14:00 do dia D até 12:00 do dia D+1:
            - 14:00+ => op_date = anchor_date, hour_timeline = 14..23
            - 00:00-11:59 => op_date = anchor_date - 1, hour_timeline = hour + 24 (24..35)
            - 12:00-13:59 => early_checkin, op_date = anchor_date, hour_timeline = 12..13
        
        Returns: (op_date, hour_timeline, flag)
        """
        hour = event_time.hour
        flag = "NORMAL"
        
        if event_type == EventType.CHECKOUT:
            op_date = anchor_date
            if hour < 12:
                hour_timeline = hour
            else:
                hour_timeline = hour
                flag = "LATE_CHECKOUT"
            return op_date, hour_timeline, flag
        
        else:
            if hour >= 14:
                op_date = anchor_date
                hour_timeline = hour
            elif hour < 12:
                op_date = anchor_date - timedelta(days=1)
                hour_timeline = hour + 24
            else:
                op_date = anchor_date
                hour_timeline = hour
                flag = "EARLY_CHECKIN"
            return op_date, hour_timeline, flag
    
    def _update_hourly_aggregations(self, events: List[FrontdeskEvent], 
                                     event_type: EventType) -> int:
        agg_counts = {}
        
        for event in events:
            event_time = event.event_time
            anchor = event.anchor_date
            if event_time is None or anchor is None:
                continue
            
            op_date, hour_timeline, flag = self._normalize_to_op_date_and_timeline(
                event_type, anchor, event_time
            )
            
            weekday_idx = op_date.weekday()
            weekday_pt = WEEKDAYS_PT[weekday_idx]
            
            key = (op_date, weekday_pt, hour_timeline, event_type)
            agg_counts[key] = agg_counts.get(key, 0) + 1
        
        updated = 0
        for (op_date, weekday_pt, hour_timeline, evt_type), count in agg_counts.items():
            existing = self.db.query(FrontdeskEventsHourlyAgg).filter(
                FrontdeskEventsHourlyAgg.op_date == op_date,
                FrontdeskEventsHourlyAgg.hour_timeline == hour_timeline,
                FrontdeskEventsHourlyAgg.event_type == evt_type
            ).first()
            
            if existing:
                existing.count_events = count
                existing.weekday_pt = weekday_pt
            else:
                agg = FrontdeskEventsHourlyAgg(
                    op_date=op_date,
                    weekday_pt=weekday_pt,
                    hour_timeline=hour_timeline,
                    event_type=evt_type,
                    count_events=count,
                    source_window="auto_agg"
                )
                self.db.add(agg)
            
            updated += 1
        
        return updated
    
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
