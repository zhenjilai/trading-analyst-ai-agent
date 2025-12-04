# import sys
# from pathlib import Path
# sys.path.insert(0, str(Path.cwd().parent))
import json
import os
from datetime import datetime
from typing import Dict, Optional, Any, List, TypedDict, Annotated

# --- LangChain & LangGraph Imports ---
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.messages import SystemMessage, HumanMessage
from langgraph.graph import StateGraph, END
from langsmith import traceable

from config.settings import settings
from src.llm.claude_client import get_claude_client
from src.prompt_engineering.templates import FOMC_SYSTEM_PROMPT

from .fomc_fetchers import fetch_all_fomc_data
from .fomc_database import FOMCDatabase
from .fomc_models import FOMCAnalysisOutput


# --- State Definition ---
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
        # 1. Setup Database
        self.db = FOMCDatabase(settings.db_connection_params)
        
        # 2. Setup LangSmith (Observability)
        if langsmith_api_key:
            os.environ["LANGSMITH_TRACING"] = "true"
            os.environ["LANGSMITH_ENDPOINT"] = "https://api.smith.langchain.com"
            os.environ["LANGSMITH_API_KEY"] = langsmith_api_key
            os.environ["LANGSMITH_PROJECT"] = "fomc-analysis-agent"
            print("✓ LangSmith Tracing Enabled")

        # 3. Setup LangChain LLM (Claude 3.7 Sonnet / "Sonnet 4")
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

        # 1. Statement
        stmt_date = fetched['statement'].get('new_release_date')
        if stmt_date and is_valid_date(stmt_date):
            self.db.upsert_statement(stmt_date, fetched['statement']['statement'])
        elif stmt_date:
            print(f"Skipped Statement Save: {stmt_date} is in the future.")

        # 2. Minutes
        min_date = fetched['minutes'].get('new_release_date')
        if min_date and is_valid_date(min_date):
            self.db.upsert_minutes(min_date, fetched['minutes']['minutes'])
        elif min_date:
            print(f"Skipped Minutes Save: {min_date} is in the future.")

        # 3. Projection
        proj_date = fetched['projection_note'].get('new_release_date')
        if proj_date and is_valid_date(proj_date):
            self.db.upsert_projection_note(proj_date, fetched['projection_note']['projection_note'])
        elif proj_date:
            print(f"Skipped Projection Save: {proj_date} is in the future.")

        # 4. Implementation Note
        impl_date = fetched['implementation_note'].get('new_release_date')
        if impl_date and is_valid_date(impl_date):
            self.db.upsert_implementation_note(impl_date, fetched['implementation_note']['implementation_note'])
        elif impl_date:
            print(f"Skipped Implementation Save: {impl_date} is in the future.")
            
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
        
        # Extract DB Dates
        d_min = db_state["minutes_date"]
        d_stmt = db_state["statement_date"]
        d_impl = db_state["implementation_date"]
        d_proj = db_state["projection_date"]

        # Find Max Date
        valid_dates = [d for d in [d_min, d_stmt, d_impl, d_proj] if d]
        if not valid_dates:
            return {
                "should_run": False, 
                "status_message": "No data in DB",
                "final_output": {"status": "skipped", "message": "No data found"}
            }
        
        max_date = max(valid_dates)
        
        # Helper to get content from fetch_results if dates match
        def get_content_from_fetch(key, subkey, target_date):
            fetched_item = fetched_results.get(key, {})
            if fetched_item.get("new_release_date") == target_date:
                return fetched_item.get(subkey)
            return None

        # Align Data
        aligned = {
            "max_release_date": max_date,
            "minutes_release_date": d_min if d_min == max_date else None,
            "minutes_content": get_content_from_fetch("minutes", "minutes", max_date) if d_min == max_date else None,
            "statement_release_date": d_stmt if d_stmt == max_date else None,
            "statement": get_content_from_fetch("statement", "statement", max_date) if d_stmt == max_date else None,
            "implementation_note_release_date": d_impl if d_impl == max_date else None,
            "implementation_note": get_content_from_fetch("implementation_note", "implementation_note", max_date) if d_impl == max_date else None,
            "projection_note_release_date": d_proj if d_proj == max_date else None,
            "projection_note": get_content_from_fetch("projection_note", "projection_note", max_date) if d_proj == max_date else None,
            "history": db_state["history"]
        }

        # Check Against Last Verdict
        last_stmt = db_state["verdict"].get("statement_date")
        last_min = db_state["verdict"].get("minutes_date")
        
        minutes_rel = aligned["minutes_release_date"]
        stmt_rel = aligned["statement_release_date"]
        
        should_run = False
        reason = "No new updates"

        if minutes_rel is None:
            if stmt_rel and stmt_rel != last_stmt:
                should_run = True
                reason = f"New Statement ({stmt_rel})"
        else:
            if minutes_rel != last_min:
                should_run = True
                reason = f"New Minutes ({minutes_rel})"

        final_out = {}
        if not should_run:
            final_out = {"status": "skipped", "message": "Database up to date"}

        return {
            "should_run": should_run, 
            "status_message": reason, 
            "aligned_data": aligned,
            "final_output": final_out
        }

    # --- Conditional Edge Decision ---
    def decision_should_analyze(self, state: FOMCGraphState):
        if state["should_run"]:
            return "continue"
        return "stop"

    # --- Node 4: Run Analysis (FIXED for Thinking Blocks) ---
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
        
        full_system_text = f"{FOMC_ANALYSIS_PROMPT}\n\n{self.parser.get_format_instructions()}"

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
            
            # --- FIX: Handle List Content (Thinking Blocks) ---
            raw_content = response.content
            response_text = ""
            
            if isinstance(raw_content, str):
                response_text = raw_content
            elif isinstance(raw_content, list):
                # Iterate through blocks and extract text
                for block in raw_content:
                    # Check for dict (standard API) or object
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
        
        # Ensure we have a primary key (statement date is usually the anchor)
        # If statement date is missing but we have minutes, use minutes date as fallback or error out depending on DB constraints.
        # Your DB schema uses statement_date as PK for analysis.
        
        if row_data["statement_release_date"]:
            success = self.db.save_fomc_analysis(row_data)
            if success:
                 print(f"Successfully saved analysis for {row_data['statement_release_date']}")
            else:
                 print("Failed to save analysis to DB.")
            
            return {
                "final_output": {
                    "status": "success", 
                    "message": "Analysis saved",
                    "data": result.model_dump()
                }
            }
        
        print("Error: Missing statement date, cannot save analysis.")
        return {"final_output": {"status": "error", "message": "Missing statement date"}}




