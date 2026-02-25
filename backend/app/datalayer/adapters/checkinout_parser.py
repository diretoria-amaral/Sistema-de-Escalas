"""
CheckInOutParser - Parser universal para dados de CHECK-IN e CHECK-OUT

Suporta formatos:
- CSV (.csv)
- Excel (.xlsx, .xls)
- PDF (.pdf)

Aplica normalização obrigatória:
- Datas em ISO format (YYYY-MM-DD)
- Cálculo de semana ISO (1-52)
- Dia da semana em português
- Classificação CHECK-IN / CHECK-OUT

NUNCA inventa dados para campos ausentes.
"""

import re
import io
from datetime import datetime, date, time, timedelta
from typing import Dict, List, Optional, Tuple, Any
import pandas as pd
import pdfplumber
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.data_lake import (
    FrontdeskEvent, FrontdeskEventsHourlyAgg, EventType,
    ReportExtractLog, ExtractStep, LogSeverity
)
from app.models.report_upload import ReportUpload

PARSER_VERSION = "2.0.0"

WEEKDAYS_PT = ["SEGUNDA-FEIRA", "TERÇA-FEIRA", "QUARTA-FEIRA", "QUINTA-FEIRA", 
               "SEXTA-FEIRA", "SÁBADO", "DOMINGO"]

WEEKDAYS_SHORT_PT = ["SEG", "TER", "QUA", "QUI", "SEX", "SAB", "DOM"]

DATE_COLUMN_VARIATIONS = [
    "data", "date", "dt", "data_evento", "event_date", "dia",
    "data_checkin", "data_checkout", "data_entrada", "data_saida",
    "checkin_date", "checkout_date", "arrival_date", "departure_date",
    "entrada", "saida", "saída"
]

TIME_COLUMN_VARIATIONS = [
    "hora", "time", "horario", "hr", "hour", "hora_evento",
    "hora_checkin", "hora_checkout", "arrival_time", "departure_time"
]

ROOM_COLUMN_VARIATIONS = [
    "uh", "quarto", "room", "apto", "apartamento", "unit", 
    "room_number", "numero_quarto", "apt"
]

ROOM_TYPE_VARIATIONS = [
    "tipo", "type", "room_type", "tipo_quarto", "categoria",
    "category", "tipo_uh"
]

QUANTITY_VARIATIONS = [
    "quantidade", "qty", "qtd", "count", "total", "volume",
    "num_guests", "pax", "hospedes"
]

EVENT_TYPE_VARIATIONS = [
    "tipo_evento", "event_type", "evento", "event", "tipo_movimentacao"
]

CHECKIN_KEYWORDS = ["entrada", "checkin", "check-in", "check in", "in", "chegada", "arrival"]
CHECKOUT_KEYWORDS = ["saida", "saída", "checkout", "check-out", "check out", "out", "partida", "departure"]


