import os
import glob
import re
import logging
from dotenv import load_dotenv
from openai import OpenAI
from tavily import TavilyClient
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor
from requests import get
from sentence_transformers import SentenceTransformer
from chromadb import Client
from chromadb.config import Settings
from PyPDF2 import PdfReader

# 환경변수 로드
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logging.getLogger("chromadb.telemetry").setLevel(logging.CRITICAL)

# 클라이언트 초기화
openai_client = OpenAI(api_key=OPENAI_API_KEY)
# SBERT 모델 로드
sbert_model = SentenceTransformer('all-MiniLM-L6-v2')

# ChromaDB 설정
settings = Settings(
    anonymized_telemetry=True,
    persist_directory="chromadb_tech_eval"
)
chroma = Client(settings)
# 컬렉션
patent_index = chroma.get_or_create_collection("patent_embeddings_sbert")

# 데이터 처리 함수
def chunk_text(text: str, max_chars: int = 2000) -> list[str]:
    sentences = re.split(r'(?<=[\.!?])\s+', text)
    chunks, current = [], ""
    for sent in sentences:
        if len(current) + len(sent) <= max_chars:
            current = current + " " + sent if current else sent
        else:
            chunks.append(current)
            current = sent
    if current:
        chunks.append(current)
    return chunks

# 인덱싱 함수
def index_patents(patent_texts: list[str], patent_ids: list[str], company: str):
    vectors = sbert_model.encode(patent_texts).tolist()
    metadatas = [{"company": company} for _ in patent_texts]
    patent_index.add(
        documents=patent_texts,
        embeddings=vectors,
        ids=patent_ids,
        metadatas=metadatas
    )

# PDF에서 특허 개수 세기
def count_patents_in_pdf(company: str, base_dir: str = "data") -> int:
    path = glob.glob(os.path.join(base_dir, company, "*.pdf"))[0]
    reader = PdfReader(path)
    full_text = "".join(page.extract_text() or "" for page in reader.pages)
    matches = re.findall(r"특허\s*\d+\s*:", full_text)
    return len(matches)

# 쿼리 생성기
class QueryGenerator:
    TECH_KWS = [
        "핵심 기술 키워드",
        "R&D 현황",
        "특허 건수 및 영역",
        "제품·솔루션 기술력"
    ]
    def tech_queries(self, company: str) -> list[str]:
        return [f"{company} {kw}" for kw in self.TECH_KWS]

# 요약 엔진
class FeatureStructurer:
    def summarize(self, title: str, snippets: list[str]) -> str:
        joined = "\n\n".join(snippets[:5])
        prompt = f"‘{title}’ 관련 핵심 정보를 5문장으로 요약하세요.\n\n{joined}"
        resp = openai_client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role":"user","content":prompt}],
            temperature=0.3,
            max_tokens=400
        )
        txt = resp.choices[0].message.content.strip()
        return txt if txt.endswith('.') else txt + '.'

# 하향식 요약
class HierarchicalSummarizer:
    def __init__(self, structurer: FeatureStructurer):
        self.structurer = structurer
    def summarize(self, title: str, snippets: list[str], batch_size: int = 5) -> str:
        batches = [snippets[i:i+batch_size] for i in range(0, len(snippets), batch_size)]
        summaries = []
        for idx, batch in enumerate(batches, 1):
            joined = "\n\n".join(batch)
            prompt = f"‘{title}’ 배치 {idx}를 5문장으로 요약하세요.\n\n{joined}"
            resp = openai_client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role":"user","content":prompt}],
                temperature=0.3,
                max_tokens=300
            )
            txt = resp.choices[0].message.content.strip()
            summaries.append(txt if txt.endswith('.') else txt + '.')
        joined_summaries = "\n\n".join(summaries)
        prompt = f"‘{title}’ 전체를 5문장으로 최종 요약하세요.\n\n{joined_summaries}"
        resp = openai_client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role":"user","content":prompt}],
            temperature=0.3,
            max_tokens=300
        )
        final = resp.choices[0].message.content.strip()
        return final if final.endswith('.') else final + '.'

# 통합 평가기
class IntegratedEvaluator:
    def __init__(self):
        self.qgen = QueryGenerator()
        self.structurer = FeatureStructurer()
        self.hier = HierarchicalSummarizer(self.structurer)
        self.patent_idx = patent_index
    def evaluate(self, company: str, n_results: int = 50, batch_size: int = 5) -> dict:
        actual_count = count_patents_in_pdf(company)
        emb = sbert_model.encode([f"{company} 기술 OR 특허"]).tolist()
        patent_snips = self.patent_idx.query(
            query_embeddings=emb,
            n_results=n_results,
            where={"company": company}
        )["documents"][0]
        tech_analysis = {}
        for q in self.qgen.tech_queries(company):
            emb_q = sbert_model.encode([q]).tolist()
            snips = self.patent_idx.query(
                query_embeddings=emb_q,
                n_results=n_results,
                where={"company": company}
            )["documents"][0]
            tech_analysis[q] = self.hier.summarize(q, snips, batch_size)
        combined = patent_snips + [s for s in tech_analysis.values()]
        summary = self.hier.summarize(f"{company} 기술력", combined, batch_size)
        return {
            "company": company,
            "patent_count": actual_count,
            "summary": summary,
            "tech_analysis": tech_analysis
        }
    