# import sys
# from pathlib import Path
# sys.path.insert(0, str(Path.cwd().parent))
# from config import get_config, FOMC_ANALYSIS_PROMPT
# from typing import TypedDict, Annotated, Dict, List, Optional, Any
# from datetime import datetime
# import operator
# from langchain_core.output_parsers import PydanticOutputParser
# from langgraph.graph import StateGraph, END
# from langsmith import Client, traceable
# import os
# import json
# from .fomc_models import FOMCAnalysisOutput
# from .fomc_fetchers import (
#     StatementFetcher,
#     MinutesFetcher,
#     ProjectionNoteFetcher,
#     ImplementationNoteFetcher
# )
# from .fomc_database import FOMCDatabase
# from anthropic import Anthropic


# class FOMCWorkflowState(TypedDict):
#     """State for the FOMC analysis workflow"""
#     target_date: str   # in YYYYMMDD format
    
#     # Raw Fetch Results (Lists for parallel execution)
#     statement_data: Annotated[List[Optional[Dict]], operator.add]
#     minutes_data: Annotated[List[Optional[Dict]], operator.add]
#     projection_data: Annotated[List[Optional[Dict]], operator.add]
#     implementation_data: Annotated[List[Optional[Dict]], operator.add]
    
#     # Processed/Aligned Data (Single Dicts)
#     aligned_statement: Optional[Dict]
#     aligned_minutes: Optional[Dict]
#     aligned_projection: Optional[Dict]
#     aligned_implementation: Optional[Dict]
#     max_release_date: Optional[str]

#     # Logic Flags
#     should_run_analysis: bool
    
#     # Context & Analysis
#     historical_data: Optional[List[Dict]]
#     combined_prompt_text: str
#     analysis_result: Optional[FOMCAnalysisOutput]
    
