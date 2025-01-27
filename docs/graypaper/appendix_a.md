# Appendix A. Polka Virtual Machine
\(
    \newcommand{\gascounter}{\varrho}
    \newcommand{\Fskip}{\text{skip}}
    \newcommand{\instr}[1]{\text{{\small \texttt{#1}}}}
    \newcommand{\regs}{\seq{\N_R}_{13}}
    \newcommand{\reg}{{\registers}}
    \newcommand{\mem}{{\memory}}
    \newcommand{\memr}{\mem^{\circlearrowleft}}
    \newcommand{\memwr}{{\mem'}^{\circlearrowleft}}
    \newcommand{\ram}{\mathbb{M}}
    \newcommand{\rnp}[1]{P(#1)}
    \newcommand{\rnq}[1]{Z(#1)}
    \newcommand{\continue}{\blacktriangleright}
    \newcommand{\gas}{\gascounter_\Delta}
    \newcommand{\instrlen}{\ell}
    \newcommand{\revbitsfunc}[1]{\overleftarrow{\mathcal{B}}_{#1}}
    \newcommand{\revunbitsfunc}[1]{\revbitsfunc{#1}^{-1}}
    \newcommand{\bitsfunc}[1]{\mathcal{B}_{#1}}
    \newcommand{\unbitsfunc}[1]{\bitsfunc{#1}^{-1}}
    \newcommand{\bits}[1]{\bitsn{8}{#1}}
    \newcommand{\unbits}[1]{\unbitsn{8}{#1}}
    \newcommand{\bitsn}[2]{\bitsfunc{#1}(#2)}
    \newcommand{\unbitsn}[2]{\unbitsfunc{#1}(#2)}
    \newcommand{\signfunc}[1]{\mathcal{Z}_{#1}}
    \newcommand{\unsignfunc}[1]{\signfunc{#1}^{-1} }
    \newcommand{\signed}[1]{\signedn{8}{#1}}
    \newcommand{\unsigned}[1]{\unsignedn{8}{#1}}
    \newcommand{\signedn}[2]{\signfunc{#1}(#2)}
    \newcommand{\unsignedn}[2]{\unsignfunc{#1}(#2)}
    %\newcommand{\signed}[1]{{{}^{\mathord{\mp}}#1}}
    %\newcommand{\unsigned}[1]{{{}^{\mathord{+}}#1}}
    %\newcommand{\signedn}[2]{{{}_{#1}^{\mathord{\mp}}#2}}
    %\newcommand{\unsignedn}[2]{{{}_{#1}^{\mathord{+}}#2}}
    \newcommand{\RA}{\token{RA}}
    \newcommand{\SP}{\token{SP}}
    \newcommand{\T}{\token{T}}
    \renewcommand{\S}{\token{S}}
    \newcommand{\A}{\token{A}}
    \newcommand{\basicblocks}{\varpi}
    \newcommand{\instructions}{\zeta}
    \newcommand{\immed}{\nu}
\)
The aim of this section is to provide a detailed implementation reference on Graypaper equation definitions.
This section has been updated to match Graypaper version 0.5.4.

## A.1. Basic Definition
| Graypaper Reference | Stub | Implementation | Conformance | Documentation |
|---------------------|-----:|---------------:|------------:|--------------:|
| Equation A.1        |   0% |             0% |          0% |            0% |

## A.2. Instructions, Opcodes and Skip-distance
| Graypaper Reference | Stub | Implementation | Conformance | Documentation |
|---------------------|-----:|---------------:|------------:|--------------:|
| Equation A.2        |   0% |             0% |          0% |            0% |
| Equation A.3        |   0% |             0% |          0% |            0% |

## A.3. Basic Blocks and Termination Instructions
| Graypaper Reference | Stub | Implementation | Conformance | Documentation |
|---------------------|-----:|---------------:|------------:|--------------:|
| Equation A.4        |   0% |             0% |          0% |            0% |

## A.4. Single-Step State Transition
| Graypaper | Equation | Implementation |
|-----------|----------|----------------|
| A.5       | 0%       | 0%             |
| A.6       | 0%       | 0%             |
| A.7       | 0%       | 0%             |
| A.8       | 0%       | 0%             |
| A.9       | 0%       | 0%             |
| A.10      | 0%       | 0%             |
| A.11      | 0%       | 0%             |
| A.12      | 0%       | 0%             |
| A.13      | 0%       | 0%             |

## A.5. Instruction Tables
### A.5.1. Instructions without Arguments
| Graypaper     | Equation                     | Implementation |
|---------------|------------------------------|----------------|
| Equation A.14 | $\ell \equiv \Fskip(\imath)$ | [TODO]        |

| $\instructions_\imath$ | Name                  | $\gas$ | Mutations              | Implementation |
|------------------------|-----------------------|--------|------------------------|----------------|
| 0                      | $\token{trap}$        | 0      | $\varepsilon = \panic$ | [TODO]         |
| 1                      | $\token{fallthrough}$ | 0      | $\\$                   | [TODO]         |

### A.5.2. Instructions with Arguments of One Immediate
| Graypaper     | Equation                                                                                                        | Implementation |
|---------------|-----------------------------------------------------------------------------------------------------------------|----------------|
| Equation A.15 | $\using l_X = \min(4, \ell) \,,$<br>$\immed_X \equiv \sext_{l_X}(\de_{l_X}(\instructions_{\imath+1\dots+l_X}))$ | [TODO]        |

| $\instructions_\imath$ | Name             | $\gas$ | Mutations                             | Implementation |
|------------------------|------------------|--------|---------------------------------------|----------------|
| 10                     | $\token{ecalli}$ | 0      | $\varepsilon = \host \times \immed_X$ | [TODO]         |

### A.5.3. Instructions with Arguments of One Register and One Extended Width Immediate
| Graypaper Reference | Stub | Implementation | Conformance | Documentation |
|---------------------|-----:|---------------:|------------:|--------------:|
| Equation A.16       |   0% |             0% |          0% |            0% |

### A.5.4. Instructions with Arguments of Two Immediates
| Graypaper Reference | Stub | Implementation | Conformance | Documentation |
|---------------------|-----:|---------------:|------------:|--------------:|
| Equation A.17       |   0% |             0% |          0% |            0% |

### A.5.5. Instructions with Arguments of One Offset
| Graypaper Reference | Stub | Implementation | Conformance | Documentation |
|---------------------|-----:|---------------:|------------:|--------------:|
| Equation A.18       |   0% |             0% |          0% |            0% |

### A.5.6. Instructions with Arguments of One Register & One Immediate
| Graypaper Reference | Stub | Implementation | Conformance | Documentation |
|---------------------|-----:|---------------:|------------:|--------------:|
| Equation A.19       |   0% |             0% |          0% |            0% |

### A.5.7. Instructions with Arguments of One Register & Two Immediates
| Graypaper Reference | Stub | Implementation | Conformance | Documentation |
|---------------------|-----:|---------------:|------------:|--------------:|
| Equation A.20       |   0% |             0% |          0% |            0% |

### A.5.8. Instructions with Arguments of One Register, One Immediate & One Offset
| Graypaper Reference | Stub | Implementation | Conformance | Documentation |
|---------------------|-----:|---------------:|------------:|--------------:|
| Equation A.21       |   0% |             0% |          0% |            0% |

### A.5.9. Instructions with Arguments of Two Registers
| Graypaper Reference | Stub | Implementation | Conformance | Documentation |
|---------------------|-----:|---------------:|------------:|--------------:|
| Equation A.22       |   0% |             0% |          0% |            0% |

### A.5.10. Instructions with Arguments of Two Registers & One Immediate
| Graypaper Reference | Stub | Implementation | Conformance | Documentation |
|---------------------|-----:|---------------:|------------:|--------------:|
| Equation A.23       |   0% |             0% |          0% |            0% |

### A.5.11. Instructions with Arguments of Two Registers & One Offset
| Graypaper Reference | Stub | Implementation | Conformance | Documentation |
|---------------------|-----:|---------------:|------------:|--------------:|
| Equation A.24       |   0% |             0% |          0% |            0% |

### A.5.12. Instructions with Arguments of Two Registers & Two Immediates
| Graypaper Reference | Stub | Implementation | Conformance | Documentation |
|---------------------|-----:|---------------:|------------:|--------------:|
| Equation A.25       |   0% |             0% |          0% |            0% |

### A.5.13. Instructions with Arguments of Three Registers
| Graypaper Reference | Stub | Implementation | Conformance | Documentation |
|---------------------|-----:|---------------:|------------:|--------------:|
| Equation A.26       |   0% |             0% |          0% |            0% |

## A.6. Host Call Definition
| Graypaper Reference | Stub | Implementation | Conformance | Documentation |
|---------------------|-----:|---------------:|------------:|--------------:|
| Equation A.27       |   0% |             0% |          0% |            0% |
| Equation A.28       |   0% |             0% |          0% |            0% |

## A.7. Standard Program Initialization
| Graypaper Reference | Stub | Implementation | Conformance | Documentation |
|---------------------|-----:|---------------:|------------:|--------------:|
| Equation A.29       |   0% |             0% |          0% |            0% |
| Equation A.30       |   0% |             0% |          0% |            0% |
| Equation A.31       |   0% |             0% |          0% |            0% |
| Equation A.32       |   0% |             0% |          0% |            0% |
| Equation A.33       |   0% |             0% |          0% |            0% |
| Equation A.34       |   0% |             0% |          0% |            0% |
| Equation A.35       |   0% |             0% |          0% |            0% |

## A.8. Argument Invocation Definition
| Graypaper Reference | Stub | Implementation | Conformance | Documentation |
|---------------------|-----:|---------------:|------------:|--------------:|
| Equation A.36       |   0% |             0% |          0% |            0% |
| Equation A.37       |   0% |             0% |          0% |            0% |
