import os
import json
import re
from typing import TypedDict, Dict, Any
from langgraph.graph import StateGraph, END
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

import config
import prompts
from mcp_server import run_eda_simulation

class AgentState(TypedDict):
    user_spec: str
    design_code: str
    sequence_code: str  # Stores the raw JSON sequence block
    error_logs: str
    attempts: int
    status: str

def get_llm():
    if not config.API_KEY:
        print("[WARNING] DEEPSEEK_API_KEY is not set. The LLM calls might fail if not using local Ollama.")
    return ChatOpenAI(
        base_url=config.BASE_URL,
        api_key=config.API_KEY or "dummy_key",
        model=config.MODEL,
        temperature=0.1
    )

def format_verilog_val(val_str: str) -> str:
    val_str = val_str.strip()
    if not val_str:
        return "32'h0"
    if "'" in val_str:
        return val_str
    if val_str.lower().startswith("0x"):
        hex_part = val_str[2:]
        return f"32'h{hex_part}"
    if val_str.isdigit():
        return f"32'd{val_str}"
    return val_str

def parse_json_to_verilog(json_str: str) -> str:
    if not json_str.strip():
        return "// Warning: Empty JSON sequence"
    
    cleaned = json_str.strip()
    
    # Remove single-line comments (e.g. // or # comments)
    cleaned = re.sub(r'//.*$', '', cleaned, flags=re.MULTILINE)
    cleaned = re.sub(r'#.*$', '', cleaned, flags=re.MULTILINE)
    
    # Remove trailing commas before closing brackets/braces
    cleaned = re.sub(r',\s*([\]}])', r'\1', cleaned)
    
    try:
        data = json.loads(cleaned)
    except Exception as e:
        # Fallback: extract array using start/end brackets
        try:
            start_idx = cleaned.find('[')
            end_idx = cleaned.rfind(']')
            if start_idx != -1 and end_idx != -1:
                cleaned = cleaned[start_idx:end_idx+1]
                data = json.loads(cleaned)
            else:
                raise e
        except Exception as e2:
            print(f"[JSON Parsing Error] {e2}. Raw content:\n{json_str}")
            return f"// JSON Parsing Error: {str(e2)}"
            
    if not isinstance(data, list):
        return "// Warning: JSON sequence is not a list."
        
    verilog_lines = []
    for item in data:
        if not isinstance(item, dict):
            continue
        # Support synonyms for type/operation/action
        t = (item.get("type") or item.get("operation") or item.get("action") or "").lower()
        # Support synonyms for addr/address
        addr = str(item.get("addr") or item.get("address") or "")
        
        addr_fmt = format_verilog_val(addr)
        
        if t in ("write", "axi_write"):
            data_val = str(item.get("data", "0"))
            data_fmt = format_verilog_val(data_val)
            verilog_lines.append(f"axi_write({addr_fmt}, {data_fmt});")
        elif t in ("read", "axi_read"):
            verilog_lines.append(f"axi_read({addr_fmt}, read_data);")

            
    return "\n        ".join(verilog_lines)

def _extract_code(content: str, tag: str) -> str:
    start = f"```{tag}"
    if start in content:
        try:
            return content.split(start)[1].split("```")[0].strip()
        except:
            pass
    # Fallback to json if json_seq requested but they just outputted json block
    if tag == "json_seq":
        start_json = "```json"
        if start_json in content:
            try:
                return content.split(start_json)[1].split("```")[0].strip()
            except:
                pass
    return ""

def generate_node(state: AgentState) -> Dict[str, Any]:
    print("\n[Generate Node] -> Generating AXI-Lite Design and Test Sequence...")
    llm = get_llm()
    msg = [
        SystemMessage(content=prompts.GENERATE_SYSTEM_PROMPT),
        HumanMessage(content=f"User Specification:\n{state['user_spec']}")
    ]
    response = llm.invoke(msg)
    design = _extract_code(response.content, "verilog_design")
    seq = _extract_code(response.content, "json_seq")
    
    print(f"Parsed raw json_seq:\n{seq}\n")
    return {
        "design_code": design,
        "sequence_code": seq,
        "attempts": 1,
        "status": "validating"
    }

