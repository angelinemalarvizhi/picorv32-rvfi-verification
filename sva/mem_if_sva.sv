// Native memory-interface protocol checks for PicoRV32 + RVFI sanity.
// Bind into dut_top for Xcelium / VCS / Questa runs:   bind dut_top mem_if_sva u_sva (.*);
module mem_if_sva (
    input logic        clk,
    input logic        resetn,
    input logic        mem_valid,
    input logic        mem_instr,
    input logic        mem_ready,
    input logic [31:0] mem_addr,
    input logic [31:0] mem_wdata,
    input logic [ 3:0] mem_wstrb,
    input logic        rvfi_valid,
    input logic [63:0] rvfi_order,
    input logic [31:0] rvfi_pc_rdata,
    input logic [31:0] rvfi_pc_wdata,
    input logic        rvfi_trap,
    input logic [ 4:0] rvfi_rd_addr,
    input logic [31:0] rvfi_rd_wdata
);
    default clocking cb @(posedge clk); endclocking
    default disable iff (!resetn);

    // request is held until accepted
    a_valid_hold: assert property (mem_valid && !mem_ready |=> mem_valid);
    a_req_stable: assert property (mem_valid && !mem_ready |=>
                                   $stable(mem_addr) && $stable(mem_wstrb) && $stable(mem_instr));
    a_wdata_stable: assert property (mem_valid && !mem_ready && |mem_wstrb |=> $stable(mem_wdata));
    // fetches never write; addresses are word aligned
    a_fetch_ro:   assert property (mem_valid && mem_instr |-> mem_wstrb == 4'b0000);
    a_aligned:    assert property (mem_valid |-> mem_addr[1:0] == 2'b00);
    // legal byte-strobe patterns only
    a_wstrb_legal: assert property (mem_valid && |mem_wstrb |->
        mem_wstrb inside {4'b0001, 4'b0010, 4'b0100, 4'b1000, 4'b0011, 4'b1100, 4'b1111});
    // RVFI: x0 never reported as written with non-zero data; order strictly increments
    a_x0_zero:    assert property (rvfi_valid && rvfi_rd_addr == 0 |-> rvfi_rd_wdata == 0);
    logic [63:0] prev_order; logic seen;
    always_ff @(posedge clk or negedge resetn)
        if (!resetn) seen <= 0;
        else if (rvfi_valid) begin prev_order <= rvfi_order; seen <= 1; end
    a_order_inc:  assert property (rvfi_valid && seen |-> rvfi_order == prev_order + 1);
    a_pc_aligned: assert property (rvfi_valid && !rvfi_trap |-> rvfi_pc_wdata[1:0] == 2'b00);

    c_wait:       cover property (mem_valid && !mem_ready ##1 mem_valid && !mem_ready ##1 mem_ready);
    c_b2b:        cover property (mem_valid && mem_ready ##1 mem_valid);
    c_store_byte: cover property (mem_valid && mem_ready && mem_wstrb == 4'b1000);
endmodule
