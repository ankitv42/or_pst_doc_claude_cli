# Step 1 — you define a TypedDict with your field names
class AgentState(TypedDict):
    sku_id:           str
    demand_summary:   Optional[dict]
    options_package:  Optional[dict]
    ...

# Step 2 — you pass it to StateGraph
builder = StateGraph(AgentState)
#                    ↑
#                    LangGraph reads the field names from here
#                    It now knows state has sku_id, demand_summary, etc.

# Step 3 — you add nodes
builder.add_node("agent1_node", agent1_node)

# Step 4 — LangGraph compiles
app = builder.compile()
#     ↑
#     LangGraph now manages a dict with AgentState's fields
#     When agent1_node returns {"demand_summary": {...}}
#     LangGraph checks — is "demand_summary" a valid field in AgentState?
#     Yes → merge it in. No → error.