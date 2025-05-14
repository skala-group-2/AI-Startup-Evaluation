from dotenv import load_dotenv
from langchain_core.runnables import RunnableLambda

from GraphState import GraphState
from langgraph.graph import StateGraph, END
from GraphState import GraphState

from agents.DispatchAgent import role_dispatch_agent, increment_index, check_continue
from agents.MarketReportAgent import market_agent
from agents.CompetitorReportAgent import competitor_agent
from agents.TechReportAgent import tech_agent
from agents.InvestmentAgent import investment_analysis_agent, validate_report, increment_retry
from agents.FinalReportAgent import final_report_agent_with_state

load_dotenv()

# ----------------------------------------
# LangGraph 구성
# ----------------------------------------
builder = StateGraph(GraphState)

# 노드 등록
builder.add_node("dispatch", RunnableLambda(role_dispatch_agent))
builder.add_node("tech", RunnableLambda(tech_agent))
builder.add_node("competitor", RunnableLambda(competitor_agent))
builder.add_node("market", RunnableLambda(market_agent))
builder.add_node("investment_report", RunnableLambda(investment_analysis_agent))
builder.add_node("increment_retry", RunnableLambda(increment_retry))
builder.add_node("final", RunnableLambda(final_report_agent_with_state))
builder.add_node("increment_index", RunnableLambda(increment_index))
builder.add_node("check_ready", RunnableLambda(lambda x: x))

# 병렬 실행처럼 동작하도록 edge 연결 (각각 따로)
builder.set_entry_point("dispatch")
builder.add_edge("dispatch", "tech")
builder.add_edge("tech", "competitor")
builder.add_edge("competitor", "market")
builder.add_edge("market", "investment_report")

builder.add_conditional_edges("investment_report", validate_report, {
    "PASS": "increment_index",
    "RETRY": "increment_retry",
    "FAIL": "increment_index"
})
builder.add_edge("increment_retry", "investment_report")
builder.add_conditional_edges("increment_index", check_continue, {
    "continue": "dispatch",
    "done": "final"
})
builder.add_edge("final", END)

graph = builder.compile()

# 실행하는 부분
test_state = {
    "current_index": 0,
    "investment_summary_retry_count": 0
}

final_state = graph.invoke(test_state, config={"recursion_limit": 50})
print(final_state["final_report"]) 