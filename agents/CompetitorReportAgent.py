from typing import TypedDict, Optional, List
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain.tools.tavily_search import TavilySearchResults

# GraphState 포함
class GraphState(TypedDict):
    startup_list: List[str]
    current_index: int
    current_company: Optional[str]
    tech_report: Optional[str]
    competitor_report: Optional[str]
    market_report: Optional[str]
    investment_summary: Optional[str]
    reports: List[str]
    final_report: Optional[str]

# 환경 변수 로드
load_dotenv()

llm = ChatOpenAI(model="gpt-3.5-turbo", temperature=0.3)
search = TavilySearchResults()

def extract_competitors_from_thevc(company_name: str) -> list:
    query = f"site:thevc.kr {company_name} 유사기업"
    results = search.invoke({"query": query})
    all_text = "\n".join([r["content"] for r in results[:5]])

    prompt = f"""
다음 텍스트는 여러 회사의 정보가 혼합되어 있습니다.

'{company_name}'에 대한 '유사 기업은 ~' 문장 하나만 정확히 찾아주세요.
다른 회사의 유사 기업 문장은 무시하세요.

그 문장에서 언급된 기업 이름만 최대 3개 추출해 주세요.

형식: 기업명1, 기업명2, 기업명3

텍스트:
{all_text}
"""
    response = llm.invoke(prompt).content.strip()
    return [name.strip() for name in response.split(",") if name.strip()]


def get_company_profile(company_name: str) -> str:
    query = f"{company_name} 스타트업 기술 전략 시장 제품 사업모델"
    results = search.invoke({"query": query})
    snippets = "\n".join([r["content"] for r in results[:5]])

    prompt = f"""
아래는 '{company_name}'에 대한 정보입니다.

이 회사의 기술, 전략, 시장 포지션을 요약해 주세요.

텍스트:
{snippets}

응답 형식:
- 회사명: {company_name}
- 기술: ...
- 전략: ...
- 시장: ...
"""
    return llm.invoke(prompt).content.strip()


def generate_competitor_report(company: str) -> str:
    competitors = extract_competitors_from_thevc(company)
    if not competitors:
        return f"[{company}]에 대한 유사 기업을 찾을 수 없습니다."

    profiles = []
    for comp in competitors:
        profile = get_company_profile(comp)
        profiles.append(profile)

    profile_text = "\n\n".join(profiles)

    prompt = f"""
'{company}'는 AI 스타트업입니다.

아래는 주요 경쟁사들의 프로필입니다:

{profile_text}

이 정보를 바탕으로 '{company}'의 경쟁사 분석 보고서를 작성해 주세요.

[경쟁사 분석 - {company}]
1. 주요 경쟁사 (간단 설명 포함)
2. 기술/전략/시장 비교 (표)
3. 각 경쟁사의 강점/약점
4. 진입장벽
5. 향후 경쟁 구도 예측

결론: 투자 관점에서 요약 평가
"""
    return llm.invoke(prompt).content.strip()


# LangGraph용 에이전트 함수
def competitor_agent(state: GraphState) -> GraphState:
    company = state.get("current_company")
    if not company:
        raise ValueError("current_company가 설정되어 있지 않습니다.")
    
    report = generate_competitor_report(company)
    return {**state, "competitor_report": report}