def validate_node(state: AgentState) -> Dict[str, Any]:
    print("\n[Validate Node] -> Parsing JSON Sequence to Verilog and running simulation...")
    
    if not state["design_code"] or not state["design_code"].strip():
        print("[FAILED] Validation FAILED: Missing design code!")
        return {
            "status": "failed",
            "error_logs": "COMPILER_ERROR: The design block ```verilog_design``` is missing or empty. You must output the full Verilog RTL for the design."
        }
        
    if not state["sequence_code"] or not state["sequence_code"].strip():
        print("[FAILED] Validation FAILED: Missing test sequence!")
        return {
            "status": "failed",
            "error_logs": "COMPILER_ERROR: The test sequence block ```json_seq``` is missing or empty. You must output the test sequence as a JSON array of objects representing write and read operations to verify the registers."
        }

    design_path = os.path.abspath("design.v")
    tb_path = os.path.abspath("tb_design.v")
    template_path = os.path.abspath("tb_template.v")
    
    with open(design_path, "w", encoding="utf-8") as f: 
        f.write(state["design_code"])

        
    # Translate the JSON sequence to Verilog tasks
    verilog_seq = parse_json_to_verilog(state["sequence_code"])
    print(f"--- Mapped Verilog Sequence ---:\n{verilog_seq}\n--------------------------------")
    
    # Assemble the final TB using VIP Template + Parsed Sequence
    with open(template_path, "r", encoding="utf-8") as f:
        template = f.read()
    
    final_tb = template.replace("// __LLM_STIMULUS_HERE__", verilog_seq)
    with open(tb_path, "w", encoding="utf-8") as f:
        f.write(final_tb)
    
    result = run_eda_simulation(design_path, tb_path)
    
    if result == "SUCCESS":
        print("[PASSED] Compilation & Simulation PASSED!")
        return {"status": "success", "error_logs": ""}
    else:
        print(f"[FAILED] Validation FAILED:\n{result}")
        return {"status": "failed", "error_logs": result}

def refine_node(state: AgentState) -> Dict[str, Any]:
    print(f"\n[Refine Node] -> Self-Healing (Attempt {state['attempts']})...")
    llm = get_llm()
    msg = [
        SystemMessage(content=prompts.REFINE_SYSTEM_PROMPT),
        HumanMessage(content=(
            f"Spec: {state['user_spec']}\n"
            f"Incorrect Design:\n```verilog_design\n{state['design_code']}\n```\n"
            f"Incorrect Sequence:\n```json_seq\n{state['sequence_code']}\n```\n"
            f"Errors:\n{state['error_logs']}\nFix the bug."
        ))
    ]
    response = llm.invoke(msg)
    design = _extract_code(response.content, "verilog_design") or state["design_code"]
    seq = _extract_code(response.content, "json_seq") or state["sequence_code"]
    
    print(f"Parsed refined json_seq:\n{seq}\n")
    return {
        "design_code": design,
        "sequence_code": seq,
        "attempts": state["attempts"] + 1,
        "status": "validating"
    }


def router(state: AgentState) -> str:
    if state["status"] == "success":
        return "end"
    if state["attempts"] >= config.MAX_RETRY_ATTEMPTS:
        print(f"\n[WARNING] Max retries reached ({config.MAX_RETRY_ATTEMPTS}). Stopping.")
        return "end"
    return "refine"

workflow = StateGraph(AgentState)
workflow.add_node("generate", generate_node)
workflow.add_node("validate", validate_node)
workflow.add_node("refine", refine_node)

workflow.set_entry_point("generate")
workflow.add_edge("generate", "validate")
workflow.add_edge("refine", "validate")
workflow.add_conditional_edges("validate", router, {"end": END, "refine": "refine"})

app = workflow.compile()
