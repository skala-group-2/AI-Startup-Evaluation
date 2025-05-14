from dotenv import load_dotenv
from langchain_core.prompts import PromptTemplate
from langchain_openai import ChatOpenAI
from GraphState import GraphState

load_dotenv()

# 프롬프트 템플릿 정의
investment_prompt = PromptTemplate.from_template("""
다음은 특정 스타트업에 대한 3가지 분석 보고서입니다.

[기술 분석 보고서]
{tech_report}

[경쟁사 비교 보고서]
{competitor_report}

[시장 분석 보고서]
{market_report}

위의 정보를 바탕으로, 아래 3가지 항목을 평가해 주세요:
회사명: (스타트업의 회사명)

1. **시장성 평가**
   - 점수 (0~10점)
   - 설명 (시장 성장 가능성, 진입장벽, 수요 등 포함)

2. **제품 기술력 평가**
   - 점수 (0~10점)
   - 설명 (핵심 기술, 독창성, 확장성 등 포함)

3. **경쟁 우위 평가**
   - 점수 (0~10점)
   - 설명 (경쟁사 대비 차별성, 지속 가능성 등 포함)

---

4. 최종 평가

- 최종 점수 = 시장성*0.5 + 기술력*0.3 + 경쟁우위*0.2 (소수점 둘째 자리까지)
- 총평: 전반적인 투자 판단과 함께, 고려할 만한 리스크 요인 등을 간단히 요약
""")

def investment_analysis_agent(state: GraphState) -> GraphState:
    prompt = investment_prompt.format(
        tech_report=state["tech_report"],
        competitor_report=state["competitor_report"],
        market_report=state["market_report"],
    )
    llm = ChatOpenAI(
        model="gpt-3.5-turbo-0125",  # 또는 "gpt-3.5-turbo"
        temperature=0.3
    )
    investment_summary_msg = llm.invoke(prompt)
    investment_summary = investment_summary_msg.content
    report = f"""
    [{state["current_company"]} 보고서]

    A. 기술 분석
    {state["tech_report"]}

    B. 경쟁사 비교
    {state["competitor_report"]}

    C. 시장 분석
    {state["market_report"]}

    D. 투자 평가
    {investment_summary}
    """
    return {
        **state,
        "investment_summary": report
    }

def validate_report(state: GraphState) -> str:
    summary = state["investment_summary"]

    eval_prompt = f"""
당신은 벤처 캐피탈의 투자 심사관으로, 아래 투자 분석 보고서가 출력 형식과 품질 기준을 잘 따르고 있는지 평가해야 합니다.

투자 분석 보고서:

------------------------
{summary}
------------------------

다음 기준에 따라 판단하세요:

1. **시장성 평가, 제품 기술력 평가, 경쟁 우위 평가 항목의 점수가 0~10 사이의 정수인지**
2. **시장성 평가, 제품 기술력 평가, 경쟁 우위 평가 항목의 설명이 해당 점수에 대한 타당한 설명으로 충분한지**
3. **최종 평가의 점수가 0~10 사이의 소수(float)인지**
4. **최종평가가 종합적인 평가로서 자연스럽고 논리적인지**

판단 결과는 아래 기준에 따라 선택하세요:

- **PASS**: 모든 항목의 형식과 설명이 정확하며 논리적으로 납득 가능함
- **RETRY**: 일부 설명이 부족하거나 점수가 애매하지만 수정 가능함
- **FAIL**: 형식 오류나 설명 누락 등으로 활용 불가능함

단 한 단어만 출력하세요: `PASS`, `RETRY`, `FAIL`
"""
    llm = ChatOpenAI(
        model="gpt-3.5-turbo-0125",  # 또는 "gpt-3.5-turbo"
        temperature=0.3
    )
    judgment = llm.invoke(eval_prompt).content.strip().upper()

    if judgment not in ["PASS", "RETRY", "FAIL"]:
        print(state.get("investment_summary_retry_count", 0))
        judgment = "RETRY" if state.get("investment_summary_retry_count", 0) < 1 else "FAIL"

    return judgment

# 재시도 시 카운트 증가
def increment_retry(state: GraphState) -> GraphState:
    return {**state, "investment_summary_retry_count": state.get("investment_summary_retry_count", 0) + 1}