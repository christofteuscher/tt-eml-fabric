#!/usr/bin/env python3
"""Fig. (fig:cell): the eml cell at transistor level, shaded by supply current.

Topology is transcribed device by device from spice/char/emlcell_b_sim12.inc,
the netlist that LVS-matches the shipped layout (device names are the netlist's).
The supply current of each leg that draws from the 3.3 V rail is parsed from
POWER.md of the paper source (not public; section 1.1, "Per leg"; schematic operating point in die
context at u = 0, v = 1; the twelve legs sum to I_vdd = 29.8686 uA).  The
script asserts that the parsed legs sum to the recorded total and that every
netlist device it draws exists in the netlist.

Writes fig_cell_src.tex and compiles it to fig_cell.pdf.

Run:
  python3 gen_fig_cell.py
"""
import os
import re
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
import sys  # noqa: E402
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import paths  # noqa: E402
POWER = paths.paper("POWER.md")
NETLIST = paths.repo("spice", "char", "emlcell_b_sim12.inc")
TEX = "/Library/TeX/texbin"


def legs():
    txt = open(POWER).read()
    per_leg = txt.split("Per leg:")[1].split("**The translinear core")[0]
    cur = {m.group(1): float(m.group(2)) for m in re.finditer(
        r"\|\s*`(X\w+)`[^|]*\|\s*[0-9./]+\s*\|\s*([0-9.]+)\s*\|", per_leg)}
    total = float(re.search(r"\| total \| \| ([0-9.]+) uA", txt).group(1))
    by_fn = {k: float(v) for k, v in re.findall(
        r"\|\s*\*\*(servo amplifiers|bias / pedestal legs|output mirrors)\*\*[^|]*\|[^|]*\|\s*([0-9.]+) uA", txt)}
    assert len(cur) == 12, cur
    assert abs(sum(cur.values()) - total) < 0.02, (sum(cur.values()), total)
    return cur, total, by_fn


def netlist_devices():
    names = set()
    for ln in open(NETLIST):
        if ln.startswith(("X", "C")):
            names.add(ln.split()[0])
    return names