class CheckInOutParser:
    """
    Parser universal para dados de CHECK-IN e CHECK-OUT.
    Suporta CSV, Excel e PDF.
    """
    
    def __init__(self, db: Session):
        self.db = db
        self.errors: List[Dict] = []
        self.warnings: List[Dict] = []
    
    def parse(self, upload: ReportUpload, force_event_type: Optional[EventType] = None) -> Dict:
        """
        Processa arquivo de CHECK-IN/CHECK-OUT.
        
        Args:
            upload: ReportUpload com file_path
            force_event_type: Se definido, força o tipo de evento (CHECKIN ou CHECKOUT)
        
        Returns:
            Dict com resultado do parsing
        """
        self.errors = []
        self.warnings = []
        
        result = {
            "success": False,
            "events_created": 0,
            "aggregations_updated": 0,
            "date_range": {"start": None, "end": None},
            "weeks_covered": [],
            "errors": [],
            "warnings": [],
            "normalization_applied": True,
            "parser_version": PARSER_VERSION
        }
        
        try:
            file_ext = upload.file_path.split(".")[-1].lower()
            
            if file_ext == "pdf":
                df, detected_type = self._parse_pdf(upload)
            elif file_ext in ["csv"]:
                df, detected_type = self._parse_csv(upload)
            elif file_ext in ["xlsx", "xls"]:
                df, detected_type = self._parse_excel(upload)
            else:
                self._log_error(upload.id, f"Formato não suportado: {file_ext}")
                result["errors"] = [e["message"] for e in self.errors]
                return result
            
            if df is None or df.empty:
                self._log_error(upload.id, "Nenhum dado extraído do arquivo")
                result["errors"] = [e["message"] for e in self.errors]
                return result
            
            self._log(upload.id, ExtractStep.EXTRACT, LogSeverity.INFO,
                     f"Dados extraídos: {len(df)} linhas", {"columns": list(df.columns)})
            
            event_type = force_event_type or detected_type
            if event_type is None:
                self._log_error(upload.id, "Tipo de evento não identificado (CHECKIN ou CHECKOUT)")
                result["errors"] = [e["message"] for e in self.errors]
                return result
            
            normalized_df = self._normalize(df, upload.id)
            
            if normalized_df is None or normalized_df.empty:
                self._log_error(upload.id, "Falha na normalização - nenhum registro válido")
                result["errors"] = [e["message"] for e in self.errors]
                return result
            
            self._log(upload.id, ExtractStep.NORMALIZE, LogSeverity.INFO,
                     f"Registros normalizados: {len(normalized_df)}")
            
            events = self._create_events(normalized_df, event_type, upload.id)
            
            for event in events:
                self.db.add(event)
                result["events_created"] += 1
            
            self.db.flush()
            
            agg_count = self._update_hourly_aggregations(events, event_type)
            result["aggregations_updated"] = agg_count
            
            if len(normalized_df) > 0:
                dates = normalized_df["date_iso"].dropna()
                if len(dates) > 0:
                    result["date_range"]["start"] = dates.min()
                    result["date_range"]["end"] = dates.max()
                
                weeks = normalized_df["iso_week"].dropna().unique().tolist()
                result["weeks_covered"] = sorted([int(w) for w in weeks])
            
            self.db.commit()
            
            self._log(upload.id, ExtractStep.PERSIST, LogSeverity.INFO,
                     f"Persistidos {result['events_created']} eventos, {agg_count} agregações")
            
            result["success"] = True
            result["errors"] = [e["message"] for e in self.errors]
            result["warnings"] = [w["message"] for w in self.warnings]
            
        except Exception as e:
            self._log(upload.id, ExtractStep.EXTRACT, LogSeverity.ERROR,
                     f"Erro no parsing: {str(e)}")
            result["errors"].append(str(e))
            self.db.rollback()
        
        return result
    
    def _parse_csv(self, upload: ReportUpload) -> Tuple[Optional[pd.DataFrame], Optional[EventType]]:
        """Parse arquivo CSV."""
        try:
            encodings = ['utf-8', 'latin-1', 'cp1252', 'iso-8859-1']
            separators = [',', ';', '\t', '|']
            
            df = None
            for encoding in encodings:
                for sep in separators:
                    try:
                        df = pd.read_csv(upload.file_path, encoding=encoding, sep=sep)
                        if len(df.columns) > 1:
                            break
                    except:
                        continue
                if df is not None and len(df.columns) > 1:
                    break
            
            if df is None:
                return None, None
            
            detected_type = self._detect_event_type_from_df(df, upload.original_filename)
            
            return df, detected_type
            
        except Exception as e:
            self._log_error(upload.id, f"Erro ao ler CSV: {str(e)}")
            return None, None
    
    def _parse_excel(self, upload: ReportUpload) -> Tuple[Optional[pd.DataFrame], Optional[EventType]]:
        """Parse arquivo Excel (.xlsx and .xls)."""
        try:
            file_ext = upload.file_path.split(".")[-1].lower() if upload.file_path else ""
            engine = 'xlrd' if file_ext == 'xls' else 'openpyxl'
            
            df = pd.read_excel(upload.file_path, engine=engine)
            
            if df.empty:
                xlsx = pd.ExcelFile(upload.file_path, engine=engine)
                for sheet in xlsx.sheet_names:
                    df = pd.read_excel(xlsx, sheet_name=sheet)
                    if not df.empty:
                        break
            
            detected_type = self._detect_event_type_from_df(df, upload.original_filename)
            
            return df, detected_type
            
        except Exception as e:
            self._log_error(upload.id, f"Erro ao ler Excel: {str(e)}")
            return None, None
    
    def _parse_pdf(self, upload: ReportUpload) -> Tuple[Optional[pd.DataFrame], Optional[EventType]]:
        """Parse arquivo PDF extraindo tabelas."""
        try:
            all_data = []
            detected_type = None
            
            with pdfplumber.open(upload.file_path) as pdf:
                for page_num, page in enumerate(pdf.pages):
                    page_text = page.extract_text() or ""
                    
                    if detected_type is None:
                        detected_type = self._detect_event_type_from_text(page_text, upload.original_filename)
                    
                    tables = page.extract_tables()
                    for table in tables:
                        if table and len(table) > 1:
                            header = [str(c).lower().strip() if c else f"col_{i}" 
                                     for i, c in enumerate(table[0])]
                            for row in table[1:]:
                                if row and any(cell for cell in row):
                                    row_dict = {}
                                    for i, val in enumerate(row):
                                        col_name = header[i] if i < len(header) else f"col_{i}"
                                        row_dict[col_name] = val
                                    all_data.append(row_dict)
            
            if not all_data:
                return None, detected_type
            
            df = pd.DataFrame(all_data)
            return df, detected_type
            
        except Exception as e:
            self._log_error(upload.id, f"Erro ao ler PDF: {str(e)}")
            return None, None
    
    def _detect_event_type_from_df(self, df: pd.DataFrame, filename: str) -> Optional[EventType]:
        """Detecta tipo de evento pelos dados do DataFrame e nome do arquivo."""
        columns_str = " ".join([str(c).lower() for c in df.columns])
        
        has_checkin = any(kw in columns_str for kw in CHECKIN_KEYWORDS)
        has_checkout = any(kw in columns_str for kw in CHECKOUT_KEYWORDS)
        
        if has_checkin and not has_checkout:
            return EventType.CHECKIN
        if has_checkout and not has_checkin:
            return EventType.CHECKOUT
        
        event_col = self._find_column(df, EVENT_TYPE_VARIATIONS)
        if event_col:
            values = df[event_col].astype(str).str.lower().unique()
            checkin_count = sum(1 for v in values if any(kw in v for kw in CHECKIN_KEYWORDS))
            checkout_count = sum(1 for v in values if any(kw in v for kw in CHECKOUT_KEYWORDS))
            
            if checkin_count > checkout_count:
                return EventType.CHECKIN
            elif checkout_count > checkin_count:
                return EventType.CHECKOUT
        
        return self._detect_event_type_from_filename(filename)
    
    def _detect_event_type_from_text(self, text: str, filename: str) -> Optional[EventType]:
        """Detecta tipo de evento pelo texto do PDF."""
        text_lower = text.lower()
        
        checkin_matches = sum(1 for kw in CHECKIN_KEYWORDS if kw in text_lower)
        checkout_matches = sum(1 for kw in CHECKOUT_KEYWORDS if kw in text_lower)
        
        if checkin_matches > checkout_matches:
            return EventType.CHECKIN
        elif checkout_matches > checkin_matches:
            return EventType.CHECKOUT
        
        return self._detect_event_type_from_filename(filename)
    
    def _detect_event_type_from_filename(self, filename: str) -> Optional[EventType]:
        """Detecta tipo de evento pelo nome do arquivo."""
        filename_lower = filename.lower()
        
        for kw in CHECKIN_KEYWORDS:
            if kw in filename_lower:
                return EventType.CHECKIN
        
        for kw in CHECKOUT_KEYWORDS:
            if kw in filename_lower:
                return EventType.CHECKOUT
        
        return None
    
    def _find_column(self, df: pd.DataFrame, variations: List[str]) -> Optional[str]:
        """Encontra coluna pelo nome, aceitando variações."""
        columns_lower = {str(c).lower().strip(): c for c in df.columns}
        
        for var in variations:
            if var.lower() in columns_lower:
                return columns_lower[var.lower()]
        
        for col_lower, col_original in columns_lower.items():
            for var in variations:
                if var.lower() in col_lower:
                    return col_original
        
        return None
    
    def _normalize(self, df: pd.DataFrame, upload_id: int) -> Optional[pd.DataFrame]:
        """
        Aplica normalização OBRIGATÓRIA:
        - Converte datas para ISO (YYYY-MM-DD)
        - Calcula semana ISO (1-52)
        - Identifica dia da semana
        """
        normalized_rows = []
        
        date_col = self._find_column(df, DATE_COLUMN_VARIATIONS)
        time_col = self._find_column(df, TIME_COLUMN_VARIATIONS)
        room_col = self._find_column(df, ROOM_COLUMN_VARIATIONS)
        room_type_col = self._find_column(df, ROOM_TYPE_VARIATIONS)
        qty_col = self._find_column(df, QUANTITY_VARIATIONS)
        
        if not date_col:
            self._log_error(upload_id, "Coluna de DATA não encontrada. Variações aceitas: " + 
                          ", ".join(DATE_COLUMN_VARIATIONS[:5]))
            return None
        
        self._log(upload_id, ExtractStep.NORMALIZE, LogSeverity.INFO,
                 f"Colunas mapeadas: date={date_col}, time={time_col}, room={room_col}")
        
        for idx, row in df.iterrows():
            try:
                date_val = row[date_col]
                parsed_date = self._parse_date(date_val)
                
                if parsed_date is None:
                    self._log_warning(upload_id, f"Linha {idx}: Data inválida '{date_val}' - registro ignorado")
                    continue
                
                parsed_time = None
                if time_col:
                    time_val = row.get(time_col)
                    parsed_time = self._parse_time(time_val)
                
                iso_week = parsed_date.isocalendar()[1]
                iso_year = parsed_date.isocalendar()[0]
                weekday_idx = parsed_date.weekday()
                weekday_pt = WEEKDAYS_PT[weekday_idx]
                weekday_short = WEEKDAYS_SHORT_PT[weekday_idx]
                
                normalized_row = {
                    "date_iso": parsed_date.isoformat(),
                    "date_obj": parsed_date,
                    "time_obj": parsed_time,
                    "iso_week": iso_week,
                    "iso_year": iso_year,
                    "weekday_idx": weekday_idx,
                    "weekday_pt": weekday_pt,
                    "weekday_short": weekday_short,
                    "room": str(row.get(room_col, "")).strip() if room_col else None,
                    "room_type": str(row.get(room_type_col, "")).strip() if room_type_col else None,
                    "quantity": self._parse_quantity(row.get(qty_col)) if qty_col else 1
                }
                
                normalized_rows.append(normalized_row)
                
            except Exception as e:
                self._log_warning(upload_id, f"Linha {idx}: Erro na normalização - {str(e)}")
                continue
        
        if not normalized_rows:
            return None
        
        return pd.DataFrame(normalized_rows)
    
    def _parse_date(self, value: Any) -> Optional[date]:
        """Parse de data em múltiplos formatos."""
        if value is None or (isinstance(value, str) and not value.strip()):
            return None
        
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        
        if isinstance(value, pd.Timestamp):
            return value.date()
        
        str_val = str(value).strip()
        
        date_formats = [
            "%Y-%m-%d",      # ISO
            "%d/%m/%Y",      # BR
            "%d-%m-%Y",      # BR alt
            "%Y/%m/%d",      # ISO alt
            "%d.%m.%Y",      # EU
            "%m/%d/%Y",      # US
            "%d/%m/%y",      # BR short year
            "%Y%m%d",        # Compact
        ]
        
        for fmt in date_formats:
            try:
                return datetime.strptime(str_val, fmt).date()
            except ValueError:
                continue
        
        try:
            return pd.to_datetime(str_val, dayfirst=True).date()
        except:
            pass
        
        return None
    
    def _parse_time(self, value: Any) -> Optional[time]:
        """Parse de horário."""
        if value is None or (isinstance(value, str) and not value.strip()):
            return None
        
        if isinstance(value, time):
            return value
        if isinstance(value, datetime):
            return value.time()
        
        str_val = str(value).strip()
        
        time_formats = [
            "%H:%M:%S",
            "%H:%M",
            "%H%M",
            "%I:%M %p",
            "%I:%M:%S %p"
        ]
        
        for fmt in time_formats:
            try:
                return datetime.strptime(str_val, fmt).time()
            except ValueError:
                continue
        
        return None
    
    def _parse_quantity(self, value: Any) -> int:
        """Parse de quantidade."""
        if value is None:
            return 1
        try:
            return int(float(value))
        except:
            return 1
    
    def _create_events(self, df: pd.DataFrame, event_type: EventType, 
                       upload_id: int) -> List[FrontdeskEvent]:
        """Cria eventos FrontdeskEvent a partir do DataFrame normalizado."""
        events = []
        
        for _, row in df.iterrows():
            qty = row.get("quantity", 1) or 1
            
            for _ in range(qty):
                event = FrontdeskEvent(
                    event_type=event_type,
                    anchor_date=row["date_obj"],
                    event_time=row.get("time_obj"),
                    uh=row.get("room") if row.get("room") and row.get("room") != "None" else None,
                    room_type=row.get("room_type") if row.get("room_type") and row.get("room_type") != "None" else None,
                    source_upload_id=upload_id
                )
                events.append(event)
        
        return events
    
    def _update_hourly_aggregations(self, events: List[FrontdeskEvent], 
                                     event_type: EventType) -> int:
        """Atualiza agregações horárias."""
        agg_counts = {}
        
        for event in events:
            anchor = event.anchor_date
            event_time = event.event_time
            
            if anchor is None:
                continue
            
            hour = event_time.hour if event_time else 12
            
            weekday_idx = anchor.weekday()
            weekday_pt = WEEKDAYS_PT[weekday_idx]
            
            key = (anchor, weekday_pt, hour, event_type)
            agg_counts[key] = agg_counts.get(key, 0) + 1
        
        updated = 0
        for (op_date, weekday_pt, hour_timeline, evt_type), count in agg_counts.items():
            existing = self.db.query(FrontdeskEventsHourlyAgg).filter(
                FrontdeskEventsHourlyAgg.op_date == op_date,
                FrontdeskEventsHourlyAgg.hour_timeline == hour_timeline,
                FrontdeskEventsHourlyAgg.event_type == evt_type
            ).first()
            
            if existing:
                existing.count_events += count
                existing.weekday_pt = weekday_pt
            else:
                agg = FrontdeskEventsHourlyAgg(
                    op_date=op_date,
                    weekday_pt=weekday_pt,
                    hour_timeline=hour_timeline,
                    event_type=evt_type,
                    count_events=count,
                    source_window="checkinout_parser"
                )
                self.db.add(agg)
            
            updated += 1
        
        return updated
    
    def _log(self, upload_id: int, step: ExtractStep, severity: LogSeverity,
             message: str, payload: dict = None):
        """Registra log no banco."""
        log = ReportExtractLog(
            report_upload_id=upload_id,
            step=step,
            severity=severity,
            message=message,
            payload_json=payload or {}
        )
        self.db.add(log)
    
    def _log_error(self, upload_id: int, message: str, payload: dict = None):
        """Registra erro."""
        self.errors.append({"message": message, "payload": payload})
        self._log(upload_id, ExtractStep.EXTRACT, LogSeverity.ERROR, message, payload)
    
    def _log_warning(self, upload_id: int, message: str, payload: dict = None):
        """Registra aviso."""
        self.warnings.append({"message": message, "payload": payload})
        self._log(upload_id, ExtractStep.NORMALIZE, LogSeverity.WARN, message, payload)


def get_iso_week_info(d: date) -> Dict:
    """
    Retorna informações ISO da semana para uma data.
    
    Returns:
        Dict com iso_week, iso_year, weekday_idx, weekday_pt
    """
    iso_cal = d.isocalendar()
    weekday_idx = d.weekday()
    
    return {
        "iso_week": iso_cal[1],
        "iso_year": iso_cal[0],
        "weekday_idx": weekday_idx,
        "weekday_pt": WEEKDAYS_PT[weekday_idx],
        "weekday_short": WEEKDAYS_SHORT_PT[weekday_idx]
    }