#     # Logging
#     errors: Annotated[List[str], operator.add]
#     logs: Annotated[List[str], operator.add]


# class FOMCAnalysisWorkflow:
#     """FOMC Analysis Workflow using LangGraph"""
    
#     def __init__(
#         self,
#         anthropic_api_key: str,
#         db_connection_params: Dict,
#         langsmith_api_key: Optional[str] = None,
#         prompt_template: Optional[str] = None,
#         enable_streaming: bool=True
#     ):
#         """
#         Initialize the FOMC Analysis Workflow
        
#         Args:
#             anthropic_api_key: Anthropic API key
#             db_connection_params: PostgreSQL connection parameters
#             langsmith_api_key: LangSmith API key for observability (optional)
#             prompt_template: Custom prompt template (optional)
#         """
#         # Initialize components
#         self.db = FOMCDatabase(db_connection_params)
        
#         # Initialize fetchers
#         self.fetchers = {
#             "statement": StatementFetcher(),
#             "minutes": MinutesFetcher(),
#             "projection": ProjectionNoteFetcher(),
#             "implementation": ImplementationNoteFetcher()
#         }
        
#         # Initialize Anthropic client (using raw SDK)
#         self.anthropic_client = Anthropic(api_key=anthropic_api_key)
#         self.model = "claude-sonnet-4-20250514"
#         self.enable_streaming = enable_streaming

#         self.parser = PydanticOutputParser(pydantic_object=FOMCAnalysisOutput)
#         self.prompt_template = prompt_template or FOMC_ANALYSIS_PROMPT

#         if langsmith_api_key:
#             os.environ["LANGSMITH_API_KEY"] = langsmith_api_key
#             os.environ["LANGSMITH_TRACING"] = "true"
#             os.environ["LANGSMITH_PROJECT"] = "fomc-analysis"
#             try:
#                 self.langsmith_client = Client()
#                 print("✅ LangSmith tracing enabled.")
#             except Exception as e:
#                 print(f"⚠️ Failed to initialize LangSmith client: {e}")
#                 self.langsmith_client = None
#         else:
#             self.langsmith_client = None
        
#         # Build the workflow graph
#         self.workflow = self._build_workflow()

    
#     def _build_workflow(self) -> StateGraph:
#         """Build the LangGraph workflow with parallel fetching"""
#         workflow = StateGraph(FOMCWorkflowState)
        
#         # 1. Parallel Fetching
#         workflow.add_node("fetch_statement", self.fetch_statement)
#         workflow.add_node("fetch_minutes", self.fetch_minutes)
#         workflow.add_node("fetch_projection", self.fetch_projection)
#         workflow.add_node("fetch_implementation", self.fetch_implementation)
        
#         # 2. Logic Processing (Date Align + Check Logic)
#         workflow.add_node("align_and_check", self.align_and_check_updates)
        
#         # 3. Preparation (Conditional)
#         workflow.add_node("fetch_history", self.fetch_history)
#         workflow.add_node("generate_prompt", self.generate_prompt)
        
#         # 4. Execution
#         workflow.add_node("run_analysis", self.run_analysis)
        
#         # 5. Commit (Save Raw + Analysis)
#         workflow.add_node("save_results", self.save_results)
        
#         # -- Edges --
#         workflow.set_entry_point("fetch_statement")
        
#         # Fan out
#         workflow.add_edge("fetch_statement", "fetch_minutes")
#         workflow.add_edge("fetch_statement", "fetch_projection")
#         workflow.add_edge("fetch_statement", "fetch_implementation")
        
#         # Fan in
#         workflow.add_edge("fetch_minutes", "align_and_check")
#         workflow.add_edge("fetch_projection", "align_and_check")
#         workflow.add_edge("fetch_implementation", "align_and_check")
        
#         # Conditional Branching
#         workflow.add_conditional_edges(
#             "align_and_check",
#             self._check_condition,
#             {
#                 "proceed": "fetch_history",
#                 "stop": END
#             }
#         )
        
#         workflow.add_edge("fetch_history", "generate_prompt")
#         workflow.add_edge("generate_prompt", "run_analysis")
#         workflow.add_edge("run_analysis", "save_results")
#         workflow.add_edge("save_results", END)
        
