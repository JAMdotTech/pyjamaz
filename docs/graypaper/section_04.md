# 4. Overview
\(
    \newcommand{\xttickets}{\mathbf{E}_T}
    \newcommand{\xtdisputes}{\mathbf{E}_D}
    \newcommand{\xtguarantees}{\mathbf{E}_G}
    \newcommand{\xtassurances}{\mathbf{E}_A}
    \newcommand{\xtpreimages}{\mathbf{E}_P}
    \newcommand{\accumulated}{\xi}
    \newcommand{\ready}{\vartheta}
    \newcommand{\beefycommitmap}{\mathbf{C}}
    \newcommand{\accountspostxfer}{\delta^\ddagger}
    \newcommand{\accountspre}{\delta}
    \newcommand{\accountspostpreimage}{\delta'}
    \newcommand{\N}{\mathbb{N}}
    \newcommand{\Y}{\mathbb{Y}}
    \newcommand{\Z}{\mathbb{Z}}
    \newcommand{\oog}{\infty}
    \newcommand{\error}{\nabla}
    \newcommand{\panic}{\lightning}
    \newcommand{\badexports}{\circledcirc}
    \newcommand{\host}{\hbar}
    \newcommand{\halt}{\blacksquare}
    \newcommand{\fault}{\text{\raisebox{6pt}{\rotatebox{180}{\textsf{F}}}}}
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
    \newcommand{\isa}[2]{#1\in #2}
    \newcommand{\memory}{\mu}
    \newcommand{\floor}[1]{\left\lfloor#1\right\rfloor}
\)
## 4.0. General
The aim of this section is to provide a detailed implementation reference on Graypaper equation definitions.
This section has been updated to match Graypaper version 0.5.4.

We begin our formalisms by recalling that a blockchain may be defined as a pairing of some initial state together with a block-level state-transition function. The latter defines the posterior state given a pairing of some prior state and a block of data applied to it.

| ID                      | Equation                                      | Implementation |
|-------------------------|-----------------------------------------------|----------------|
| <a name="4.1">(4.1)</a> | $\sigma' \equiv \Upsilon(\sigma, \mathbf{B})$ | [TODO]         |

## 4.1. The Block
To aid comprehension and definition of our protocol, we partition as many of our terms as possible into their functional components. We begin with the block $\mathbf{B}$ which may be restated as the header $\mathbf{H}$ and some input data external to the system and thus said to be _extrinsic_, $\mathbf{E}$

| Graypaper               | Equation                                                                                  | Implementation                                              |
|-------------------------|-------------------------------------------------------------------------------------------|-------------------------------------------------------------|
| <a name="4.2">(4.2)</a> | $\mathbf{B} \equiv (\mathbf{H}, \mathbf{E})$                                              | [Link](/types/types_blocks/#pyjamaz.models.block.Block)     |
| <a name="4.3">(4.3)</a> | $\mathbf{E} \equiv (\xttickets, \xtdisputes, \xtguarantees, \xtassurances, \xtpreimages)$ | [Link](/types/types_blocks/#pyjamaz.models.block.Extrinsic) |

## 4.2. The State 
Our state may be logically partitioned into several largely independent segments which can both help avoid visual clutter within our protocol description and provide formality over elements of computation which may be simultaneously calculated (i.e. parallelized). We therefore pronounce an equivalence between $\sigma$ (some complete state) and a tuple of partitioned segments of that state.

| Graypaper               | Equation                                                                                                                                     | Implementation                                            |
|-------------------------|----------------------------------------------------------------------------------------------------------------------------------------------|-----------------------------------------------------------|
| <a name="4.4">(4.4)</a> | $\sigma \equiv (\alpha, \beta, \gamma, \delta, \eta, \iota, \kappa, \lambda, \rho, \tau, \varphi, \chi, \psi, \pi, \ready, \accumulated)$    | [Link](/types/types_state/#pyjamaz.models.state.JamState) |

### 4.2.1. State Transition Dependency Graph 
| Graypaper                 | Equation                                                                                                                                                               | Implementation |
|---------------------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------|----------------|
| <a name="4.5">(4.5)</a>   | $\tau' \prec \mathbf{H}$                                                                                                                                               | [TODO]         |
| <a name="4.6">(4.6)</a>   | $\beta^\dagger \prec (\mathbf{H}, \beta) \label{eq:betadagger}$                                                                                                        | [TODO]         |
| <a name="4.7">(4.7)</a>   | $\beta' \prec (\mathbf{H}, \xtguarantees, \beta^\dagger, \beefycommitmap)$                                                                                             | [TODO]         |
| <a name="4.8">(4.8)</a>   | $\gamma' \prec (\mathbf{H}, \tau, \xttickets, \gamma, \iota, \eta', \kappa', \psi')$                                                                                   | [TODO]         |
| <a name="4.9">(4.9)</a>   | $\eta' \prec (\mathbf{H}, \tau, \eta)$                                                                                                                                 | [TODO]         |
| <a name="4.10">(4.10)</a> | $\kappa' \prec (\mathbf{H}, \tau, \kappa, \gamma)$                                                                                                                     | [TODO]         |
| <a name="4.11">(4.11)</a> | $\lambda' \prec (\mathbf{H}, \tau, \lambda, \kappa)$                                                                                                                   | [TODO]         |
| <a name="4.12">(4.12)</a> | $\psi' \prec (\xtdisputes, \psi)$                                                                                                                                      | [TODO]         |
| <a name="4.13">(4.13)</a> | $\rho^\dagger \prec (\xtdisputes, \rho) \label{eq:rhodagger}$                                                                                                          | [TODO]         |
| <a name="4.14">(4.14)</a> | $\rho^\ddagger \prec (\xtassurances, \rho^\dagger) \label{eq:rhoddagger}$                                                                                              | [TODO]         |
| <a name="4.15">(4.15)</a> | $\rho' \prec (\xtguarantees, \rho^\ddagger, \kappa, \tau')$                                                                                                            | [TODO]         |
| <a name="4.16">(4.16)</a> | $\mathbf{W}^* \prec (\xtassurances, \rho')$                                                                                                                            | [TODO]         |
| <a name="4.17">(4.17)</a> | $(\ready', \accumulated', \accountspostxfer, \chi', \iota', \varphi', \beefycommitmap) \prec (\mathbf{W}^*, \ready, \accumulated, \accountspre, \chi, \iota, \varphi)$ | [TODO]         |
| <a name="4.18">(4.18)</a> | $\accountspostpreimage \prec (\xtpreimages, \accountspostxfer, \tau') \label{eq:accountspostpreimage}$                                                                 | [TODO]         |
| <a name="4.19">(4.19)</a> | $\alpha' \prec (\mathbf{H}, \xtguarantees, \varphi', \alpha)$                                                                                                          | [TODO]         |
| <a name="4.20">(4.20)</a> | $\pi' \prec (\xtguarantees, \xtpreimages, \xtassurances, \xttickets, \tau, \kappa', \pi, \mathbf{H})$                                                                  | [TODO]         |

## 4.6. Economics
A value of tokens is generally referred to as a _balance_, and such a value is said to be a member of the set of balances, $\N_B$, which is exactly equivalent to the set of naturals less than $2^{64}$ (\ie 64-bit unsigned integers in coding parlance).

| Graypaper                 | Equation                  | Implementation |
|---------------------------|---------------------------|----------------|
| <a name="4.21">(4.21)</a> | $\N_B \equiv \N_{2^{64}}$ | [TODO]         |

## 4.7. The Virtual Machine and Gas
| Graypaper                 | Equation                                                                                                                                                                                                                                                                                                 | Implementation |
|---------------------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|----------------|
| <a name="4.22">(4.22)</a> | $\Psi\colon \tuple{\, \begin{alignedat}{3} \Y\ts\ \ \N_R\ts\ \ &&\N_G\ts\\ \!\lseq\N_R\rseq_{13}\ts\ \ &&\mathbb{M}\\ \end{alignedat} \,} \to \tuple{\, \begin{aligned} \{\halt, \panic, \oog\} \cup \{\fault,\host\} \times \N_R,\\ \N_R,\ \ \Z_G,\ \ \seq{\N_R}_{13},\ \ \mathbb{M} \end{aligned} \,}$ | [TODO]         |
| <a name="4.23">(4.23)</a> | $\Z_G \equiv \mathbb{Z}_{-2^{63}\dots2^{63}}\ ,\quad \N_G \equiv \mathbb{N}_{2^{64}}\ ,\quad \N_R \equiv \N_{2^{64}}$                                                                                                                                                                                    | [TODO]         |
| <a name="4.24">(4.24)</a> | $\mathbb{M} \equiv \tuple{\isa{\mathbf{V}}{\Y_{2^{32}}}, \isa{\mathbf{A}}{\seq{\{\text{W}, \text{R}, \none\}}_p}}\,,\ p = \frac{2^{32}}{\mathsf{Z}_P}$                                                                                                                                                   | [TODO]         |
| <a name="4.25">(4.25)</a> | $\mathsf{Z}_P = 2^{12}$                                                                                                                                                                                                                                                                                  | [TODO]         |
| <a name="4.26">(4.26)</a> | $\mathbb{V}_{\memory} \equiv \{i \mid \memory_\mathbf{A}[\floor{\nicefrac{i}{\mathsf{Z}_P}}] \ne \none \} \}$                                                                                                                                                                                            | [TODO]         |
| <a name="4.27">(4.27)</a> | $\mathbb{V}^*_{\memory} \equiv \{i \mid \memory_\mathbf{A}[\floor{\nicefrac{i}{\mathsf{Z}_P}}] = \text{W}$                                                                                                                                                                                               | [TODO]         |

## 4.8. Epochs and Slots
| Graypaper                 | Equation                  | Implementation |
|---------------------------|---------------------------|----------------|
| <a name="4.28">(4.28)</a> | $\N_T \equiv \N_{2^{32}}$ | [TODO]         |
