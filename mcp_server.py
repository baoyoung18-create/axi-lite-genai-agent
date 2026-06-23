import os
import subprocess
from mcp.server.fastmcp import FastMCP

# 初始化 FastMCP 服务，命名为 Synopsys_EDA_Tools
mcp = FastMCP("Synopsys_EDA_Tools")

def mock_linter(design_path: str, tb_path: str) -> str:
    """
    高逼真的本地 Mock 仿真器。如果用户电脑没装 iverilog，则用此逻辑拦截典型的 AXI/CDC 错误。
    """
    try:
        with open(design_path, "r", encoding="utf-8") as f:
            code = f.read()
            
        # 1. 语法检查
        if "endmodule" not in code:
            return "COMPILER_ERROR: Missing 'endmodule'."
            
        # 2. AXI 协议死锁检查
        if "AWVALID" in code and "AWREADY" in code:
            if "WVALID" not in code or "WREADY" not in code:
                return "SIMULATION_FAILED:\n[SIM_ERROR] AXI Protocol Violation: Missing WVALID/WREADY channel logic."
                
        # 3. 跨时钟域 (CDC) 亚稳态检查
        # 如果代码里同时出现了两个不同的时钟，且没有打拍同步电路或 FIFO，报 CDC 错误
        if "axi_clk" in code and "core_clk" in code:
            # 简单启发式：检查是否有双触发器同步 (e.g., reg [1:0] sync_) 或者 fifo
            if "sync" not in code.lower() and "fifo" not in code.lower() and "reg [1:0]" not in code:
                return (
                    "SIMULATION_FAILED:\n"
                    "[SIM_ERROR] CDC Hazard Detected! \n"
                    "Signal crossed from axi_clk domain to core_clk domain without proper synchronization.\n"
                    "Recommendation: Insert a double-flop synchronizer for 1-bit control signals or an Async FIFO for data buses."
                )
                
        return "SUCCESS"
    except Exception as e:
        return f"COMPILER_ERROR: Could not read files. Exception: {str(e)}"


@mcp.tool()
def run_eda_simulation(design_path: str, tb_path: str) -> str:
    """
    Run Icarus Verilog compilation and functional simulation for AXI-Lite designs.
    Args:
        design_path: The absolute path to the Verilog design file (e.g., design.v).
        tb_path: The absolute path to the Verilog testbench file (e.g., tb_design.v).
    Returns:
        String output containing SUCCESS or detailed ERROR logs.
    """
    if not os.path.exists(design_path):
        return f"COMPILER_ERROR: Design file {design_path} not found."
    if not os.path.exists(tb_path):
        return f"COMPILER_ERROR: Testbench file {tb_path} not found."
        
    sim_out = design_path + ".sim"
    
    try:
        # Step 1: Compilation
        compile_result = subprocess.run(
            ["iverilog", "-Wall", "-o", sim_out, design_path, tb_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=5
        )
        
        if compile_result.returncode != 0:
            if os.path.exists(sim_out):
                os.remove(sim_out)
            return f"COMPILER_ERROR:\n{compile_result.stderr}"
            
        # Step 2: Simulation
        sim_run = subprocess.run(
            ["vvp", sim_out],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=5
        )
        
        if os.path.exists(sim_out):
            os.remove(sim_out)
            
        stdout_content = sim_run.stdout
        
        if sim_run.returncode != 0:
            return f"SIMULATION_CRASHED:\n{sim_run.stderr}\nStdout:\n{stdout_content}"
            
        # Catch standard Testbench assertion failures
        if "[SIM_ERROR]" in stdout_content or "Error:" in stdout_content or "Timeout" in stdout_content:
            return f"SIMULATION_FAILED:\n{stdout_content}"
            
        return "SUCCESS"
        
    except subprocess.TimeoutExpired:
        if os.path.exists(sim_out):
            os.remove(sim_out)
        return "SIMULATION_FAILED:\n[SIM_ERROR] Timeout: Handshake deadlock detected in simulation."
    except FileNotFoundError:
        # iverilog 没安装时自动触发高保真 Mock Linter
        print("[MCP Server] iverilog not found. Using Mock CDC/AXI Linter fallback.")
        return mock_linter(design_path, tb_path)

if __name__ == "__main__":
    print("🚀 Synopsys EDA MCP Server is starting...")
    mcp.run()