#         return workflow.compile()
    
#     def fetch_statement(self, state: FOMCWorkflowState):
#         """Fetch FOMC statement"""
#         print("Fetching FOMC statement...")
#         try:
#             dt = state.get("target_date")
#             return {"statement_data": [self.fetchers["statement"].fetch(dt)]}
#         except Exception as e:
#             return {
#                 "errors": [f"Error fetching statement: {str(e)}"],
#                 "statement_data": [None]
#             }

#     def fetch_minutes(self, state: FOMCWorkflowState):
#         """Fetch FOMC minutes"""
#         print("Fetching FOMC minutes...")
#         try:
#             dt = state.get("target_date")
#             return {"minutes_data": [self.fetchers["minutes"].fetch(dt)]}
#         except Exception as e:
#             return {
#                 "errors": [f"Error fetching minutes: {str(e)}"],
#                 "minutes_data": [None]
#             }

#     def fetch_projection(self, state: FOMCWorkflowState):
#         """Fetch FOMC projection note"""
#         print("Fetching FOMC projection note...")
#         try:
#             dt = state.get("target_date")
#             return {"projection_data": [self.fetchers["projection"].fetch(dt)]}
#         except Exception as e:
#             return {
#                 "errors": [f"Error fetching projection: {str(e)}"],
#                 "projection_data": [None]
#             }

#     def fetch_implementation(self, state: FOMCWorkflowState):
#         """Fetch FOMC implementation note"""
#         print("Fetching FOMC implementation note...")
#         try:
#             dt = state.get("target_date")
#             return {"implementation_data": [self.fetchers["implementation"].fetch(dt)]}
#         except Exception as e:
#             return {
#                 "errors": [f"Error fetching implementation: {str(e)}"],
#                 "implementation_data": [None]
#             }
    
#     def align_and_check_updates(self, state: FOMCWorkflowState):
#         """
#         Replicates n8n 'Date Align' and 'Check If FOMC Data Exists' nodes.
#         """
#         # Helper to safely get the last item or None
#         def get_last(data_list):
#             return data_list[-1] if data_list else None

#         raw_stmt = get_last(state["statement_data"])
#         raw_min = get_last(state["minutes_data"])
#         raw_proj = get_last(state["projection_data"])
#         raw_impl = get_last(state["implementation_data"])
        
#         # 2. Date Align Logic (Knockout non-max dates)
#         dates = []
#         if raw_stmt and raw_stmt.get("new_release_date"): dates.append(raw_stmt["new_release_date"])
#         if raw_min and raw_min.get("new_release_date"): dates.append(raw_min["new_release_date"])
#         if raw_proj and raw_proj.get("new_release_date"): dates.append(raw_proj["new_release_date"])
#         if raw_impl and raw_impl.get("new_release_date"): dates.append(raw_impl["new_release_date"])
        
#         if not dates:
#             return {"should_run_analysis": False, "logs": ["No dates found in fetched data."]}
            
#         max_date_str = max(dates)
        
#         def knockout(data_dict):
#             if not data_dict or data_dict.get("new_release_date") != max_date_str:
#                 return None
#             return data_dict
            
#         aligned_stmt = knockout(raw_stmt)
#         aligned_min = knockout(raw_min)
#         aligned_proj = knockout(raw_proj)
#         aligned_impl = knockout(raw_impl)

#         # 3. Check Against Database Logic
#         db_stmt_date = self.db.get_latest_statement_date()
#         db_min_date = self.db.get_latest_minutes_date()
        
#         # Corresponds to n8n vars
#         minutes_rel = aligned_min.get("new_release_date") if aligned_min else None
#         stmt_rel = aligned_stmt.get("new_release_date") if aligned_stmt else None
        
#         is_new = False
        
#         # n8n Logic: (minutesRel == null && stmtDate !== stmtRelease) || (minutesRel != null && minutesRel !== minutesDate)
#         if minutes_rel is None:
#             # Case A: No new minutes, check if statement changed
#             if stmt_rel and stmt_rel != db_stmt_date:
#                 is_new = True
#         else:
#             # Case B: Minutes exist, check if minutes changed
#             if minutes_rel != db_min_date:
#                 is_new = True

