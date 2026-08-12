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

    output wire [19:0] w_bin,       // 5 weights x 2 digits x 2 bits
    output wire [4:0]  w_sgn,
    output wire [4:0]  w_sgnb,
    output wire [2:0]  rtrim,      // 3, not 4 -- see TRIM_BITS below
    output wire        porb
);

  /* NW WAS 11 BUT ONLY 5 WEIGHTS ARE WIRED.  The die carries 5 MDACs
   * (CA.ua/CA.va/CB.ua/CB.va + link1.gamma); weights 5..10 reached no
   * silicon at all, and gen_toplvs listed their pins under "OPEN pins --
   * each is a pin the netlist gives no net": t20..t43, sgn5..sgn10,
   * sgnb5..sgnb10.  That is 30 dead flops of a 64-bit chain, each one a
   * dfrtp_1 contributing hvi.5 fragments and area for nothing.
   *
   * Cutting them is also what makes the custom all-MV flop affordable:
   * a continuous-diffusion dfrtp cannot use diffusion breaks for
   * isolation, so it needs dummy GATE columns instead and comes out
   * ~41-45 sites against the PDK's 32 (+30-40%).  Growing cfgdig by that
   * much would push it down into the 16.4 um emlcell->cfgdig corridor
   * whose ~23 lanes are exactly what forced the binary encoding.  Losing
   * 30 of 64 flops more than pays for it.
   *
   * TRIM_BASE replaces the hardcoded shift_q[61:58]: with NW no longer
   * 11 that literal pointed into empty chain. */
  localparam NW        = 5;
  localparam TRIM_BASE = NW * 5;          // 25
  // TRIM_BITS = 3, NOT 4.  rptat_trim is THREE binary segments (1x/2x/4x the
  // 5k unit) over a 15k base -- see bias/rptat_trim.inc: "Eight levels in 5k
  // steps ... coarse ON PURPOSE: this is a range-setter, not a precision
  // knob".  It has exactly three shorting switches (t0/t1/t2) and there is
  // no fourth tap to drive.  Allocating 4 bits here made trim3 a config bit
  // that reaches nothing: it showed up as an OPEN pin at the top level
  // ("each is a pin the netlist gives no net") while every geometric check
  // stayed clean.  A 4th bit would need eight more res_5k for the 8x segment,
  // and the 3-bit range (15-50k) already covers the measured poly spread
  // (21-39k = +40%/-22% of design current).  So the WORD shrinks; the trim
  // network is correct as laid out.
  localparam TRIM_BITS = 3;
  localparam NBITS     = TRIM_BASE + TRIM_BITS + 1;   // 29 -- 3 trim + tail
                                          // flop that drives scan_out

  reg [NBITS-1:0] shift_q;

  always @(posedge scan_clk or negedge rst_n) begin
    if (!rst_n)
      shift_q <= {NBITS{1'b0}};
    else
      shift_q <= {shift_q[NBITS-2:0], scan_data};
  end

  assign scan_out = shift_q[NBITS-1];
  assign porb     = rst_n;

  /* ---- BINARY digit lines: 2 bits per digit, no decode.
   * The MDAC switches are now binary-weighted (switch 2 shares switch 1's
   * control), so a radix-4 digit reads value = c0*1 + c1*2 over 0..3 -- the
   * same range the 3-line thermometer covered.  Thermometer spent 3 wires
   * on 4 levels; this spends 2, which removes 10 nets from the single
   * cfgdig->MDAC corridor that is capacity-limited (task #35: it carries
   * ~23 and ~29 wanted to cross, so exactly 10 always failed).
   * The decoder is DELETED rather than relocated -- the raw digit IS the
   * binary code, so this is strictly less logic.
   * w_bin is weight-major then digit-major: weight i, digit j, bit k is
   * w_bin[i*4 + j*2 + k], j=0 for digit a (weight 1), j=1 for digit b. */
  genvar i, j, c;
  generate
    for (i = 0; i < NW; i = i + 1) begin : g_weight
      wire [4:0] code = shift_q[i*5 +: 5];

      for (j = 0; j < 2; j = j + 1) begin : g_digit
        wire [1:0] d = code[(1-j)*2 +: 2];
        assign w_bin[i*4 + j*2 + 0] = d[0];
        assign w_bin[i*4 + j*2 + 1] = d[1];
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
    end
  endgenerate

  assign rtrim = shift_q[TRIM_BASE +: TRIM_BITS];

endmodule
