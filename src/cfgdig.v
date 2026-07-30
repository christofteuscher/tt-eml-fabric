/*
 * cfgdig -- EML Fabric configuration block, hardened as a standalone macro.
 * Copyright (c) 2026 Christof Teuscher
 * SPDX-License-Identifier: Apache-2.0
 *
 * Split out of tt_um_teuscher_eml_fabric so OpenLane can place-and-route it
 * on its own: the wrapper instantiates this plus the analog macro, and
 * neither of those is synthesisable.
 *
 * ENTIRELY 3.3 V (sky130_fd_sc_hvl).  Forced by measurement, not taste:
 * with a 1.8 V gate the MDAC switch compliance tops out at 0.85-0.90 V
 * while the cell input nodes sit at 1.17-1.25 V
 * (mdac/switch_gate_1v8.spice), so every config line must swing to 3.3 V.
 * A 1.8 V chain would need one level shifter per OUTPUT line (~109 of
 * them at 97.3 um2); this way only the 4 scan pins need shifting, and
 * those live OUTSIDE this macro, in the top-level assembly.
 *
 * Config map, 4-cell fabric, 64-bit chain:
 *   [54:0]  11 x 5-bit signed weights.  A -> B -> C chain plus test cell T.
 *           A is the chain root and the B/C coupling enters ONE fixed input
 *           each (B at v, C at u -- gen_chain.py), so only 3 gammas exist.
 *           Order: A.ua A.va B.ua B.va B.vg C.ua C.va C.ug T.ua T.va T.ug
 *           w[4:0]: w[4] = sign, w[3:2] = digit a, w[1:0] = digit b
 *           (radix-4, LSB 1/4 unit, FS 3.75).  w[3:0] as an integer m is
 *           the magnitude: value = m/4.
 *   [57:55] observation mux select      [61:58] R_ptat trim   [63:62] spare
 *
 * LATCHLESS by choice: the analog follows the shift register directly.
 * The latch bank cost 5.5 kum2 of floorplan and every intended use is
 * program -> settle -> measure, where garbage during the shift is
 * harmless.  Reset still leaves a safe quiescent state.
 */

`default_nettype none

module cfgdig (
    input  wire        scan_data,
    input  wire        scan_clk,
    input  wire        rst_n,
    output wire        scan_out,

    output wire [65:0] w_therm,     // 11 weights x 2 digits x 3 legs
    output wire [10:0] w_sgn,
    output wire [10:0] w_sgnb,
    output wire [7:0]  mux_oh,      // one-hot + complement for the
    output wire [7:0]  mux_ohb,     // pass-gate observation mux
    output wire [3:0]  rtrim,
    output wire        porb
);

  localparam NBITS = 64;
  localparam NW    = 11;

  reg [NBITS-1:0] shift_q;

  always @(posedge scan_clk or negedge rst_n) begin
    if (!rst_n)
      shift_q <= {NBITS{1'b0}};
    else
      shift_q <= {shift_q[NBITS-2:0], scan_data};
  end

  assign scan_out = shift_q[NBITS-1];
  assign porb     = rst_n;

  /* ---- thermometer decode: 2 bits -> 3 lines per digit.
   * d=0 -> 000, 1 -> 001, 2 -> 011, 3 -> 111.
   * w_therm is weight-major then digit-major: weight i, digit j, leg k is
   * w_therm[i*6 + j*3 + k], j=0 for digit a (weight 1), j=1 for digit b
   * (weight 1/4) -- a straight concatenation of per-weight 6-bit fields. */
  genvar i, j, c;
  generate
    for (i = 0; i < NW; i = i + 1) begin : g_weight
      wire [4:0] code = shift_q[i*5 +: 5];

      for (j = 0; j < 2; j = j + 1) begin : g_digit
        wire [1:0] d = code[(1-j)*2 +: 2];
        assign w_therm[i*6 + j*3 + 0] = (d >= 2'd1);
        assign w_therm[i*6 + j*3 + 1] = (d >= 2'd2);
        assign w_therm[i*6 + j*3 + 2] = (d >= 2'd3);
      end

      /* Steering is a complementary NMOS pair off one summing node (mdac
       * XSP/XSN).  If both were off nsum would float and the leg currents
       * would have nowhere to go.  Never gate these on "magnitude != 0". */
      assign w_sgn [i] = ~code[4];   // positive -> direct path, adds
      assign w_sgnb[i] =  code[4];   // negative -> mirror path, subtracts
    end

    /* one-hot mux select: each channel needs a transmission gate to the
     * output bus and one to the dump rail, hence the complement too */
    for (c = 0; c < 8; c = c + 1) begin : g_mux
      assign mux_oh[c]  = (shift_q[57:55] == c[2:0]);
      assign mux_ohb[c] = ~mux_oh[c];
    end
  endgenerate

  assign rtrim = shift_q[61:58];

endmodule
