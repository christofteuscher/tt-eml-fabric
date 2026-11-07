* parasitic-free control
.subckt emlcell_b nu nv out vdd vrefb ve pbias VSUB nb0 nc2 ndl nsv
X0 a_16237_18364_t0 a_15733_18364_t0 VSUB sky130_fd_pr__res_high_po_0p35 l=11.44
X1 VSUB a_13460_550_t3 a_13460_550_t3 VSUB sky130_fd_pr__nfet_g5v0d10v5 ad=2.2 pd=5.1 as=4.4 ps=10.2 w=4 l=2
X2 vdd pbias out vdd sky130_fd_pr__pfet_g5v0d10v5 ad=9.6 pd=33.2 as=9.6 ps=33.2 w=16 l=8
X3 a_14221_18364_t0 a_13717_18364_t0 VSUB sky130_fd_pr__res_high_po_0p35 l=11.44
X4 ve a_4860_8760_t3 a_4860_8760_t3 VSUB sky130_fd_pr__nfet_g5v0d10v5 ad=2.2 pd=5.1 as=4.4 ps=10.2 w=4 l=2
X5 a_13717_18364_t0 nu VSUB sky130_fd_pr__res_high_po_0p35 l=11.44
X6 a_16741_18364_t0 a_16237_18364_t0 VSUB sky130_fd_pr__res_high_po_0p35 l=11.44
X7 a_5880_10660_t0 dw_12460_11350_h a_4860_8760_t3 vdd sky130_fd_pr__pfet_g5v0d10v5 ad=8.8 pd=17.1 as=8.8 ps=17.1 w=16 l=2
X8 a_2374_3250_t3 nb0 a_1840_1350_t0 vdd sky130_fd_pr__pfet_g5v0d10v5 ad=17.6 pd=34.2 as=8.8 ps=17.1 w=16 l=2
X9 vdd pbias nb0 vdd sky130_fd_pr__pfet_g5v0d10v5 ad=2.4 pd=9.2 as=2.4 ps=9.2 w=4 l=8
X10 w_9880_11630_t1 vrefb a_1400_10660_t0 vdd sky130_fd_pr__pfet_g5v0d10v5 ad=8.8 pd=17.1 as=8.8 ps=17.1 w=16 l=2
X11 a_4860_8760_t3 dw_12460_11350_h a_5880_10660_t0 vdd sky130_fd_pr__pfet_g5v0d10v5 ad=8.8 pd=17.1 as=8.8 ps=17.1 w=16 l=2
X12 vdd pbias nsv vdd sky130_fd_pr__pfet_g5v0d10v5 ad=9.6 pd=33.2 as=9.6 ps=33.2 w=16 l=8
X13 a_1400_10660_t0 nv a_380_8760_t3 vdd sky130_fd_pr__pfet_g5v0d10v5 ad=8.8 pd=17.1 as=8.8 ps=17.1 w=16 l=2
X14 a_14480_2450_t0 pbias vdd vdd sky130_fd_pr__pfet_g5v0d10v5 ad=8.8 pd=17.1 as=17.6 ps=34.2 w=16 l=4
X15 VSUB a_13100_15680_t3 sky130_fd_pr__cap_mim_m3_1 l=15.65 w=32
X16 VSUB a_1840_1350_t0 w_12740_8770_t4 VSUB sky130_fd_pr__nfet_g5v0d10v5 ad=4.4 pd=9.1 as=8.8 ps=18.2 w=8 l=1
X17 vdd pbias dw_12460_11350_h vdd sky130_fd_pr__pfet_g5v0d10v5 ad=4.8 pd=17.2 as=4.8 ps=17.2 w=8 l=8
X18 a_13460_550_t3 nsv a_14480_2450_t0 vdd sky130_fd_pr__pfet_g5v0d10v5 ad=8.8 pd=17.1 as=8.8 ps=17.1 w=16 l=2
X19 w_12740_8770_t4 a_1840_1350_t0 VSUB VSUB sky130_fd_pr__nfet_g5v0d10v5 ad=8.8 pd=18.2 as=4.4 ps=9.1 w=8 l=1
X20 ndl a_13100_15680_t3 nsv VSUB sky130_fd_pr__nfet_03v3_nvt ad=2.4 pd=9.2 as=2.4 ps=9.2 w=4 l=0.5
X21 w_12740_8770_t4 a_1840_1350_t0 sky130_fd_pr__cap_mim_m3_1 l=17.3 w=58
X22 w_9880_11630_t1 a_16741_18364_t0 VSUB sky130_fd_pr__res_high_po_0p35 l=11.44
X23 a_380_8760_t3 nv a_1400_10660_t0 vdd sky130_fd_pr__pfet_g5v0d10v5 ad=8.8 pd=17.1 as=8.8 ps=17.1 w=16 l=2
X24 a_5880_10660_t0 pbias vdd vdd sky130_fd_pr__pfet_g5v0d10v5 ad=8.8 pd=17.1 as=17.6 ps=34.2 w=16 l=4
X25 vdd nc2 nc2 vdd sky130_fd_pr__pfet_g5v0d10v5 ad=4.8 pd=17.2 as=4.8 ps=17.2 w=8 l=2
X26 nv w_9880_11630_t1 ve VSUB sky130_fd_pr__npn_05v5_W1p00L1p00
X27 nc2 w_12740_8770_t4 VSUB VSUB sky130_fd_pr__npn_05v5_W1p00L1p00
X28 a_14725_18364_t0 a_14221_18364_t0 VSUB sky130_fd_pr__res_high_po_0p35 l=11.44
X29 a_13100_15680_t3 w_12740_11630_n131 a_14480_2450_t0 vdd sky130_fd_pr__pfet_g5v0d10v5 ad=8.8 pd=17.1 as=8.8 ps=17.1 w=16 l=2
X30 a_1840_1350_t0 a_600_1350_t3 VSUB VSUB sky130_fd_pr__nfet_g5v0d10v5 ad=4.4 pd=10.2 as=2.2 ps=5.1 w=4 l=2
X31 nb0 nb0 VSUB VSUB sky130_fd_pr__npn_05v5_W1p00L1p00
X32 VSUB ndl ndl VSUB sky130_fd_pr__nfet_g5v0d10v5 ad=19.2 pd=65.2 as=19.2 ps=65.2 w=32 l=2
X33 a_14480_2450_t0 nsv a_13460_550_t3 vdd sky130_fd_pr__pfet_g5v0d10v5 ad=8.8 pd=17.1 as=8.8 ps=17.1 w=16 l=2
X34 VSUB a_600_1350_t3 a_600_1350_t3 VSUB sky130_fd_pr__nfet_g5v0d10v5 ad=2.2 pd=5.1 as=4.4 ps=10.2 w=4 l=2
X35 a_2374_3250_t3 pbias vdd vdd sky130_fd_pr__pfet_g5v0d10v5 ad=8.8 pd=17.1 as=8.8 ps=17.1 w=16 l=4
X36 dw_12460_11350_h w_12740_11630_n131 ve VSUB sky130_fd_pr__npn_05v5_W1p00L1p00
X37 VSUB ndl out VSUB sky130_fd_pr__nfet_g5v0d10v5 ad=19.2 pd=65.2 as=19.2 ps=65.2 w=32 l=2
X38 vdd nc2 out vdd sky130_fd_pr__pfet_g5v0d10v5 ad=4.8 pd=17.2 as=4.8 ps=17.2 w=8 l=2
X39 w_12740_8770_t4 a_14725_18364_t0 VSUB sky130_fd_pr__res_high_po_0p35 l=11.44
X40 vrefb nv VSUB sky130_fd_pr__res_xhigh_po_0p35 l=17.5
X41 vrefb dw_12460_11350_h VSUB sky130_fd_pr__res_xhigh_po_0p35 l=17.5
X42 nu w_12740_8770_t4 sky130_fd_pr__cap_mim_m3_1 l=15.6 w=32
X43 w_9880_11630_t1 a_380_8760_t3 ve VSUB sky130_fd_pr__nfet_g5v0d10v5 ad=4.4 pd=10.2 as=2.2 ps=5.1 w=4 l=2
X44 a_14480_2450_t0 w_12740_11630_n131 a_13100_15680_t3 vdd sky130_fd_pr__pfet_g5v0d10v5 ad=17.6 pd=34.2 as=8.8 ps=17.1 w=16 l=2
X45 a_15733_18364_t0 nsv VSUB sky130_fd_pr__res_high_po_0p35 l=11.44
X46 w_12740_11630_n131 a_4860_8760_t3 ve VSUB sky130_fd_pr__nfet_g5v0d10v5 ad=4.4 pd=10.2 as=2.2 ps=5.1 w=4 l=2
X47 a_13100_15680_t3 a_13460_550_t3 VSUB VSUB sky130_fd_pr__nfet_g5v0d10v5 ad=4.4 pd=10.2 as=2.2 ps=5.1 w=4 l=2
X48 vdd pbias w_12740_8770_t4 vdd sky130_fd_pr__pfet_g5v0d10v5 ad=8.8 pd=17.1 as=17.6 ps=34.2 w=16 l=2.67
X49 w_12740_11630_n131 dw_12460_11350_h sky130_fd_pr__cap_mim_m3_1 l=15.65 w=32
X50 ve a_380_8760_t3 a_380_8760_t3 VSUB sky130_fd_pr__nfet_g5v0d10v5 ad=2.2 pd=5.1 as=4.4 ps=10.2 w=4 l=2
X51 a_1840_1350_t0 nb0 a_2374_3250_t3 vdd sky130_fd_pr__pfet_g5v0d10v5 ad=8.8 pd=17.1 as=8.8 ps=17.1 w=16 l=2
X52 vdd pbias dw_12460_11350_h vdd sky130_fd_pr__pfet_g5v0d10v5 ad=2.4 pd=9.2 as=2.4 ps=9.2 w=4 l=8
X53 a_600_1350_t3 nu a_2374_3250_t3 vdd sky130_fd_pr__pfet_g5v0d10v5 ad=8.8 pd=17.1 as=8.8 ps=17.1 w=16 l=2
X54 a_1400_10660_t0 pbias vdd vdd sky130_fd_pr__pfet_g5v0d10v5 ad=8.8 pd=17.1 as=17.6 ps=34.2 w=16 l=4
X55 a_2374_3250_t3 nu a_600_1350_t3 vdd sky130_fd_pr__pfet_g5v0d10v5 ad=8.8 pd=17.1 as=8.8 ps=17.1 w=16 l=2
X56 w_9880_11630_t1 nv sky130_fd_pr__cap_mim_m3_1 l=15.65 w=32
X57 vdd pbias nv vdd sky130_fd_pr__pfet_g5v0d10v5 ad=4.8 pd=17.2 as=4.8 ps=17.2 w=8 l=8
X58 a_5880_10660_t0 vrefb w_12740_11630_n131 vdd sky130_fd_pr__pfet_g5v0d10v5 ad=17.6 pd=34.2 as=8.8 ps=17.1 w=16 l=2
X59 a_1400_10660_t0 vrefb w_9880_11630_t1 vdd sky130_fd_pr__pfet_g5v0d10v5 ad=17.6 pd=34.2 as=8.8 ps=17.1 w=16 l=2
X60 w_12740_11630_n131 vrefb a_5880_10660_t0 vdd sky130_fd_pr__pfet_g5v0d10v5 ad=8.8 pd=17.1 as=8.8 ps=17.1 w=16 l=2
.ends