#         return {
#             "aligned_statement": aligned_stmt,
#             "aligned_minutes": aligned_min,
#             "aligned_projection": aligned_proj,
#             "aligned_implementation": aligned_impl,
#             "max_release_date": max_date_str,
#             "should_run_analysis": is_new,
#             "logs": [f"Max Date: {max_date_str}, New Data Detected: {is_new}"]
#         }

#     def _check_condition(self, state: FOMCWorkflowState):
#         if state["should_run_analysis"]:
#             return "proceed"
#         return "stop"
    
#     def fetch_history(self, state: FOMCWorkflowState) -> Dict:
#         """Fetch historical FOMC data from database (last 6 months verdicts)"""
#         print("Fetching historical data from database...")
#         try:
#             # Get last 6 months of FOMC verdicts from database
#             history = self.db.get_six_months_fomc_verdict()
            
#             if history:
#                 print(f"  ✓ Retrieved {len(history)} historical verdicts")
#                 return {"historical_data": history}
#             else:
#                 print("  ℹ No historical data available")
#                 return {"historical_data": [None]}
                
#         except Exception as e:
#             return {
#                 "errors": [f"Error fetching historical data: {str(e)}"],
#                 "historical_data": [None]
#             }
            
#     def generate_prompt(self, state: FOMCWorkflowState):
#         parts = []
#         # Order similar to n8n prompt construction
#         if state["aligned_minutes"]:
#             parts.append(f"FOMC MINUTES:\n{state['aligned_minutes'].get('meeting_content', '')}")
#         if state["aligned_statement"]:
#             parts.append(f"FOMC STATEMENT:\n{state['aligned_statement'].get('statement', '')}")
#         if state["aligned_implementation"]:
#             parts.append(f"IMPLEMENTATION NOTE:\n{state['aligned_implementation'].get('implementation_note', '')}")
#         if state["aligned_projection"]:
#             parts.append(f"PROJECTION MATERIALS:\n{state['aligned_projection'].get('projection_note', '')}")
#         if state["historical_data"]:
#             parts.append(f"HISTORICAL DATA:\n{json.dumps(state['historical_data'], indent=2, default=str)}")
            
#         return {"combined_prompt_text": "\n\n".join(parts)}
    
#     def save_results(self, state: FOMCWorkflowState):
#         """
#         Saves EVERYTHING at the end.
#         1. Upserts Raw Documents.
#         2. Upserts Analysis Result (Replacing whole row based on statement_date).
#         """
#         print("Saving data to database...")
#         errors = []
        
#         with self.db.get_connection() as conn:
#             try:
#                 # 1. Save Raw Docs (Upsert)
#                 if state["aligned_statement"]:
#                     self.db.upsert_statement(state["aligned_statement"]["new_release_date"], state["aligned_statement"]["statement"], conn)
#                 if state["aligned_minutes"]:
#                     self.db.upsert_minutes(state["aligned_minutes"]["new_release_date"], state["aligned_minutes"]["meeting_content"], conn)
#                 if state["aligned_projection"]:
#                     self.db.upsert_projection_note(state["aligned_projection"]["new_release_date"], state["aligned_projection"]["projection_note"], conn)
#                 if state["aligned_implementation"]:
#                     self.db.upsert_implementation_note(state["aligned_implementation"]["new_release_date"], state["aligned_implementation"]["implementation_note"], conn)
                
#                 # 2. Save Analysis
#                 if state["analysis_result"]:
#                     analysis_dict = state["analysis_result"].model_dump()
                    
#                     # Data structure matching n8n output
#                     row_data = {
#                         "execution_date": datetime.now().strftime("%Y-%m-%d"),
#                         "statement_release_date": state["aligned_statement"]["new_release_date"] if state["aligned_statement"] else None,
#                         "implementation_note_release_date": state["aligned_implementation"]["new_release_date"] if state["aligned_implementation"] else None,
#                         "projection_note_release_date": state["aligned_projection"]["new_release_date"] if state["aligned_projection"] else None,
#                         "minutes_release_date": state["aligned_minutes"]["new_release_date"] if state["aligned_minutes"] else None,
#                         "content": analysis_dict
#                     }
                    
