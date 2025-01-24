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
\)

The aim of this section is to provide a detailed implementation reference on Graypaper equation definitions.
This section has been updated to match Graypaper version 0.5.0.

| Graypaper Reference | Stub | Implementation | Conformance | Documentation |
|---------------------|-----:|---------------:|------------:|--------------:|
| Equation 4.1        |   0% |             0% |          0% |            0% |

### Equation 4.1
\(
    (4.1)  \quad 
    \sigma' \equiv \Upsilon(\sigma, \mathbf{B})
\)
### Implementation
[TODO]
### Conformance
[TODO]
### Documentation
We begin our formalisms by recalling that a blockchain may be defined as a pairing of some initial state together with a block-level state-transition function. The latter defines the posterior state given a pairing of some prior state and a block of data applied to it. Formally, we say:
### References
[TODO]

## 4.1. The Block 
| Graypaper Reference | Stub | Implementation | Conformance | Documentation |
|---------------------|-----:|---------------:|------------:|--------------:|
| Equation 4.2        |   0% |             0% |          0% |            0% |
| Equation 4.3        |   0% |             0% |          0% |            0% |

### Equation 4.2
\(
    (4.2)  \quad 
    \mathbf{B} \equiv (\mathbf{H}, \mathbf{E})
\)
### Implementation
[TODO]
### Conformance
[TODO]
### Documentation
To aid comprehension and definition of our protocol, we partition as many of our terms as possible into their functional components. We begin with the block $B$ which may be restated as the header $H$ and some input data external to the system and thus said to be \emph{extrinsic}, $\mathbf{E}$:
### References
[TODO]

### Equation 4.3
\(
    (4.3)  \quad 
    \mathbf{E} \equiv (\xttickets, \xtdisputes, \xtguarantees, \xtassurances, \xtpreimages)
\)
### Implementation
[TODO]
### Conformance
[TODO]
### Documentation
To aid comprehension and definition of our protocol, we partition as many of our terms as possible into their functional components. We begin with the block \(\mathbf{B}\) which may be restated as the header \(\mathbf{H}\) and some input data external to the system and thus said to be _extrinsic_, \(\mathbf{E}\):
### References
[TODO]

## 4.2. The State 
| Graypaper Reference | Stub | Implementation | Conformance | Documentation |
|---------------------|-----:|---------------:|------------:|--------------:|
| Equation 4.4        |   0% |             0% |          0% |            0% |

### Equation 4.4
\(
    (4.4)  \quad 
    \sigma \equiv (\alpha, \beta, \gamma, \delta, \eta, \iota, \kappa, \lambda, \rho, \tau, \varphi, \chi, \psi, \pi, \ready, \accumulated)
\)
### Implementation
[TODO]
### Conformance
[TODO]
### Documentation
Our state may be logically partitioned into several largely independent segments which can both help avoid visual clutter within our protocol description and provide formality over elements of computation which may be simultaneously calculated (i.e. parallelized). We therefore pronounce an equivalence between \(\sigma\) (some complete state) and a tuple of partitioned segments of that state:
### References
[TODO]

### 4.2.1. State Transition Dependency Graph 
| Graypaper Reference | Stub | Implementation | Conformance | Documentation |
|---------------------|-----:|---------------:|------------:|--------------:|
| Equation 4.5        |   0% |             0% |          0% |            0% |
| Equation 4.6        |   0% |             0% |          0% |            0% |
| Equation 4.7        |   0% |             0% |          0% |            0% |
| Equation 4.8        |   0% |             0% |          0% |            0% |
| Equation 4.9        |   0% |             0% |          0% |            0% |
| Equation 4.10       |   0% |             0% |          0% |            0% |
| Equation 4.11       |   0% |             0% |          0% |            0% |
| Equation 4.12       |   0% |             0% |          0% |            0% |
| Equation 4.13       |   0% |             0% |          0% |            0% |
| Equation 4.14       |   0% |             0% |          0% |            0% |
| Equation 4.15       |   0% |             0% |          0% |            0% |
| Equation 4.16       |   0% |             0% |          0% |            0% |
| Equation 4.17       |   0% |             0% |          0% |            0% |
| Equation 4.18       |   0% |             0% |          0% |            0% |
| Equation 4.19       |   0% |             0% |          0% |            0% |
| Equation 4.20       |   0% |             0% |          0% |            0% |

### Equation 4.5
\(
    (4.5)  \quad 
    \tau' \prec \mathbf{H}
\)

\(
    (4.6)  \quad 
    \beta^\dagger \prec (\mathbf{H}, \beta) \label{eq:betadagger} \\
\)

\(
    (4.7)  \quad 
    \beta' \prec (\mathbf{H}, \xtguarantees, \beta^\dagger, \beefycommitmap) \\
\)

\(
    (4.8)  \quad 
    \gamma' \prec (\mathbf{H}, \tau, \xttickets, \gamma, \iota, \eta', \kappa', \psi') \\
\)

