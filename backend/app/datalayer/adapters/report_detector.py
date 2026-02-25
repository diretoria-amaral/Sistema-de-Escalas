import re
from typing import Optional, Tuple, List
import pdfplumber
import pandas as pd

PARSER_VERSION = "2.0.0"

CHECKIN_KEYWORDS = ["entrada", "checkin", "check-in", "check in", "chegada", "arrival"]
CHECKOUT_KEYWORDS = ["saida", "saída", "checkout", "check-out", "check out", "partida", "departure"]

DATE_COLUMN_HINTS = ["data", "date", "dt", "dia", "data_evento"]


class ReportDetector:
    """
    Detector de tipo de relatório por CONTEÚDO (não por nome de arquivo).
    
    Tipos suportados:
    - HP_DAILY: Relatório de Histórico e Previsão de Movimentação
    - CHECKIN_DAILY: Relatório diário de check-ins
    - CHECKOUT_DAILY: Relatório diário de check-outs
    
    Formatos suportados: PDF, CSV, Excel
    """
    
    HP_PATTERNS = [
        r"Relat[oó]rio\s+de\s+Hist[oó]rico\s+e\s+Previs[aã]o\s+de\s+Movimenta[cç][aã]o\s*[-–—]\s*Detalhado\s+por\s+tipo\s+de\s+hospedagem",
        r"Relat[oó]rio\s+de\s+Hist[oó]rico\s+e\s+Previs[aã]o\s+de\s+Movimenta[cç][aã]o",
        r"Detalhado\s+por\s+tipo\s+de\s+hospedagem",
        r"Per[ií]odo:\s*\d{2}/\d{2}/\d{4}\s*[-–—]\s*\d{2}/\d{2}/\d{4}"
    ]
    
    HP_EMISSION_PATTERN = r"(\w+-feira),?\s+(\d{1,2})\s+de\s+(\w+)\s+de\s+(\d{4})\s+[àa]?s?\s*(\d{2}):(\d{2})"
    
    CHECKIN_ANCHOR = r"Entradas?\s+(\d{2}/\d{2}/\d{4})"
    CHECKOUT_ANCHOR = r"Sa[ií]das?\s+(\d{2}/\d{2}/\d{4})"
    
    @classmethod
    def detect_from_pdf(cls, file_path: str) -> Tuple[Optional[str], int, str]:
        try:
            with pdfplumber.open(file_path) as pdf:
                text = ""
                for page in pdf.pages[:3]:
                    page_text = page.extract_text() or ""
                    text += page_text + "\n"
                
                return cls._detect_from_text(text)
        except Exception as e:
            return None, 0, f"Erro ao ler PDF: {str(e)}"
    
    @classmethod
    def detect_from_text(cls, text: str) -> Tuple[Optional[str], int, str]:
        return cls._detect_from_text(text)
    
    @classmethod
    def _detect_from_text(cls, text: str) -> Tuple[Optional[str], int, str]:
        hp_matches = sum(1 for p in cls.HP_PATTERNS if re.search(p, text, re.IGNORECASE))
        has_emission_line = bool(re.search(cls.HP_EMISSION_PATTERN, text, re.IGNORECASE))
        
        if hp_matches >= 2 or (hp_matches >= 1 and has_emission_line):
            confidence = min(100, (hp_matches + (1 if has_emission_line else 0)) * 30)
            details = f"{hp_matches}/4 padrões"
            if has_emission_line:
                details += " + linha de emissão"
            return "HP_DAILY", confidence, f"Detectado HP_DAILY ({details})"
        
        checkin_match = re.search(cls.CHECKIN_ANCHOR, text, re.IGNORECASE)
        checkout_match = re.search(cls.CHECKOUT_ANCHOR, text, re.IGNORECASE)
        
        has_checkin_anchor = bool(checkin_match)
        has_checkout_anchor = bool(checkout_match)
        
        if has_checkin_anchor and not has_checkout_anchor:
            anchor_date = checkin_match.group(1) if checkin_match else ""
            return "CHECKIN_DAILY", 95, f"Detectado CHECKIN_DAILY (âncora Entrada {anchor_date})"
        
        if has_checkout_anchor and not has_checkin_anchor:
            anchor_date = checkout_match.group(1) if checkout_match else ""
            return "CHECKOUT_DAILY", 95, f"Detectado CHECKOUT_DAILY (âncora Saída {anchor_date})"
        
        if has_checkin_anchor and has_checkout_anchor:
            return None, 0, "Ambíguo: contém âncoras de CHECKIN e CHECKOUT"
        
        return None, 0, "Tipo de relatório não identificado automaticamente"
    
    @classmethod
    def detect_from_filename(cls, filename: str) -> Tuple[Optional[str], int, str]:
        """Fallback: detectar por nome do arquivo (baixa confiança)."""
        filename_lower = filename.lower()
        
        if "checkin" in filename_lower or "check-in" in filename_lower or "entrada" in filename_lower:
            return "CHECKIN_DAILY", 40, "Detectado por nome do arquivo (CHECKIN) - baixa confiança"
        
        if "checkout" in filename_lower or "check-out" in filename_lower or "checkou" in filename_lower:
            return "CHECKOUT_DAILY", 40, "Detectado por nome do arquivo (CHECKOUT) - baixa confiança"
        
        if "saida" in filename_lower or "saída" in filename_lower:
            return "CHECKOUT_DAILY", 40, "Detectado por nome do arquivo (CHECKOUT) - baixa confiança"
        
        if "hp" in filename_lower or "historico" in filename_lower or "previsao" in filename_lower:
            return "HP_DAILY", 40, "Detectado por nome do arquivo (HP) - baixa confiança"
        
        return None, 0, "Não detectado pelo nome do arquivo"
    
    @classmethod
    def detect_from_csv(cls, file_path: str) -> Tuple[Optional[str], int, str]:
        """Detecta tipo de relatório a partir de arquivo CSV."""
        try:
            encodings = ['utf-8', 'latin-1', 'cp1252', 'iso-8859-1']
            separators = [',', ';', '\t', '|']
            
            df = None
            for encoding in encodings:
                for sep in separators:
                    try:
                        df = pd.read_csv(file_path, encoding=encoding, sep=sep, nrows=100)
                        if len(df.columns) > 1:
                            break
                    except:
                        continue
                if df is not None and len(df.columns) > 1:
                    break
            
            if df is None or df.empty:
                return None, 0, "Não foi possível ler o arquivo CSV"
            
            return cls._detect_from_dataframe(df)
            
        except Exception as e:
            return None, 0, f"Erro ao ler CSV: {str(e)}"
    
    @classmethod
    def detect_from_excel(cls, file_path: str) -> Tuple[Optional[str], int, str]:
        """Detecta tipo de relatório a partir de arquivo Excel (.xlsx and .xls)."""
        try:
            file_ext = file_path.split(".")[-1].lower() if file_path else ""
            engine = 'xlrd' if file_ext == 'xls' else 'openpyxl'
            
            df = pd.read_excel(file_path, engine=engine, nrows=100)
            
            if df.empty:
                xlsx = pd.ExcelFile(file_path, engine=engine)
                for sheet in xlsx.sheet_names[:3]:
                    df = pd.read_excel(xlsx, sheet_name=sheet, nrows=100)
                    if not df.empty:
                        break
            
            if df.empty:
                return None, 0, "Arquivo Excel vazio"
            
            return cls._detect_from_dataframe(df)
            
        except Exception as e:
            return None, 0, f"Erro ao ler Excel: {str(e)}"
    
    @classmethod
    def _detect_from_dataframe(cls, df: pd.DataFrame) -> Tuple[Optional[str], int, str]:
        """Detecta tipo de relatório pelos dados do DataFrame."""
        columns_str = " ".join([str(c).lower() for c in df.columns])
        
        has_date_col = any(hint in columns_str for hint in DATE_COLUMN_HINTS)
        if not has_date_col:
            return None, 0, "Arquivo não contém coluna de data reconhecida"
        
        checkin_score = sum(1 for kw in CHECKIN_KEYWORDS if kw in columns_str)
        checkout_score = sum(1 for kw in CHECKOUT_KEYWORDS if kw in columns_str)
        
        if checkin_score > checkout_score:
            confidence = min(90, 50 + checkin_score * 15)
            return "CHECKIN_DAILY", confidence, f"Detectado CHECKIN_DAILY por colunas (score: {checkin_score})"
        
        if checkout_score > checkin_score:
            confidence = min(90, 50 + checkout_score * 15)
            return "CHECKOUT_DAILY", confidence, f"Detectado CHECKOUT_DAILY por colunas (score: {checkout_score})"
        
        if len(df.columns) >= 2 and has_date_col:
            return None, 30, "Arquivo tabular com datas - tipo específico não identificado"
        
        return None, 0, "Tipo de relatório não identificado automaticamente"
    
    @classmethod
    def detect(cls, file_path: str, filename: str) -> Tuple[Optional[str], int, str]:
        """
        Detecta tipo de relatório automaticamente baseado no formato e conteúdo.
        
        Args:
            file_path: Caminho completo do arquivo
            filename: Nome original do arquivo
        
        Returns:
            Tuple[tipo_detectado, confiança, mensagem]
        """
        ext = filename.split(".")[-1].lower() if "." in filename else ""
        
        if ext == "pdf":
            result = cls.detect_from_pdf(file_path)
            if result[0]:
                return result
        
        elif ext == "csv":
            result = cls.detect_from_csv(file_path)
            if result[0]:
                return result
        
        elif ext in ["xlsx", "xls"]:
            result = cls.detect_from_excel(file_path)
            if result[0]:
                return result
        
        fallback = cls.detect_from_filename(filename)
        return fallback