#                     # Statement date is required as Primary Key
#                     if row_data["statement_release_date"]:
#                         self.db.save_fomc_analysis(row_data, conn)
#                     else:
#                         errors.append("Cannot save analysis: Missing statement date (Primary Key).")
                
#             except Exception as e:
#                 errors.append(f"Transaction failed: {str(e)}")
                
#         return {"errors": errors, "logs": ["Data save transaction complete."]}
    
#     @traceable(run_type="llm", name="FOMC Analysis")
#     def run_analysis(self, state: FOMCWorkflowState) -> Dict:
#         """Run the FOMC analysis using Claude"""
#         user_content_text = f"{state['combined_prompt_text']}\n\n{self.parser.get_format_instructions()}"
        
#         print("Sending request to Claude (Thinking + Caching enabled)...")
        
#         try:
#             if self.enable_streaming:
#                 response_text = ""
                
#                 with self.anthropic_client.messages.create(
#                     model=self.model,
#                     stream=True,
#                     max_tokens=64000,
#                     thinking={
#                         "type": "enabled",
#                         "budget_tokens": 20000
#                     },
#                     system=[{
#                         "type": "text",
#                         "text": self.prompt_template,
#                         "cache_control": {"type": "ephemeral"}
#                     }],
#                     messages=[{
#                         "role": "user",
#                         "content": [{
#                             "type": "text",
#                             "text": user_content_text,
#                             "cache_control": {"type": "ephemeral"}
#                         }]
#                     }]
#                 ) as stream:
#                     for event in stream:
#                         # We only care about text deltas (ignoring thinking deltas)
#                         if event.type == "content_block_delta" and event.delta.type == "text_delta":
#                             response_text += event.delta.text
                
#                 print("\n✓ Streaming complete")
                
#             else:
#                 print("Using non-streaming mode...")
#                 response = self.anthropic_client.messages.create(
#                     model=self.model,
#                     max_tokens=64000,
#                     thinking={
#                         "type": "enabled",
#                         "budget_tokens": 20000
#                     },
#                     system=[{
#                         "type": "text",
#                         "text": self.prompt_template,
#                         "cache_control": {"type": "ephemeral"}
#                     }],
#                     messages=[{
#                         "role": "user",
#                         "content": [{
#                             "type": "text",
#                             "text": user_content_text,
#                             "cache_control": {"type": "ephemeral"}
#                         }]
#                     }]
#                 )
                
#                 response_text = ""
#                 for block in response.content:
#                     if block.type == "text":
#                         response_text += block.text
            
#             if not response_text:
#                 raise ValueError("No text response from Claude")
            
#             # Strip markdown code fences if present
#             response_text = response_text.strip()
#             if response_text.startswith("```json"):
#                 response_text = response_text[7:]  # Remove ```json
#             elif response_text.startswith("```"):
#                 response_text = response_text[3:]  # Remove ```
#             if response_text.endswith("```"):
#                 response_text = response_text[:-3]  # Remove trailing ```
#             response_text = response_text.strip()
            
#             # Parse into Pydantic model
#             print("Parsing response...")
#             result = self.parser.parse(response_text)
            
#             print("✓ Analysis completed successfully")
#             return {"analysis_result": result}
            
#         except Exception as e:
#             print(f"✗ Error in analysis: {str(e)}")
#             return {
#                 "errors": [f"Error running analysis: {str(e)}"],
#                 "analysis_result": None
#             }
    
#     def run(self, meeting_date: str) -> Dict:
#         """
#         Run the complete FOMC analysis workflow
        
#         Args:
#             meeting_date: Meeting date in YYYYMMDD format
            
#         Returns:
#             Dict containing the analysis result and any errors
#         """
#         target_date = meeting_date if meeting_date else datetime.now().strftime("%Y%m%d")
#         print(f"Starting FOMC analysis workflow for meeting date: {meeting_date}")
        
#         # Initialize state
#         initial_state = {
#             "target_date": meeting_date,
#             "statement_data": [],
#             "minutes_data": [],
#             "projection_data": [],
#             "implementation_data": [],
#             "errors": [],
#             "logs": []
#         }

#         result = self.workflow.invoke(initial_state)
#         return result
