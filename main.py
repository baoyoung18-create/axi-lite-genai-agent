import os
import sys
# Force stdout to use UTF-8 to prevent UnicodeEncodeError in non-UTF-8 terminals
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

from agent import app


def main():
    print("====================================================")
    print("   AXI-Lite GenAI Agent (with Self-Healing Loop)    ")
    print("====================================================")
    
    spec_sync = """
给我生成一个标准的 AXI4-Lite 模块。地址 0x00 是可读可写的控制寄存器，最低位控制 start；地址 0x04 是只读的 status 寄存器；地址 0x08 到 0x14 是 4 个连续的参数寄存器
"""
    
    spec_cdc = """
Create an AXI4-Lite Slave.
The AXI bus runs on 'axi_clk' (and reset 'axi_rst_n').
The core logic runs on 'core_clk'.
Address 0x00 is a 1-bit Control Register (Read/Write) named 'start_engine'. 
Ensure you synchronize 'start_engine' into the 'core_clk' domain to avoid CDC hazards.
"""
    
    print("Choose a test specification:")
    print("1. Standard Sync AXI-Lite")
    print("2. Async CDC AXI-Lite (Cross Clock Domain)")
    choice = input("Enter 1 or 2 [Default: 2]: ")
    
    spec = spec_sync if choice.strip() == "1" else spec_cdc
    
    print("\n[User Specification]")
    print(spec)
    print("-" * 50)
    
    initial_state = {
        "user_spec": spec,
        "design_code": "",
        "sequence_code": "",
        "error_logs": "",
        "attempts": 0,
        "status": ""
    }
    
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    
    for s in app.stream(initial_state):
        pass

    print("\n[FINISHED] Agent execution finished.")
    print("Check 'design.v' and 'tb_design.v' for the final output.")

if __name__ == "__main__":
    main()
