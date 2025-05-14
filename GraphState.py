from typing import TypedDict, List, Optional

# 전체 그래프 상태 정의
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