TEMPLATE = r"""\documentclass[border=2pt]{standalone}
\usepackage[T1]{fontenc}
\usepackage{lmodern}
\usepackage[american,siunitx]{circuitikz}
\usepackage{xcolor}
\usetikzlibrary{calc,backgrounds,fit}
\renewcommand{\familydefault}{\sfdefault}
\definecolor{servo}{HTML}{D55E00}
\definecolor{bias}{HTML}{0072B2}
\definecolor{mirr}{HTML}{6F6F6F}
\definecolor{core}{HTML}{009E73}
\definecolor{otaA}{HTML}{E69F00}
\ctikzset{amplifiers/scale=0.62, tripoles/mos style/arrows, transistors/scale=0.85,
          bipoles/resistor/height=0.22, bipoles/resistor/width=0.6,
          bipoles/capacitor/height=0.4, bipoles/capacitor/width=0.12}
\tikzset{
  lab/.style={font=\normalsize, inner sep=1pt},
  cur/.style={font=\normalsize\bfseries, inner sep=1pt},
  dev/.style={font=\normalsize, inner sep=1pt, text=black!75},
  net/.style={font=\small\itshape, inner sep=1pt, text=black!60},
  region/.style={rounded corners=3pt, fill opacity=0.13, draw opacity=0.55, line width=0.5pt},
}
\begin{document}
\begin{circuitikz}[line width=0.6pt]
%% ---------------------------------------------------------------- rails
\def\VDD{9.0}
\draw (-0.6,\VDD) -- (25.4,\VDD) node[right,lab]{$V_{dd}$ \SI{3.3}{V}};
\draw (-0.6,0) -- (25.4,0) node[right,lab]{ground};
\draw (17.0,1.25) -- (25.4,1.25) node[right,lab]{$V_E$ \SI{0.55}{V}};
\draw (15.8,2.15) -- (25.4,2.15) node[right,lab]{$V_{\mathrm{refb}}$ \SI{1.2}{V}};

%% ================================================= exponential path
\node[npn, anchor=C] (QR) at (1.2,4.9) {};
\node[dev,left] at ($(QR.center)+(-0.35,-0.35)$) {$Q_R$};
\draw (QR.E) -- (QR.E |- 0,0);
\coordinate (nb0) at ($(QR.C)+(0,1.3)$);
\draw (QR.C) -- (nb0);
\draw (QR.B) -- ++(-0.35,0) |- ($(QR.C)+(0,0.45)$) to[short,-*] ($(QR.C)+(0,0.45)$);
\node[pmos, anchor=D] (LR1) at ($(QR.C)+(0,2.55)$) {};
\draw (LR1.D) -- (nb0) node[pos=0.5,right,net]{};
\draw (LR1.S) -- (LR1.S |- 0,\VDD);
\node[cur,bias,left] at ($(LR1.G)+(-0.05,0)$) {<<XLR1>>};

\node[op amp] (A1) at (3.6,5.85) {};
\node[lab] at ($(A1.center)+(-0.12,0)$) {$A_1$};
\draw (nb0) to[short,*-] (nb0 -| A1.-) -- (A1.-);
\coordinate (nu) at (2.55,4.0);
\draw (A1.+) -| (nu);
\coordinate (vb2) at (5.05,4.0);
\draw (A1.out) -| (vb2);
\draw (nu) to[R, l=\small$R_u$, *-*, n=RU] (vb2);
\draw (nu) -- ++(0,-0.75) coordinate (cfu1) to[C, l_=\small$C_u$] (cfu1 -| vb2) -- (vb2);
\draw (cfu1) to[short,-o] ++(0,-1.0) coordinate (uin);
\node[lab,below] at (uin) {$u$ in};
\node[npn, anchor=B] (Q2) at ($(vb2)+(0.55,0)$) {};
\draw (vb2) -- (Q2.B);
\node[dev,right] at ($(Q2.center)+(0.25,-0.35)$) {$Q_2$};
\draw (Q2.E) -- (Q2.E |- 0,0);
\node[cur,servo] at ($(A1.center)+(0,0.95)$) {<<XMT_OT>> + <<XMS_OT>>};

%% output mirror (pfet pair), exp current to the output
\node[pmos, anchor=D, xscale=-1] (PM1) at ($(Q2.C |- 0,7.45)$) {};
\draw (Q2.C) -- (PM1.D);
\draw (PM1.S) -- (PM1.S |- 0,\VDD);
\node[pmos, anchor=D] (PM2) at ($(Q2.C |- 0,7.45)+(1.9,0)$) {};
\draw (PM2.S) -- (PM2.S |- 0,\VDD);
\draw (PM1.G) -- (PM2.G);
\draw (PM1.G) |- ($(PM1.D)+(0,0.25)$) to[short,-*] ($(PM1.D)+(0,0.25)$);
\node[cur,mirr,below] at ($(PM1.D)!0.5!(PM2.D)+(0,-0.15)$) {<<XMPM1>> + <<XMPM2>>};

%% ================================================= output node
\coordinate (outbus) at (PM2.D |- 0,2.35);
\draw (PM2.D) -- (outbus);
\node[pmos, anchor=D] (LO3) at ($(PM2.D)+(1.2,0)$) {};
\draw (LO3.S) -- (LO3.S |- 0,\VDD);
\draw (LO3.D) |- (outbus);
\node[cur,bias,right] at ($(LO3.D)+(0.08,-0.35)$) {<<XLO3>>};
\draw (outbus) to[short,*-o] ++(0,-1.25) coordinate (outp);
\node[lab,below] at (outp) {out};

%% ================================================= ln V-to-I
\node[pmos, anchor=D] (LO2) at (12.3,7.45) {};
\draw (LO2.S) -- (LO2.S |- 0,\VDD);
\node[cur,bias,left] at ($(LO2.G)+(-0.05,0)$) {<<XLO2>>};
\coordinate (nsvR) at ($(LO2.D)+(0,-0.7)$);
\coordinate (nsvA) at ($(LO2.D)+(0,-1.8)$);
\node[nmos, anchor=D, xscale=-1] (MNP) at ($(LO2.D)+(0,-2.4)$) {};
\draw (LO2.D) -- (MNP.D);
\node[dev,left] at ($(MNP.center)+(-0.3,0)$) {$M_P$};
\node[nmos, anchor=D] (MN1) at ($(MNP.S)+(0,-0.55)$) {};
\draw (MNP.S) -- (MN1.D);
\draw (MN1.S) -- (MN1.S |- 0,0);
\draw (MN1.G) |- ($(MN1.D)+(0,0.25)$) to[short,-*] ($(MN1.D)+(0,0.25)$);
\node[nmos, anchor=G, xscale=-1] (MN2) at ($(MN1.G)+(-0.75,0)$) {};
\draw (MN2.G) -- (MN1.G);
\draw (MN2.S) -- (MN2.S |- 0,0);
\draw (MN2.D) |- (outbus);
\node[op amp, yscale=-1, xscale=-1, anchor=out] (A4) at ($(MNP.G)+(0.55,0)$) {};
\draw (A4.out) -- (MNP.G);
\node[lab] at ($(A4.center)+(0.1,0)$) {$A_4$};
\draw (nsvA) to[short,*-] (nsvA -| A4.+) ;
\draw (nsvA -| A4.+) |- (A4.+);
\node[cur,servo,below] at ($(A4.center)+(0.1,-0.65)$) {<<XMT_ON>>};

%% ================================================= ln transdiode A (signal)
\node[pmos, anchor=D] (LPA) at (19.0,7.45) {};
\draw (LPA.S) -- (LPA.S |- 0,\VDD);
\node[cur,bias,left] at ($(LPA.G)+(-0.05,0)$) {<<XLPA>>};
\node[npn, anchor=C] (QA) at (19.0,4.55) {};
\draw (LPA.D) -- (QA.C);
\coordinate (nv) at (19.0,6.1);
\node[dev,below] at ($(QA.center)+(0.1,-0.72)$) {$Q_A$};
\draw (QA.E) -- (QA.E |- 0,1.25);
\node[op amp, yscale=-1, anchor=out] (A2) at ($(QA.B)+(-0.5,0)$) {};
\coordinate (oa) at ($(QA.B)+(-0.25,0)$);
\draw (A2.out) -- (QA.B);
\node[lab] at ($(A2.center)+(-0.12,0)$) {$A_2$};
\draw (nv) to[short,*-] (nv -| A2.+) ;
\draw ($(A2.+)+(-0.3,0)$) -- (A2.+);
\draw (nv -| A2.+) -- ++(-0.3,0) |- (A2.+);
\draw (A2.-) -| ($(A2.- |- 0,2.15)+(-0.3,0)$) to[short,-*] ($(A2.- |- 0,2.15)+(-0.3,0)$);
\draw (oa) to[short,*-] ($(oa |- 0,5.3)$) coordinate (oaT) to[C, l_=\small$C_A$, -*] (oaT -| QA.C);
\draw (nv) -- ++(0.75,0) coordinate (rsa) to[R, l=\small$R_{SA}$, n=RSA] (rsa |- 0,2.15) to[short,-*] (rsa |- 0,2.15);
\node[cur,servo,below] at ($(A2.center)+(-0.1,-0.65)$) {<<XMT_OA>>};
\node[lab,right] at ($(nv)+(0.05,0.18)$) {$v$ in};

%% ln resistor from oa (QA base) to nsv
\draw (oaT) -- (oaT |- nsvR) -- ($(oaT |- nsvR)+(-1.2,0)$) to[R, l_=\small$R_{\mathrm{LN}}$, n=RLN] ($(nsvR)+(2.0,0)$) -- (nsvR) to[short,-*] (nsvR);

%% ================================================= ln transdiode B (reference)
\node[pmos, anchor=D] (LPB) at (23.6,7.45) {};
\draw (LPB.S) -- (LPB.S |- 0,\VDD);
\node[cur,bias,left] at ($(LPB.G)+(-0.05,0)$) {<<XLPB_LVR>>};
\node[npn, anchor=C] (QB) at (23.6,4.55) {};
\draw (LPB.D) -- (QB.C);
\coordinate (nvb) at (23.6,6.1);
\node[dev,below] at ($(QB.center)+(0.1,-0.72)$) {$Q_B$};
\draw (QB.E) -- (QB.E |- 0,1.25);
\node[op amp, yscale=-1, anchor=out] (A3) at ($(QB.B)+(-0.5,0)$) {};
\coordinate (ob) at ($(QB.B)+(-0.25,0)$);
\draw (A3.out) -- (QB.B);
\node[lab] at ($(A3.center)+(-0.12,0)$) {$A_3$};
\draw (nvb) to[short,*-] (nvb -| A3.+) -- ++(-0.3,0) |- (A3.+);
\draw (A3.-) -| ($(A3.- |- 0,2.15)+(-0.3,0)$) to[short,-*] ($(A3.- |- 0,2.15)+(-0.3,0)$);
\draw (ob) to[short,*-] ($(ob |- 0,5.3)$) coordinate (obT) to[C, l_=\small$C_B$, -*] (obT -| QB.C);
\draw (nvb) -- ++(0.75,0) coordinate (rsb) to[R, l=\small$R_{SB}$, n=RSB] (rsb |- 0,2.15) to[short,-*] (rsb |- 0,2.15);
\node[cur,servo,below] at ($(A3.center)+(-0.1,-0.65)$) {<<XMT_OB>>};

%% ob to A4 minus input, along a bus at y = 2.9
\draw (ob) |- ($(A4.- |- 0,2.85)+(0.45,0)$) |- (A4.-);

%% ================================================= shading by function
\begin{scope}[on background layer]
 \node[region, draw=core, fill=core, fit=(QR)(Q2)(QA)(QB), inner sep=0pt, opacity=0] {};
 \foreach \n in {RU,RLN}{\fill[core, opacity=0.22, rounded corners=2pt] ($(\n.center)+(-0.5,-0.25)$) rectangle ($(\n.center)+(0.5,0.25)$);}
 \foreach \n in {RSA,RSB}{\fill[core, opacity=0.22, rounded corners=2pt] ($(\n.center)+(-0.25,-0.5)$) rectangle ($(\n.center)+(0.25,0.5)$);}
 \foreach \n in {QR,Q2,QA,QB}{\fill[core, opacity=0.22, rounded corners=2pt] ($(\n.center)+(-0.55,-0.7)$) rectangle ($(\n.center)+(0.55,0.7)$);}
 \foreach \n in {A1,A2,A3,A4}{\fill[servo, opacity=0.16, rounded corners=2pt] ($(\n.center)+(-1.0,-0.95)$) rectangle ($(\n.center)+(1.0,1.2)$);}
 \foreach \n in {LR1,LO3,LO2,LPA,LPB}{\fill[bias, opacity=0.16, rounded corners=2pt] ($(\n.center)+(-0.55,-0.75)$) rectangle ($(\n.center)+(0.55,0.75)$);}
 \fill[mirr, opacity=0.16, rounded corners=2pt] ($(PM1.center)+(-0.6,-0.8)$) rectangle ($(PM2.center)+(0.6,0.8)$);
\end{scope}

%% ================================================= legend
\begin{scope}[shift={(-0.4,-1.15)}]
 \foreach \c/\t [count=\i from 0] in {servo/{servo amplifiers: <<servo>>},
                                        bias/{bias and pedestal legs: <<bias>>},
                                        mirr/{output mirror: <<mirr>>},
                                        core/{translinear core (4 NPN, 4 resistors): 0 from $V_{dd}$}}{
   \fill[\c, opacity=0.35] (\i*6.6,0) rectangle ++(0.4,0.3);
   \node[lab, anchor=west] at (\i*6.6+0.5,0.15) {\t};
 }
\end{scope}
\node[font=\Large\bfseries, anchor=north west] at (-0.9,10.0) {a};

%% ================================================= (b) servo amplifier, transistor level
\begin{scope}[shift={(0.6,-9.2)}]
 \node[font=\Large\bfseries, anchor=north west] at (-1.5,6.6) {b};
 \fill[servo, opacity=0.10, rounded corners=3pt] (-1.0,-0.3) rectangle (10.6,6.2);
 \draw (-0.6,5.8) -- (10.2,5.8) node[right,lab]{$V_{dd}$};
 \draw (-0.6,0) -- (10.2,0) node[right,lab]{ground or $V_E$};
 \node[pmos, anchor=D] (MT) at (2.6,4.65) {};
 \draw (MT.S) -- (MT.S |- 0,5.8);
 \node[lab,left] at (MT.G) {$p_{\mathrm{bias}}$};
 \node[cur,servo,right,align=left] at ($(MT.center)+(0.45,-0.05)$) {tail <<XMT_OA>> ($A_2$--$A_4$)\\ \phantom{tail} <<XMT_OT>> ($A_1$)};
 \coordinate (ntail) at ($(MT.D)+(0,-0.3)$);
 \draw (MT.D) -- (ntail);
 \node[pmos, anchor=S] (MP1) at ($(ntail)+(-1.3,0)$) {};
 \node[pmos, anchor=S, xscale=-1] (MP2) at ($(ntail)+(1.3,0)$) {};
 \draw (MP1.S) -- (MP2.S);
 \fill (ntail) circle (1.6pt);
 \node[lab,left] at (MP1.G) {$+$\,in};
 \node[lab,right] at (MP2.G) {in\,$-$};
 \node[nmos, anchor=D] (MN1i) at ($(MP1.D)+(0,-0.9)$) {};
 \node[nmos, anchor=D, xscale=-1] (MN2i) at ($(MP2.D)+(0,-0.9)$) {};
 \draw (MP1.D) -- (MN1i.D); \draw (MP2.D) -- (MN2i.D);
 \draw (MN1i.S) -- (MN1i.S |- 0,0); \draw (MN2i.S) -- (MN2i.S |- 0,0);
 \draw (MN1i.G) -- (MN2i.G);
 \draw (MN1i.G) |- ($(MN1i.D)+(0,0.3)$) to[short,-*] ($(MN1i.D)+(0,0.3)$);
 \coordinate (no1) at ($(MN2i.D)+(0,0.45)$);
 \draw (no1) to[short,*-o] ($(no1)+(1.2,0)$) node[above,lab]{out ($A_2$--$A_4$)};
 %% second stage, A1 only
 \node[nmos, anchor=D] (MN3) at (8.0,2.2) {};
 \node[pmos, anchor=D] (MS) at (8.0,4.65) {};
 \draw (MS.S) -- (MS.S |- 0,5.8);
 \draw (MN3.S) -- (MN3.S |- 0,0);
 \coordinate (o2) at ($(MS.D)!0.5!(MN3.D)$);
 \draw (MS.D) -- (MN3.D);
 \draw (o2) to[short,*-o] ++(1.0,0) node[right,lab]{out ($A_1$)};
 \node[lab,left] at (MS.G) {$p_{\mathrm{bias}}$};
 \draw (MN3.G) -- ++(-0.6,0) coordinate (g3);
 \draw ($(no1)+(0.6,0)$) to[short,*-] ($(no1)+(0.6,-0.9)$) -| (g3);
 \draw ($(no1)+(0.6,-0.9)$) ++(0,0) coordinate (ccl);
 \draw (g3) ++(0,0.95) coordinate (cct);
 \draw[densely dashed, black!55, rounded corners=2pt] (6.3,0.25) rectangle (10.0,5.55);
 \node[lab, text=black!60, anchor=south] at (8.2,0.3) {second stage, $A_1$ only};
 \node[cur,servo,right] at ($(MS.center)+(0.35,-0.25)$) {<<XMS_OT>>};
 \draw (g3) to[C, l_=\small$C_C$, *-] (g3 |- o2) -- (o2);
 \draw ($(o2)+(0,0)$) -- ++(0,0) ;
\end{scope}
\end{circuitikz}
\end{document}
"""


