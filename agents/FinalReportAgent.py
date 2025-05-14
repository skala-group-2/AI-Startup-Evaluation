from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from GraphState import GraphState

load_dotenv()

def validate_final_report(report: str, retry_count: int = 0) -> str:
    eval_prompt = f"""
당신은 벤처 캐피탈의 투자 심사관으로, 아래 투자 분석 보고서가 출력 형식과 품질 기준을 잘 따르고 있는지 평가해야 합니다.

투자 분석 보고서:

------------------------
{report}
------------------------

다음 기준에 따라 판단하세요:

1. **시장성 평가, 제품 기술력 평가, 경쟁 우위 평가 항목의 점수가 0~10 사이의 정수인지**
2. **각 항목에 대한 설명이 해당 점수에 대한 타당한 설명으로 충분한지**
3. **최종 평가의 점수가 0~10 사이의 소수(float)인지**
4. **최종평가가 종합적인 평가로서 자연스럽고 논리적인지**

판단 결과는 아래 중 하나로 선택하세요:

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
        judgment = "RETRY" if retry_count < 2 else "FAIL"
    return judgment

def save_markdown(text: str, filename: str = "투자_최종_보고서.md", silent: bool = False):
    with open(filename, "w", encoding="utf-8") as f:
        f.write(text)
    if not silent:
        print(f"✅ Markdown 파일 저장 완료: {filename}")

def summerize_report(text) -> str:
    llm = ChatOpenAI(
        model="gpt-3.5-turbo-0125",  # 또는 "gpt-3.5-turbo"
        temperature=0.3
    )
    prompt = f"""
    당신은 벤처캐피탈의 투자 분석 보고서 작성 전문가입니다.

    아래는 AI 분석 에이전트들이 생성한 평가 결과를 바탕으로 구성된 텍스트입니다.
    이 텍스트를 기반으로 다음 기준을 모두 충족하는 **기업별 종합 보고서**를 작성해주세요:

    1. **해당 기업에 대해 점수(시장성, 기술력, 경쟁력, 최종점수)와 설명이 3줄 이상 명확하게 정리**되어야 합니다.
    2. **최종점수 기준으로 기업들을 투자 우선순위에 따라 정렬**해야 하며 각 기업별 최종점수를 명시해주어야 합니다.
    3. **해당 기업 투자 추천 여부 및 이유가 시장성, 기술력, 경쟁력의 요소를 바탕으로 명확하고 자세하게 작성**되어야 합니다.
    4. **전체 산업/기술 트렌드 분석, 공통 리스크 요인, 향후 투자 전략 제안이 포함**되어야 합니다.
    5. 모든 내용은 벤처캐피탈 보고서에 적합하도록 **논리적이고 명료한 문단 구성**으로 작성해주세요.

    ------------------------
    {text}
    ------------------------
    """
    report = llm.invoke(prompt).content.strip()
    return report

def final_report_agent_with_state(state: GraphState, max_retries: int = 3) -> dict:
    max_retries: int = 3
    reports = state.get("reports")
    full_report = ""
    for text in reports:
        company_report = summerize_report(text)
        full_report = full_report + "\n\n" + company_report

    for i in range(max_retries):
        prompt = f"""
    당신은 벤처캐피탈의 투자 분석 보고서 작성 전문가입니다.

    아래는 AI 분석 에이전트들이 생성한 평가 결과를 바탕으로 구성된 텍스트입니다.
    이 텍스트를 기반으로 다음 기준을 모두 충족하는 **총평**을 작성해주세요:

    1. 투자하기 좋은 기업을 선정하세요.
    2. 각 기업을 서로 비교 분석한 내용을 4문장 이상 작성하세요

    ------------------------
    {full_report}
    ------------------------
    """
        llm = ChatOpenAI(
            model="gpt-3.5-turbo-0125",  # 또는 "gpt-3.5-turbo"
            temperature=0.3
        )

        # 보고서 생성
        final_report = llm.invoke(prompt).content.strip()

    # 저장은 마지막에만, 메시지도 여기서만 출력
    save_markdown(full_report + "\n\n" + final_report, silent=False)

    return {
        **state,
        "final_report": final_report,
    }