// 绝不死锁的 AXI Master VIP (Verification IP)
// 包含标准的时序同步与看门狗逻辑

module tb_axi_lite_vip;
    reg clk;
    reg rst_n;
    
    // 强制 LLM 遵守的标准信号命名
    reg [31:0] S_AXI_AWADDR;
    reg S_AXI_AWVALID;
    wire S_AXI_AWREADY;
    reg [31:0] S_AXI_WDATA;
    reg [3:0] S_AXI_WSTRB;
    reg S_AXI_WVALID;
    wire S_AXI_WREADY;
    wire [1:0] S_AXI_BRESP;
    wire S_AXI_BVALID;
    reg S_AXI_BREADY;
    reg [31:0] S_AXI_ARADDR;
    reg S_AXI_ARVALID;
    wire S_AXI_ARREADY;
    wire [31:0] S_AXI_RDATA;
    wire [1:0] S_AXI_RRESP;
    wire S_AXI_RVALID;
    reg S_AXI_RREADY;

    // DUT Instantiation (要求 LLM 生成的模块名必须是 axi_lite_slave，端口严格匹配)
    axi_lite_slave dut (
        .S_AXI_ACLK(clk),
        .S_AXI_ARESETN(rst_n),
        .S_AXI_AWADDR(S_AXI_AWADDR),
        .S_AXI_AWVALID(S_AXI_AWVALID),
        .S_AXI_AWREADY(S_AXI_AWREADY),
        .S_AXI_WDATA(S_AXI_WDATA),
        .S_AXI_WSTRB(S_AXI_WSTRB),
        .S_AXI_WVALID(S_AXI_WVALID),
        .S_AXI_WREADY(S_AXI_WREADY),
        .S_AXI_BRESP(S_AXI_BRESP),
        .S_AXI_BVALID(S_AXI_BVALID),
        .S_AXI_BREADY(S_AXI_BREADY),
        .S_AXI_ARADDR(S_AXI_ARADDR),
        .S_AXI_ARVALID(S_AXI_ARVALID),
        .S_AXI_ARREADY(S_AXI_ARREADY),
        .S_AXI_RDATA(S_AXI_RDATA),
        .S_AXI_RRESP(S_AXI_RRESP),
        .S_AXI_RVALID(S_AXI_RVALID),
        .S_AXI_RREADY(S_AXI_RREADY)
    );

    always #5 clk = ~clk;

    // 严谨的时钟同步 AXI Write Task (商业级 BFM)
    task axi_write(input [31:0] addr, input [31:0] data);
        begin
            @(posedge clk);
            S_AXI_AWADDR <= addr;
            S_AXI_AWVALID <= 1;
            S_AXI_WDATA <= data;
            S_AXI_WVALID <= 1;
            S_AXI_WSTRB <= 4'hF;
            S_AXI_BREADY <= 1;

            // 等待 AWREADY
            while (!S_AXI_AWREADY) begin
                @(posedge clk);
            end
            S_AXI_AWVALID <= 0;

            // 等待 WREADY
            while (!S_AXI_WREADY) begin
                @(posedge clk);
            end
            S_AXI_WVALID <= 0;

            // 等待 BVALID
            while (!S_AXI_BVALID) begin
                @(posedge clk);
            end
            S_AXI_BREADY <= 0;
            
            $display("[VIP_LOG] Write addr=0x%08h, data=0x%08h completed", addr, data);
        end
    endtask

    // 严谨的时钟同步 AXI Read Task (商业级 BFM)
    task axi_read(input [31:0] addr, output [31:0] data);
        begin
            @(posedge clk);
            S_AXI_ARADDR <= addr;
            S_AXI_ARVALID <= 1;
            S_AXI_RREADY <= 1;

            // 等待 ARREADY
            while (!S_AXI_ARREADY) begin
                @(posedge clk);
            end
            S_AXI_ARVALID <= 0;

            // 等待 RVALID
            while (!S_AXI_RVALID) begin
                @(posedge clk);
            end
            
            data = S_AXI_RDATA;
            S_AXI_RREADY <= 0;
            
            $display("[VIP_LOG] Read addr=0x%08h, data=0x%08h completed", addr, data);
        end
    endtask

    // 测试主流程
    reg [31:0] read_data;
    
    initial begin
        clk = 0; rst_n = 0;
        S_AXI_AWADDR = 0; S_AXI_AWVALID = 0; S_AXI_WDATA = 0; S_AXI_WSTRB = 0; S_AXI_WVALID = 0; S_AXI_BREADY = 0;
        S_AXI_ARADDR = 0; S_AXI_ARVALID = 0; S_AXI_RREADY = 0;
        read_data = 0;
        
        #20 rst_n = 1;
        #10;
        
        // ----------------------------------------------------
        // LLM GENERATED SEQUENCE WILL BE INJECTED HERE
        // __LLM_STIMULUS_HERE__
        // ----------------------------------------------------
        
        $display("[SIM_SUCCESS] All VIP Stimulus Sequence Completed!");
        #10 $finish;
    end

    // Watchdog
    initial begin
        #5000;
        $display("[SIM_ERROR] Watchdog timeout - simulation deadlock. The VIP waited too long for a ready/valid signal.");
        $finish;
    end

endmodule