def main():
    cur, total, by_fn = legs()
    devs = netlist_devices()
    for name in list(cur) + ["XQR", "XQ2", "XQA", "XQB", "CFU", "CFA", "CFB", "XMNP",
                             "XMNM1", "XMNM2", "XU_0", "XLN_0", "XSA_0", "XSB_0"]:
        assert name in devs, name
    src = TEMPLATE

    def fmt(x):
        return r"\SI{%.2f}{\micro\ampere}" % x

    def sub(m):
        keys = m.group(0)
        return keys
    # single legs and sums ("<<A>> + <<B>>" -> one summed label)
    def repl_sum(m):
        names = re.findall(r"<<(\w+)>>", m.group(0))
        return fmt(sum(cur[n] for n in names))
    src = re.sub(r"<<X\w+>>(?:\s*\+\s*<<X\w+>>)*", repl_sum, src)
    share = lambda k: r"\SI{%.1f}{\percent} of $I_{dd}$" % (100 * by_fn[k] / total)
    src = (src.replace("<<servo>>", share("servo amplifiers"))
              .replace("<<bias>>", share("bias / pedestal legs"))
              .replace("<<mirr>>", share("output mirrors")))
    assert "<<" not in src
    out = os.path.join(HERE, "fig_cell_src.tex")
    open(out, "w").write(src)
    env = dict(os.environ, PATH=TEX + ":" + os.environ["PATH"])
    r = subprocess.run(["pdflatex", "-interaction=nonstopmode", "-halt-on-error",
                        "fig_cell_src.tex"], cwd=HERE, env=env, capture_output=True, text=True)
    if r.returncode:
        print(r.stdout[-3000:])
        raise SystemExit("pdflatex failed")
    os.replace(os.path.join(HERE, "fig_cell_src.pdf"), os.path.join(HERE, "fig_cell.pdf"))
    for ext in ("aux", "log"):
        p = os.path.join(HERE, "fig_cell_src." + ext)
        if os.path.exists(p):
            os.remove(p)
    print("wrote fig_cell.pdf; total %.4f uA; by function %s" % (total, by_fn))


if __name__ == "__main__":
    main()