\(
    (4.9)  \quad 
    \eta' \prec (\mathbf{H}, \tau, \eta) \\
\)

\(
    (4.10)  \quad 
    \kappa' \prec (\mathbf{H}, \tau, \kappa, \gamma) \\
\)

\(
    (4.11)  \quad 
    \lambda' \prec (\mathbf{H}, \tau, \lambda, \kappa) \\
\)

\(
    (4.12)  \quad 
    \psi' \prec (\xtdisputes, \psi) \\
\)

\(
    (4.13)  \quad 
    \rho^\dagger \prec (\xtdisputes, \rho) \label{eq:rhodagger} \\
\)

\(
    (4.14)  \quad 
    \rho^\ddagger \prec (\xtassurances, \rho^\dagger) \label{eq:rhoddagger} \\
\)

\(
    (4.15)  \quad 
    \rho' \prec (\xtguarantees, \rho^\ddagger, \kappa, \tau') \\
\)

\(
    (4.16)  \quad 
    \mathbf{W}^* \prec (\xtassurances, \rho') \\
\)

\(
    (4.17)  \quad 
    (\ready', \accumulated', \accountspostxfer, \chi', \iota', \varphi', \beefycommitmap) \prec (\mathbf{W}^*, \ready, \accumulated, \accountspre, \chi, \iota, \varphi) \\
\)

\(
    (4.18)  \quad 
    \accountspostpreimage \prec (\xtpreimages, \accountspostxfer, \tau') \label{eq:accountspostpreimage} \\
\)

\(
    (4.19)  \quad 
    \alpha' \prec (\mathbf{H}, \xtguarantees, \varphi', \alpha) \\
\)

\(
    (4.20)  \quad
    \pi' \prec (\xtguarantees, \xtpreimages, \xtassurances, \xttickets, \tau, \kappa', \pi, \mathbf{H})
\)

### Implementation
[TODO]
### Conformance
[TODO]
### Documentation
### References
[TODO]

### Equation 4.6
\(
\)
### Implementation
[TODO]
### Conformance
[TODO]
### Documentation
### References
[TODO]

### Equation 4.7
\(
\)
### Implementation
[TODO]
### Conformance
[TODO]
### Documentation
### References
[TODO]

### Equation 4.8
\(
\)
### Implementation
[TODO]
### Conformance
[TODO]
### Documentation
### References
[TODO]

### Equation 4.9
\(
\)
### Implementation
[TODO]
### Conformance
[TODO]
### Documentation
### References
[TODO]

### Equation 4.10
\(
\)
### Implementation
[TODO]
### Conformance
[TODO]
### Documentation
### References
[TODO]

### Equation 4.11
\(
\)
### Implementation
[TODO]
### Conformance
[TODO]
### Documentation
### References
[TODO]

### Equation 4.12
\(
\)
### Implementation
[TODO]
### Conformance
[TODO]
### Documentation
### References
[TODO]

### Equation 4.13
\(
\)
### Implementation
[TODO]
### Conformance
[TODO]
### Documentation
### References
[TODO]

### Equation 4.14
\(
\)
### Implementation
[TODO]
### Conformance
[TODO]
### Documentation
### References
[TODO]

### Equation 4.15
\(
\)
### Implementation
[TODO]
### Conformance
[TODO]
### Documentation
### References
[TODO]

### Equation 4.16
\(
\)
### Implementation
[TODO]
### Conformance
[TODO]
### Documentation
### References
[TODO]

### Equation 4.17
\(
\)
### Implementation
[TODO]
### Conformance
[TODO]
### Documentation
### References
[TODO]

### Equation 4.18
\(
\)
### Implementation
[TODO]
### Conformance
[TODO]
### Documentation
### References
[TODO]

### Equation 4.19
\(
\)
### Implementation
[TODO]
### Conformance
[TODO]
### Documentation
### References
[TODO]

### Equation 4.20
\(
\)
### Implementation
[TODO]
### Conformance
[TODO]
### Documentation
### References
[TODO]

## 4.6. Economics
| Graypaper Reference | Stub | Implementation | Conformance | Documentation |
|---------------------|-----:|---------------:|------------:|--------------:|
| Equation 4.21       |   0% |             0% |          0% |            0% |

## 4.7. The Virtual Machine and Gas
| Graypaper Reference | Stub | Implementation | Conformance | Documentation |
|---------------------|-----:|---------------:|------------:|--------------:|
| Equation 4.22       |   0% |             0% |          0% |            0% |
| Equation 4.23       |   0% |             0% |          0% |            0% |
| Equation 4.24       |   0% |             0% |          0% |            0% |
| Equation 4.25       |   0% |             0% |          0% |            0% |
| Equation 4.26       |   0% |             0% |          0% |            0% |
| Equation 4.27       |   0% |             0% |          0% |            0% |

## 4.8. Epochs and Slots
| Graypaper Reference | Stub | Implementation | Conformance | Documentation |
|---------------------|-----:|---------------:|------------:|--------------:|
| Equation 4.28       |   0% |             0% |          0% |            0% |
