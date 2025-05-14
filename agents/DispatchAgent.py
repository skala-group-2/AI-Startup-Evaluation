from GraphState import GraphState

STARTUP_LIST = ["업스테이지", "노타AI", "트웰브랩스", "뤼이드", "에어스메디컬"]



def role_dispatch_agent(state: GraphState) -> GraphState:
    idx = state["current_index"]
    company = STARTUP_LIST[idx]
    return {
        "current_index": idx,
        "current_company": company
    }

def increment_index(state: GraphState) -> GraphState:
    summary = state.get("investment_summary", "[요약 없음]")
    reports = state.get("reports", [])
    print(state["current_index"])
    return {
        **state,
        "current_index": state["current_index"] + 1,
        "tech_report": None,
        "competitor_report": None,
        "market_report": None,
        "investment_summary": None,
        "investment_summary_retry_count": 0,
        "reports": reports + [summary]
    }

def check_continue(state: GraphState) -> str:
    return "continue" if state["current_index"] < len(STARTUP_LIST) else "done"