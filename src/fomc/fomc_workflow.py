import json
import os
from datetime import datetime, date
from typing import Dict, Optional, Any, List, TypedDict

# --- LangChain & LangGraph Imports ---
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.messages import SystemMessage, HumanMessage
from langgraph.graph import StateGraph, END
from langsmith import traceable

from src.llm.claude_client import get_claude_client
from src.prompt_engineering.templates import FOMC_SYSTEM_PROMPT

from .fomc_fetchers import fetch_all_fomc_data
from .fomc_database import FOMCDatabase
from .fomc_models import FOMCAnalysisOutput


class FOMCGraphState(TypedDict):
    """
    Represents the state of the FOMC Analysis Workflow.
    Passed between LangGraph nodes.
    """
    force_date: Optional[str]
    
    # Node Outputs
    fetch_results: Dict[str, Any]      # Output from Scraper
    db_state: Dict[str, Any]           # Output from DB Query
    
    # Logic Checks
    aligned_data: Dict[str, Any]       # Data aligned by date
    should_run: bool                   # Decision flag
    status_message: str                # Reason for running/skipping
    
    # Final Results
    analysis_result: Optional[FOMCAnalysisOutput] # Structured LLM Output
    final_output: Dict[str, Any]       # Final JSON for return

class FOMCAnalysisWorkflow:
    def __init__(self, anthropic_api_key: str, db_connection_params: Dict, langsmith_api_key: Optional[str] = None):
        """
        Initialize the workflow with credentials passed from main.py
        """
        # 1. Setup Database (Use the params passed in, not the global settings)
        self.db = FOMCDatabase(db_connection_params)
        
        # 2. Setup LangSmith (Observability)
        if langsmith_api_key:
            os.environ["LANGSMITH_TRACING"] = "true"
            os.environ["LANGSMITH_ENDPOINT"] = "https://api.smith.langchain.com"
            os.environ["LANGSMITH_API_KEY"] = langsmith_api_key
            os.environ["LANGSMITH_PROJECT"] = "fomc-analysis-agent"
            # print("✓ LangSmith Tracing Enabled") # Optional: Keep logs clean

        # 3. Setup LangChain LLM
        # We assume get_claude_client handles the key or env var. 
        # If your factory takes an api_key arg, pass it here: get_claude_client(api_key=anthropic_api_key)
        self.llm = get_claude_client() 
        self.parser = PydanticOutputParser(pydantic_object=FOMCAnalysisOutput)

        # 4. Build the Graph
        self.app = self._build_graph()

    def _build_graph(self):
        """Constructs the LangGraph StateMachine"""
        workflow = StateGraph(FOMCGraphState)

        # -- Define Nodes --
        workflow.add_node("scrape_and_upsert", self.node_scrape_and_upsert)
        workflow.add_node("pull_db_state", self.node_pull_db_state)
        workflow.add_node("check_logic", self.node_check_logic)
        workflow.add_node("run_analysis", self.node_run_analysis)
        workflow.add_node("save_results", self.node_save_results)

        # -- Define Edges --
        workflow.set_entry_point("scrape_and_upsert")
        workflow.add_edge("scrape_and_upsert", "pull_db_state")
        workflow.add_edge("pull_db_state", "check_logic")
        
        # -- Conditional Branching --
        workflow.add_conditional_edges(
            "check_logic",
            self.decision_should_analyze,
            {
                "continue": "run_analysis",
                "stop": END
            }
        )
        
        workflow.add_edge("run_analysis", "save_results")
        workflow.add_edge("save_results", END)

        return workflow.compile()

    # --- Public Entry Point ---
    def run(self, force_date: Optional[str] = None) -> Dict:
        """Executes the workflow graph"""
        print(f"Starting LangGraph Workflow (Force Date: {force_date if force_date else 'Auto'})...")
        
        initial_state = {
            "force_date": force_date,
            "fetch_results": {},
            "db_state": {},
            "aligned_data": {},
            "should_run": False,
            "status_message": "",
            "analysis_result": None,
            "final_output": {"status": "started"}
        }

        # Invoke the graph
        final_state = self.app.invoke(initial_state)
        return final_state["final_output"]

    # --- Node 1: Scrape & Upsert ---
    def node_scrape_and_upsert(self, state: FOMCGraphState) -> Dict:
        print(">> Node: Scrape & Upsert")
        force_date = state.get("force_date")
        fetched = fetch_all_fomc_data(force_date)
        
        today = datetime.now().date()
        
        def is_valid_date(date_str: Optional[str]) -> bool:
            if not date_str: return False
            try:
                release_date = datetime.strptime(date_str, "%Y-%m-%d").date()
                return release_date <= today
            except ValueError: return False

        for key in ['statement', 'minutes', 'projection_note', 'implementation_note']:
            item = fetched.get(key, {})
            d = item.get('new_release_date')
            content = item.get(key) # key matches content field name mostly
            
            # Helper for specific DB methods
            if d and is_valid_date(d):
                if key == 'statement': self.db.upsert_statement(d, content)
                elif key == 'minutes': self.db.upsert_minutes(d, content)
                elif key == 'projection_note': self.db.upsert_projection_note(d, content)
                elif key == 'implementation_note': self.db.upsert_implementation_note(d, content)
            
        return {"fetch_results": fetched}

    # --- Node 2: Pull DB State ---
    def node_pull_db_state(self, state: FOMCGraphState) -> Dict:
        print(">> Node: Pull DB State")
        
        # 1. Fetch History to find latest verdict
        history = self.db.get_six_months_fomc_verdict()
        latest_verdict = history[0] if history else {}

        # 2. Fetch Latest Dates (Strings)
        db_data = {
            "minutes_date": self.db.get_latest_minutes_date(),
            "statement_date": self.db.get_latest_statement_date(),
            "implementation_date": self.db.get_latest_implementation_date(),
            "projection_date": self.db.get_latest_projection_date(),
            "verdict": latest_verdict,
            "history": history
        }
        return {"db_state": db_data}

    # --- Node 3: Check Logic ---
    def node_check_logic(self, state: FOMCGraphState) -> Dict:
        print(">> Node: Check Logic")
        db_state = state["db_state"]
        fetched_results = state.get("fetch_results", {})
        force_date = state.get("force_date")
        
        d_min = db_state["minutes_date"]
        d_stmt = db_state["statement_date"]
        d_impl = db_state["implementation_date"]
        d_proj = db_state["projection_date"]
        
        valid_dates = [d for d in [d_min, d_stmt, d_impl, d_proj] if d]
        auto_max_date = max(valid_dates) if valid_dates else None
        
        # Unified Target Date Logic
        target_date = force_date if force_date else auto_max_date
        
        if not target_date:
            # Fallback if DB is empty and no force date
            target_date = datetime.now().strftime("%Y-%m-%d")

        # 2. ALIGN DATA (Knockout Strategy)
        #    We knockout any content that does not match 'target_date'
        def get_aligned(key, subkey, candidate_date):
            if candidate_date != target_date:
                return None
            # Fetch content from results (or DB if needed)
            item = fetched_results.get(key, {})
            if item.get("new_release_date") == target_date:
                return item.get(subkey)
            return None

        aligned = {
            "max_release_date": target_date,
            "minutes_release_date": target_date if d_min == target_date else None,
            "minutes_content": get_aligned("minutes", "minutes", d_min),
            "statement_release_date": target_date if d_stmt == target_date else None,
            "statement": get_aligned("statement", "statement", d_stmt),
            "implementation_note_release_date": target_date if d_impl == target_date else None,
            "implementation_note": get_aligned("implementation_note", "implementation_note", d_impl),
            "projection_note_release_date": target_date if d_proj == target_date else None,
            "projection_note": get_aligned("projection_note", "projection_note", d_proj),
            "history": db_state["history"]
        }

        # Check Against Last Verdict
        last_stmt_verdict = db_state["verdict"].get("statement_date")
        last_min_verdict = db_state["verdict"].get("minutes_date")
        
        new_stmt = aligned["statement_release_date"]
        new_min = aligned["minutes_release_date"]
        
        # n8n Logic: (minutes == null && stmt != last_stmt) || (minutes != null && minutes != last_min)
        is_new_statement_only = (new_min is None) and (new_stmt is not None) and (new_stmt != last_stmt_verdict)
        is_new_minutes = (new_min is not None) and (new_min != last_min_verdict)
        
        is_new_data = is_new_statement_only or is_new_minutes
        
        # Final Trigger: "If EITHER condition is met"
        should_run = bool(force_date) or is_new_data
        
        # Construct Status Message
        if force_date:
            status_msg = f"Forced Run ({force_date})"
        elif is_new_data:
            status_msg = f"New Data Found ({target_date})"
        else:
            status_msg = f"No new data (Max: {target_date})"

        final_out = {}
        if not should_run:
            final_out = {"status": "skipped", "message": status_msg}

        return {
            "should_run": should_run, 
            "status_message": status_msg, 
            "aligned_data": aligned,
            "final_output": final_out
        }

    # --- Conditional Edge Decision ---
    def decision_should_analyze(self, state: FOMCGraphState):
        if state["should_run"]:
            return "continue"
        return "stop"

    # --- Node 4: Run Analysis ---
    @traceable(run_type="llm", name="FOMC Analysis Chain")
    def node_run_analysis(self, state: FOMCGraphState) -> Dict:
        print(f">> Node: Run Analysis ({state['status_message']})")
        inputs = state["aligned_data"]
        
        # Filter History
        raw_history = inputs.get("history", [])
        clean_history = []
        for item in raw_history:
            item_copy = item.copy()
            if 'execution_date' in item_copy:
                del item_copy['execution_date']
            clean_history.append(item_copy)

        history_json = json.dumps(clean_history, indent=2, default=str)
        
        # FIX: Changed FOMC_ANALYSIS_PROMPT to FOMC_SYSTEM_PROMPT
        full_system_text = f"{FOMC_SYSTEM_PROMPT}\n\n{self.parser.get_format_instructions()}"

        messages = [
            SystemMessage(
                content=[{
                    "type": "text", 
                    "text": full_system_text, 
                    "cache_control": {"type": "ephemeral"}
                }]
            ),
            HumanMessage(
                content=(
                    f"Minutes: {inputs.get('minutes_content') or ''}\n"
                    f"Policy Statement: {inputs.get('statement') or ''}\n"
                    f"Implementation Notes: {inputs.get('implementation_note') or ''}\n"
                    f"Projections Notes: {inputs.get('projection_note') or ''}\n"
                    f"Historical Data: {history_json}"
                )
            )
        ]

        try:
            print("Invoking Claude 3.7 Sonnet (with Caching)...")
            response = self.llm.invoke(messages)
            
            # --- Handle Thinking Blocks / Text extraction ---
            raw_content = response.content
            response_text = ""
            
            if isinstance(raw_content, str):
                response_text = raw_content
            elif isinstance(raw_content, list):
                for block in raw_content:
                    if isinstance(block, dict):
                         if block.get("type") == "text":
                            response_text += block.get("text", "")
                    elif hasattr(block, "type") and getattr(block, "type") == "text":
                         response_text += getattr(block, "text", "")
            
            if not response_text:
                raise ValueError(f"Could not extract text from response: {raw_content}")

            # Clean possible markdown code blocks
            response_text = response_text.strip()
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0]
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0]
            
            parsed_result = self.parser.parse(response_text.strip())
            return {"analysis_result": parsed_result}
            
        except Exception as e:
            print(f"Error in analysis: {e}")
            return {
                "analysis_result": None, 
                "final_output": {"status": "error", "message": str(e)}
            }

    # --- Node 5: Save Results ---
    def node_save_results(self, state: FOMCGraphState) -> Dict:
        print(">> Node: Save Results")
        result = state.get("analysis_result")
        inputs = state["aligned_data"]
        
        if not result:
            print("No analysis result to save.")
            return {}

        row_data = {
            "execution_date": datetime.now().strftime("%Y-%m-%d"),
            "statement_release_date": inputs.get("statement_release_date"),
            "implementation_note_release_date": inputs.get("implementation_note_release_date"),
            "projection_note_release_date": inputs.get("projection_note_release_date"),
            "minutes_release_date": inputs.get("minutes_release_date"),
            "content": result.model_dump(mode='json')
        }
        
        if row_data["statement_release_date"] or row_data["minutes_release_date"]:
            success = self.db.save_fomc_analysis(row_data)
            if success:
                 print(f"Successfully saved analysis for {row_data['statement_release_date'] or row_data['minutes_release_date']}")
            else:
                 print("Failed to save analysis to DB.")
            
            return {
                "final_output": {
                    "status": "success", 
                    "message": "Analysis saved",
                    "data": result.model_dump()
                }
            }
        
        print("Error: Missing primary dates (statement or minutes), cannot save.")
        return {"final_output": {"status": "error", "message": "Missing statement/minutes date"}}