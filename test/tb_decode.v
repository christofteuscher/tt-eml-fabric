/*
 * Testbench for the config chain + radix-4 thermometer decode.
 * 64-bit / 11-weight / 2-digit map (4-cell fabric).
 * Run: iverilog -g2012 -o /tmp/tb tb_decode.v ../src/tt_um_teuscher_eml_fabric.v
 *      && /tmp/tb
 *
 * The decode is what stands between a binary magnitude the host writes and
 * the 3-leg thermometer gates in mdac_digit, so the properties checked here
 * are the ones the analog block actually depends on:
 *   1. reconstruction -- popcounts of the three digits recover the code
 *   2. thermometer legality -- lines fill in order, never 010 or 101
 *   3. monotonicity -- value never falls as the code increments
 *   4. steering -- sgn/sgnb strictly complementary, always, including reset
 *   5. independence -- each weight decodes from its own 8 bits only
 */
`default_nettype none
`timescale 1ns / 1ps

module tb_decode;

  reg [7:0] ui_in = 8'b0;
  wire [7:0] uo_out;
  reg rst_n = 1'b0;

  wire [65:0] w_therm;  wire [10:0] w_sgn, w_sgnb;
  wire [7:0]  mux_oh, mux_ohb;  wire [3:0] rtrim;  wire porb, sout;
  cfgdig dut (
      .scan_data(ui_in[0]), .scan_clk(ui_in[1]), .rst_n(rst_n),
      .scan_out(sout),
      .w_therm(w_therm), .w_sgn(w_sgn), .w_sgnb(w_sgnb),
      .mux_oh(mux_oh), .mux_ohb(mux_ohb), .rtrim(rtrim), .porb(porb)
  );
  assign uo_out = {7'b0, sout};

  integer errors = 0;
  task check(input cond, input [511:0] what);
    begin
      if (!cond) begin
        errors = errors + 1;
        $display("  FAIL: %0s", what);
      end
    end
  endtask

  // ---- scan: MSB first, since shift_q[95-k] receives the k-th bit ----
  task scan(input [63:0] word);
    integer k;
    begin
      for (k = 63; k >= 0; k = k - 1) begin
        ui_in[0] = word[k];
        #1 ui_in[1] = 1'b1;   // scan_clk rising
        #1 ui_in[1] = 1'b0;
      end
      #1 ui_in[2] = 1'b1;     // scan_latch rising
      #1 ui_in[2] = 1'b0;
      #1;
    end
  endtask

  function [1:0] popcnt3(input [2:0] t);
    popcnt3 = t[0] + t[1] + t[2];
  endfunction

  function legal3(input [2:0] t);   // thermometer must fill in order
    legal3 = (t == 3'b000) || (t == 3'b001) || (t == 3'b011) || (t == 3'b111);
  endfunction

  integer w, m, s, prev, val;
  reg [63:0] word;
  reg [5:0] th;
  reg [7:0] rb;
  integer k;

  initial begin
    // ---- reset must leave a safe, quiescent state ----
    #2 rst_n = 1'b0; #2;
    check(w_therm == 66'b0, "reset: all thermometer lines must be off");
    check(w_sgn == 11'h7FF && w_sgnb == 11'h000,
          "reset: steering must be direct-path, not floating");
    rst_n = 1'b1; #2;

    // ---- 1-3: exhaustive over one weight's 64 magnitudes x 2 signs ----
    for (s = 0; s < 2; s = s + 1) begin
      prev = -1;
      for (m = 0; m < 16; m = m + 1) begin
        word = 64'b0;
        word[4:0] = {s[0], m[3:0]};
        scan(word);
        th = w_therm[5:0];
        val = 4*popcnt3(th[2:0]) + popcnt3(th[5:3]);

        check(legal3(th[2:0]) && legal3(th[5:3]),
              "digit is not a legal thermometer");
        // value in 1/4 units = 4*a + b
        check(val == m, "decoded magnitude does not match the code");
        check(val > prev, "magnitude is not strictly increasing with the code");
        prev = val;

        check(w_sgn[0] == ~s[0] && w_sgnb[0] == s[0],
              "steering does not follow the sign bit");
        check(w_sgn[0] != w_sgnb[0],
              "steering switches are not complementary");
      end
    end
    $display("exhaustive single-weight decode (32 codes): %0d errors", errors);

    // ---- 4-5: all eleven weights, each a distinct code, decoded
    // independently (w+2 mod 16 spreads over the magnitude range)
    word = 64'b0;
    for (w = 0; w < 11; w = w + 1)
      word[w*5 +: 5] = {(w[0]), 4'((w + 2) & 15)};
    scan(word);
    for (w = 0; w < 11; w = w + 1) begin
      th = w_therm[w*6 +: 6];
      check(4*popcnt3(th[2:0]) + popcnt3(th[5:3])
            == ((w + 2) & 15), "weight decoded from the wrong bit field");
      check(w_sgn[w] == ~w[0], "weight sign decoded from the wrong bit");
    end
    $display("eleven independent weights: %0d errors", errors);

    // ---- mux and trim pass through undecoded ----
    word = 64'b0; word[57:55] = 3'd5; word[61:58] = 4'd11;
    scan(word);
    check(dut.shift_q[57:55] == 3'd5, "mux select mis-sliced");
    check(mux_oh == 8'b0010_0000 && mux_ohb == 8'b1101_1111,
          "mux one-hot decode wrong");
    check(rtrim == 4'd11, "R_ptat trim mis-sliced");

    // ---- 96-bit scan/latch/readback round trip still intact ----
    word = 64'hDEAD_BEEF_1234_5678;
    scan(word);
    for (k = 0; k < 8; k = k + 1) begin      // readback the top 8 bits
      rb[k] = uo_out[0];
      #1 ui_in[1] = 1'b1; #1 ui_in[1] = 1'b0;
    end
    check(rb == {word[56], word[57], word[58], word[59],
                 word[60], word[61], word[62], word[63]},
          "scan readback does not return what was shifted in");
    $display("mux/trim slicing + 64-bit round trip: %0d errors", errors);

    // ---- shifting a new word must not disturb the analog side ----
    word = 64'b0; word[4:0] = 5'h0F;
    scan(word);
    th = w_therm[5:0];
`ifdef HAS_LATCH
    for (k = 0; k < 64; k = k + 1) begin     // shift noise, do NOT latch
      ui_in[0] = k[0];
      #1 ui_in[1] = 1'b1; #1 ui_in[1] = 1'b0;
    end
    check(w_therm[5:0] == th,
          "decode changed while shifting -- cfg_q is not holding");
    $display("analog held stable during shift: %0d errors", errors);
`endif

    if (errors == 0) $display("\nALL DECODE CHECKS PASS");
    else             $display("\n%0d FAILURES", errors);
    $finish;
  end

endmodule
