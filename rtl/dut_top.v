// Verification wrapper: PicoRV32 configured as RV32IM with the RVFI trace port enabled.
// Memory is modelled by the cocotb testbench on the native mem_* interface.
module dut_top (
    input  wire        clk,
    input  wire        resetn,
    output wire        trap,
    output wire        mem_valid,
    output wire        mem_instr,
    input  wire        mem_ready,
    output wire [31:0] mem_addr,
    output wire [31:0] mem_wdata,
    output wire [ 3:0] mem_wstrb,
    input  wire [31:0] mem_rdata,
    output wire        rvfi_valid,
    output wire [63:0] rvfi_order,
    output wire [31:0] rvfi_insn,
    output wire        rvfi_trap,
    output wire [ 4:0] rvfi_rs1_addr,
    output wire [ 4:0] rvfi_rs2_addr,
    output wire [31:0] rvfi_rs1_rdata,
    output wire [31:0] rvfi_rs2_rdata,
    output wire [ 4:0] rvfi_rd_addr,
    output wire [31:0] rvfi_rd_wdata,
    output wire [31:0] rvfi_pc_rdata,
    output wire [31:0] rvfi_pc_wdata,
    output wire [31:0] rvfi_mem_addr,
    output wire [ 3:0] rvfi_mem_rmask,
    output wire [ 3:0] rvfi_mem_wmask,
    output wire [31:0] rvfi_mem_rdata,
    output wire [31:0] rvfi_mem_wdata
);
    picorv32 #(
        .ENABLE_COUNTERS(0),
        .ENABLE_MUL(1),
        .ENABLE_DIV(1),
        .BARREL_SHIFTER(0),
        .CATCH_MISALIGN(1),
        .CATCH_ILLINSN(1),
        .COMPRESSED_ISA(0)
    ) u_cpu (
        .clk(clk), .resetn(resetn), .trap(trap),
        .mem_valid(mem_valid), .mem_instr(mem_instr), .mem_ready(mem_ready),
        .mem_addr(mem_addr), .mem_wdata(mem_wdata), .mem_wstrb(mem_wstrb), .mem_rdata(mem_rdata),
        .pcpi_wr(1'b0), .pcpi_rd(32'd0), .pcpi_wait(1'b0), .pcpi_ready(1'b0),
        .irq(32'd0),
        .rvfi_valid(rvfi_valid), .rvfi_order(rvfi_order), .rvfi_insn(rvfi_insn), .rvfi_trap(rvfi_trap),
        .rvfi_halt(), .rvfi_intr(), .rvfi_mode(), .rvfi_ixl(),
        .rvfi_rs1_addr(rvfi_rs1_addr), .rvfi_rs2_addr(rvfi_rs2_addr),
        .rvfi_rs1_rdata(rvfi_rs1_rdata), .rvfi_rs2_rdata(rvfi_rs2_rdata),
        .rvfi_rd_addr(rvfi_rd_addr), .rvfi_rd_wdata(rvfi_rd_wdata),
        .rvfi_pc_rdata(rvfi_pc_rdata), .rvfi_pc_wdata(rvfi_pc_wdata),
        .rvfi_mem_addr(rvfi_mem_addr), .rvfi_mem_rmask(rvfi_mem_rmask), .rvfi_mem_wmask(rvfi_mem_wmask),
        .rvfi_mem_rdata(rvfi_mem_rdata), .rvfi_mem_wdata(rvfi_mem_wdata),
        .rvfi_csr_mcycle_rmask(), .rvfi_csr_mcycle_wmask(), .rvfi_csr_mcycle_rdata(), .rvfi_csr_mcycle_wdata(),
        .rvfi_csr_minstret_rmask(), .rvfi_csr_minstret_wmask(), .rvfi_csr_minstret_rdata(), .rvfi_csr_minstret_wdata()
    );
endmodule
