import os
import re
from typing import Dict, List, Tuple, Optional, Any
from datetime import datetime, date
import pandas as pd
import pdfplumber
from io import BytesIO


class ReportProcessor:
    
    KNOWN_PATTERNS = {
        "ocupacao_diaria": {
            "keywords": ["ocupação", "occupancy", "taxa", "quartos ocupados", "rooms occupied"],
            "headers": ["data", "date", "ocupação", "occupancy", "quartos", "rooms"],
            "indicators": ["occupancy_rate", "rooms_occupied", "rooms_available"],
            "sectors": ["governanca", "recepcao"]
        },
        "previsao_chegadas": {
            "keywords": ["chegadas", "arrivals", "check-in", "entradas", "previsão"],
            "headers": ["data", "chegadas", "arrivals", "hóspedes", "guests"],
            "indicators": ["arrivals", "departures", "stayovers"],
            "sectors": ["governanca", "recepcao"]
        },
        "relatorio_governanca": {
            "keywords": ["governança", "housekeeping", "limpeza", "camareira", "uhd"],
            "headers": ["quarto", "room", "status", "camareira", "tempo"],
            "indicators": ["rooms_cleaned", "cleaning_time", "employees"],
            "sectors": ["governanca"]
        },
        "receita_diaria": {
            "keywords": ["receita", "revenue", "faturamento", "adr", "revpar"],
            "headers": ["data", "receita", "revenue", "adr", "revpar"],
            "indicators": ["revenue", "adr", "revpar"],
            "sectors": ["recepcao", "financeiro"]
        },
        "eventos": {
            "keywords": ["evento", "event", "grupo", "group", "banquete", "conferência"],
            "headers": ["data", "evento", "participantes", "sala"],
            "indicators": ["events", "participants", "rooms_blocked"],
            "sectors": ["ab", "recepcao", "governanca"]
        }
    }
    
    def __init__(self):
        self.upload_dir = "uploads/reports"
        os.makedirs(self.upload_dir, exist_ok=True)
    
    def detect_report_type(self, content: str, filename: str) -> Tuple[str, int, List[str], List[str]]:
        content_lower = content.lower()
        filename_lower = filename.lower()
        
        best_match = None
        best_score = 0
        best_indicators = []
        best_sectors = []
        
        for report_type, patterns in self.KNOWN_PATTERNS.items():
            score = 0
            
            for keyword in patterns["keywords"]:
                if keyword in content_lower or keyword in filename_lower:
                    score += 10
            
            for header in patterns["headers"]:
                if header in content_lower:
                    score += 5
            
            if score > best_score:
                best_score = score
                best_match = report_type
                best_indicators = patterns["indicators"]
                best_sectors = patterns["sectors"]
        
        confidence = min(100, best_score)
        
        return best_match or "desconhecido", confidence, best_indicators, best_sectors
    
    def extract_text_from_pdf(self, file_content: bytes) -> str:
        text_content = []
        try:
            with pdfplumber.open(BytesIO(file_content)) as pdf:
                for page in pdf.pages:
                    text = page.extract_text()
                    if text:
                        text_content.append(text)
        except Exception as e:
            text_content.append(f"Error extracting PDF: {str(e)}")
        
        return "\n".join(text_content)
    
    def extract_tables_from_pdf(self, file_content: bytes) -> List[pd.DataFrame]:
        tables = []
        try:
            with pdfplumber.open(BytesIO(file_content)) as pdf:
                for page in pdf.pages:
                    page_tables = page.extract_tables()
                    for table in page_tables:
                        if table and len(table) > 1:
                            df = pd.DataFrame(table[1:], columns=table[0])
                            tables.append(df)
        except Exception:
            pass
        return tables
    
    def read_excel(self, file_content: bytes) -> Tuple[str, List[pd.DataFrame]]:
        try:
            excel_file = pd.ExcelFile(BytesIO(file_content))
            text_content = []
            dataframes = []
            
            for sheet_name in excel_file.sheet_names:
                df = pd.read_excel(excel_file, sheet_name=sheet_name)
                dataframes.append(df)
                text_content.append(f"Sheet: {sheet_name}")
                text_content.append(" ".join(str(col) for col in df.columns))
                for _, row in df.head(10).iterrows():
                    text_content.append(" ".join(str(val) for val in row.values))
            
            return "\n".join(text_content), dataframes
        except Exception as e:
            return f"Error reading Excel: {str(e)}", []
    
    def read_csv(self, file_content: bytes) -> Tuple[str, pd.DataFrame]:
        try:
            for encoding in ['utf-8', 'latin-1', 'cp1252']:
                try:
                    df = pd.read_csv(BytesIO(file_content), encoding=encoding)
                    text_content = []
                    text_content.append(" ".join(str(col) for col in df.columns))
                    for _, row in df.head(20).iterrows():
                        text_content.append(" ".join(str(val) for val in row.values))
                    return "\n".join(text_content), df
                except UnicodeDecodeError:
                    continue
            return "Could not decode CSV", pd.DataFrame()
        except Exception as e:
            return f"Error reading CSV: {str(e)}", pd.DataFrame()
    
    def extract_dates(self, content: str) -> Tuple[Optional[date], Optional[date]]:
        date_patterns = [
            r'(\d{2})/(\d{2})/(\d{4})',
            r'(\d{4})-(\d{2})-(\d{2})',
            r'(\d{2})-(\d{2})-(\d{4})',
        ]
        
        dates_found = []
        
        for pattern in date_patterns:
            matches = re.findall(pattern, content)
            for match in matches:
                try:
                    if len(match[0]) == 4:
                        d = date(int(match[0]), int(match[1]), int(match[2]))
                    else:
                        d = date(int(match[2]), int(match[1]), int(match[0]))
                    if 2020 <= d.year <= 2030:
                        dates_found.append(d)
                except ValueError:
                    continue
        
        if dates_found:
            return min(dates_found), max(dates_found)
        return None, None
    
    def extract_occupancy_data(self, dataframes: List[pd.DataFrame]) -> List[Dict[str, Any]]:
        occupancy_data = []
        
        for df in dataframes:
            columns_lower = [str(c).lower() for c in df.columns]
            
            date_col = None
            occupancy_col = None
            rooms_col = None
            arrivals_col = None
            departures_col = None
            
            for i, col in enumerate(columns_lower):
                if any(kw in col for kw in ['data', 'date', 'dia']):
                    date_col = df.columns[i]
                if any(kw in col for kw in ['ocupação', 'occupancy', 'taxa', 'occ%']):
                    occupancy_col = df.columns[i]
                if any(kw in col for kw in ['quartos', 'rooms', 'uhs', 'ocupados']):
                    rooms_col = df.columns[i]
                if any(kw in col for kw in ['chegadas', 'arrivals', 'check-in', 'in']):
                    arrivals_col = df.columns[i]
                if any(kw in col for kw in ['saídas', 'departures', 'check-out', 'out']):
                    departures_col = df.columns[i]
            
            if date_col:
                for _, row in df.iterrows():
                    try:
                        date_val = pd.to_datetime(row[date_col]).date()
                        record = {"date": date_val}
                        
                        if occupancy_col:
                            val = row[occupancy_col]
                            if isinstance(val, str):
                                val = float(val.replace('%', '').replace(',', '.'))
                            record["occupancy_rate"] = float(val)
                        
                        if rooms_col:
                            record["rooms_occupied"] = int(row[rooms_col])
                        
                        if arrivals_col:
                            record["arrivals"] = int(row[arrivals_col])
                        
                        if departures_col:
                            record["departures"] = int(row[departures_col])
                        
                        occupancy_data.append(record)
                    except Exception:
                        continue
        
        return occupancy_data
    
    def process_file(self, file_content: bytes, filename: str, file_type: str) -> Dict[str, Any]:
        result = {
            "text_content": "",
            "dataframes": [],
            "detected_type": "desconhecido",
            "confidence": 0,
            "indicators": [],
            "sectors": [],
            "date_start": None,
            "date_end": None,
            "extracted_data": {}
        }
        
        if file_type == "pdf":
            result["text_content"] = self.extract_text_from_pdf(file_content)
            result["dataframes"] = self.extract_tables_from_pdf(file_content)
        elif file_type in ["xlsx", "xls"]:
            result["text_content"], result["dataframes"] = self.read_excel(file_content)
        elif file_type == "csv":
            text, df = self.read_csv(file_content)
            result["text_content"] = text
            if not df.empty:
                result["dataframes"] = [df]
        
        detected_type, confidence, indicators, sectors = self.detect_report_type(
            result["text_content"], filename
        )
        result["detected_type"] = detected_type
        result["confidence"] = confidence
        result["indicators"] = indicators
        result["sectors"] = sectors
        
        date_start, date_end = self.extract_dates(result["text_content"])
        result["date_start"] = date_start
        result["date_end"] = date_end
        
        if result["dataframes"]:
            occupancy_data = self.extract_occupancy_data(result["dataframes"])
            if occupancy_data:
                result["extracted_data"]["occupancy"] = occupancy_data
        
        return result


report_processor = ReportProcessor()
