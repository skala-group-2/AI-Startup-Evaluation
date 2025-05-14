import os
import logging
from dotenv import load_dotenv
from tavily import TavilyClient
from bs4 import BeautifulSoup
from typing import List, Dict, Optional, Any, TypedDict
from openai import OpenAI
from concurrent.futures import ThreadPoolExecutor
from requests import get

# (1) GraphState 정의
class GraphState(TypedDict):                 # 조사 대상 기업 목록
    current_index: Optional[int]                        # 현재 조사 중인 기업 인덱스
    current_company: Optional[str]               # 현재 기업 이름
    tech_report: Optional[str]
    competitor_report: Optional[str]
    market_report: Optional[str]
    investment_summary: Optional[str]  
    investment_summary_retry_count: Optional[int]
    reports: Optional[List[str]]
    final_report: Optional[str]

# (2) 환경변수 로드
load_dotenv()
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# (3) 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# (4) OpenAI 클라이언트 초기화
client = OpenAI(api_key=OPENAI_API_KEY)

# (5) 도메인 분류기
class DomainClassifier:
    def __init__(self):
        if not TAVILY_API_KEY:
            raise ValueError("TAVILY_API_KEY가 설정되어 있지 않습니다.")
        self.retriever = TavilyClient(api_key=TAVILY_API_KEY)

    def classify(self, company: str) -> str:
        resp = self.retriever.search(
            query=company,
            max_results=5,
            include_images=False,
            include_image_descriptions=False
        )
        snippets = [item.get("content") or item.get("description", "") for item in resp.get("results", [])]
        joined = "\n\n".join(snippets[:5])
        prompt = f"""
다음은 '{company}'에 대한 검색 결과에서 추출된 텍스트입니다.
이 정보를 참고하여 '{company}'의 핵심 도메인을 한두 단어로 태깅해 주세요.
텍스트:
{joined}
"""
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=20,
            temperature=0.0,
        )
        return response.choices[0].message.content.strip()

# (6) 쿼리 생성기
class QueryGenerator:
    DOMAIN_QUERIES = ["시장 규모", "CAGR", "핵심 기술 트렌드"]
    COMPANY_QUERIES = ["시장 점유율", "손익", "펀딩 현황", "매출 현황"]

    def make_domain_queries(self, domain: str) -> List[str]:
        return [f"{domain} 시장 {kw}" for kw in self.DOMAIN_QUERIES]

    def make_company_queries(self, company: str) -> List[str]:
        return [f"{company} {kw}" for kw in self.COMPANY_QUERIES]

# (7) 웹 검색기
class WebRetriever:
    def __init__(self, api_key: str):
        if not api_key:
            raise ValueError("TAVILY_API_KEY가 설정되어 있지 않습니다.")
        self.client = TavilyClient(api_key=api_key)

    def search(self, query: str, num: int = 5) -> List[Dict[str, str]]:
        resp = self.client.search(query=query, max_results=num,
                                  include_images=False,
                                  include_image_descriptions=False)
        results = []
        for item in resp.get("results", []):
            url = item.get("url")
            snippet = item.get("content") or item.get("description") or ""
            if url:
                results.append({"url": url, "snippet": snippet})
        return results

# (8) 콘텐츠 추출기 (병렬)
class ContentExtractor:
    def extract_snippets(self, url: str, keywords: List[str]) -> List[str]:
        snippets = []
        try:
            res = get(url, timeout=5)
            res.raise_for_status()
            soup = BeautifulSoup(res.text, "html.parser")
            for p in soup.find_all("p"):
                text = p.get_text(strip=True)
                if any(kw in text for kw in keywords):
                    snippets.append(text)
        except Exception as e:
            logger.warning(f"URL 처리 중 오류 ({url}): {e}")
        return snippets

    def extract_bulk(self, urls: List[str], keywords: List[str]) -> List[str]:
        snippets = []
        with ThreadPoolExecutor(max_workers=8) as executor:
            futures = [executor.submit(self.extract_snippets, url, keywords) for url in urls]
            for future in futures:
                snippets.extend(future.result())
        return snippets

# (9) 요약기
class FeatureStructurer:
    def summarize(self, title: str, texts: List[str]) -> str:
        if not texts:
            return "정보 부족"
        joined = "\n\n".join(texts[:5])
        prompt = f"""
아래는 '{title}'에 관한 핵심 정보 스니펫입니다.
- 요청: '{title}'에 해당하는 핵심 숫자나 키워드를 정확히 **2문장 이내**로 완결형 문장(마침표 포함)으로 요약하세요.
- 문장은 마침표로 끝나야 하며, 불필요한 내용은 제거하세요.
- 출력은 반드시 2문장으로 구성되어야 합니다.

스니펫:
{joined}
"""
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=250,
            temperature=0.2,
            stop=["\n"]
        )
        summary = response.choices[0].message.content.strip()
        if not summary.endswith("."):
            summary += "."
        return summary

# (10) 시장성 평가
class MarketEvaluationAgent:
    def __init__(self):
        self.domain_cls = DomainClassifier()
        self.query_gen = QueryGenerator()
        self.retriever = WebRetriever(api_key=TAVILY_API_KEY)
        self.extractor = ContentExtractor()
        self.structurer = FeatureStructurer()

    def evaluate(self, company: str) -> Dict[str, Any]:
        comp_name = company
        domain = self.domain_cls.classify(comp_name)

        def analyze(queries: List[str], keywords: List[str]) -> Dict[str, str]:
            out: Dict[str, str] = {}
            for q in queries:
                entries = self.retriever.search(q)
                api_snippets = [e['snippet'] for e in entries if e['snippet']]
                urls = [e['url'] for e in entries]
                web_snippets = self.extractor.extract_bulk(urls, keywords)
                all_snippets = api_snippets + web_snippets
                out[q] = self.structurer.summarize(q, all_snippets)
            return out

        domain_analysis = analyze(self.query_gen.make_domain_queries(domain), [domain])
        company_analysis = analyze(self.query_gen.make_company_queries(comp_name), [comp_name])

        return {
            "company": comp_name,
            "domain": domain,
            "domain_analysis": domain_analysis,
            "company_analysis": company_analysis,
        }

# (11) 보고서 포맷 함수
def format_market_report(result: Dict[str, Any]) -> str:
    company_str = f"1. 기업: {result['company']}"
    domain_str = f"2. 도메인: {result['domain']}"
    domain_lines = [f"   - {k}: {v}" for k, v in result['domain_analysis'].items()]
    domain_analysis_str = "3. 도메인 분석:\n" + "\n".join(domain_lines)
    company_lines = [f"   - {k}: {v}" for k, v in result['company_analysis'].items()]
    company_analysis_str = "4. 기업 분석:\n" + "\n".join(company_lines)
    report = (
        "시장성 평가\n"
        + company_str + "\n"
        + domain_str + "\n"
        + domain_analysis_str + "\n"
        + company_analysis_str
    )
    return report

# (12) market_agent
def market_agent(state: GraphState) -> GraphState:
    company = state.get("current_company")
    if not company:
        raise ValueError("current_company가 설정되어 있지 않습니다.")
    agent = MarketEvaluationAgent()
    result = agent.evaluate(company)
    report = format_market_report(result)
    return {"market_report": report}
    # return {**state, "market_report": report}