# 5. The Header
\(
    \newcommand{\bm}{}
    \newcommand{\ts}{,\,}
    \newcommand{\lseq}{[}
    \newcommand{\rseq}{]}
    \newcommand{\ltup}{\!\left\lgroup}
    \newcommand{\rtup}{\right\rgroup\!}
    \newcommand{\ltuple}{\!\left\lgroup}
    \newcommand{\rtuple}{\right\rgroup\!}
    \newcommand{\sq}[1]{\left[#1\right]}
    \newcommand{\seq}[1]{\lseq#1\rseq}
    \newcommand{\tup}[1]{\ltup#1\rtup}
    \newcommand{\tuple}[1]{\ltuple#1\rtuple}
    \newcommand{\none}{\varnothing}
    \renewcommand{\H}{\mathbb{H}}
    \newcommand{\N}{\mathbb{N}}
    \newcommand{\se}{\mathcal{E}}
    \newcommand{\xttickets}{\mathbf{E}_T}
    \newcommand{\xtdisputes}{\mathbf{E}_D}
    \newcommand{\xtguarantees}{\mathbf{E}_G}
    \newcommand{\xtassurances}{\mathbf{E}_A}
    \newcommand{\xtpreimages}{\mathbf{E}_P}
    \newcommand{\where}{ \text{where }}
    \newcommand{\also}{ \text{and }}
    \newcommand{\var}[1]{\left\updownarrow#1\right.\!}
    %\newcommand{\orderedin}{\ensuremath{\mathrel{\mathrlap{<}{\scalebox{0.95}[1]{$-$}}}}}%
\)
The aim of this section is to provide a detailed implementation reference on Graypaper equation definitions.
This section has been updated to match Graypaper version 0.5.4. 

## 5.0. General
| Graypaper               | Equation                                                                                                                                                         | Implementation |
|-------------------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------|----------------|
| <a name="5.1">(5.1)</a> | $\mathbf{H} \equiv (\mathbf{H}_p, \mathbf{H}_r, \mathbf{H}_x, \mathbf{H}_t, \mathbf{H}_e, \mathbf{H}_w, \mathbf{H}_o, \mathbf{H}_i, \mathbf{H}_v, \mathbf{H}_s)$ | [TODO]         |
| <a name="5.2">(5.2)</a> | $\mathbf{H}_p \in \H \,,\quad \mathbf{H}_p \equiv \mathcal{H}(\se(P(\mathbf{H})))$                                                                               | [TODO]         |
| <a name="5.3">(5.3)</a> | $h \in \mathbf{A} \Leftrightarrow h = \mathbf{H} \vee (\exists i \in \mathbf{A} : h = P(i))$                                                                     | [TODO]         |
| <a name="5.4">(5.4)</a> | $\mathbf{H}_x \in \H \ ,\\ \mathbf{H}_x \equiv \mathcal{H}(\se(\mathcal{H}^\#(\mathbf{a})))$                                                                     | [TODO]         |
| <a name="5.5">(5.5)</a> | $\where \mathbf{a} = [\se_T(\xttickets), \se_P(\xtpreimages), \mathbf{g}, \se_A(\xtassurances), \se_D(\xtdisputes)]$                                             | [TODO]         |
| <a name="5.6">(5.6)</a> | $\also \mathbf{g} = \se(\var{[\se(\mathcal{H}(w), \se_4(t), \var{a}) \mid (w, t, a) \orderedin \xtguarantees]})$                                                 | [TODO]         |
| <a name="5.7">(5.7)</a> | $\mathbf{H}_t \in \N_T \,,\\ P(\mathbf{H})_t < \mathbf{H}_t\ \wedge\ \mathbf{H}_t\cdot\mathsf{P} \leq \mathcal{T}$                                               | [TODO]         |
| <a name="5.8">(5.8)</a> | $\mathbf{H}_r \in \H \,,\\ \mathbf{H}_r \equiv \mathcal{M}_\sigma(\sigma)$                                                                                       | [TODO]         |
| <a name="5.9">(5.9)</a> | $\mathbf{H}_i \in \N_\mathsf{V} \,,\\ \mathbf{H}_a \equiv \kappa'[\mathbf{H}_i]$                                                                                 | [TODO]         |

## 5.1. The Markers
If not $\none$, then the epoch marker specifies key and entropy relevant to the following epoch in case the ticket contest does not complete adequately (a very much unexpected eventuality). Similarly, the winning-tickets marker, if not $\none$, provides the series of 600 slot sealing "tickets" for the next epoch. Finally, the offenders marker is the sequence of Ed25519 keys of newly misbehaving validators.

| Graypaper                 | Equation                                                                                                                                                          | Implementation |
|---------------------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------|----------------|
| <a name="5.10">(5.10)</a> | $\mathbf{H}_e \in \tuple{\H\ts\H\ts\lseq\H_B\rseq_{\mathsf{V}}}\bm{?}\,,\\ \mathbf{H}_w \in \seq{\mathbb{C}} _{\mathsf{E}}\bm{?}\,,\\ \mathbf{H}_o \in \seq{\H_E}$ | [TODO]         |
