\( {% include-markdown "./preamble.tex" comments=false %} \)
\( {% include-markdown "./section_04.tex" comments=false %} \)
# 4. Overview
## 4.0. General
The aim of this section is to provide a detailed implementation reference on Graypaper equation definitions.
This section has been updated to match Graypaper version 0.6.2.

We begin our formalisms by recalling that a blockchain may be defined as a pairing of some initial state together with a block-level state-transition function. The latter defines the posterior state given a pairing of some prior state and a block of data applied to it.

| ID                      | Equation                | Implementation |
|-------------------------|-------------------------|----------------|
| <a name="4.1">(4.1)</a> | $\equationfourpointone$ | [TODO]         |

## 4.1. The Block
To aid comprehension and definition of our protocol, we partition as many of our terms as possible into their functional components. We begin with the block $\mathbf{B}$ which may be restated as the header $\mathbf{H}$ and some input data external to the system and thus said to be _extrinsic_, $\mathbf{E}$

| Graypaper               | Equation                  | Implementation                                                   |
|-------------------------|---------------------------|------------------------------------------------------------------|
| <a name="4.2">(4.2)</a> | $\equationfourpointtwo$   | [Link](/types/types_blocks/#pyjamaz.models.block.Block)     |
| <a name="4.3">(4.3)</a> | $\equationfourpointthree$ | [Link](/types/types_blocks/#pyjamaz.models.block.Extrinsic) |

## 4.2. The State 
Our state may be logically partitioned into several largely independent segments which can both help avoid visual clutter within our protocol description and provide formality over elements of computation which may be simultaneously calculated (i.e. parallelized). We therefore pronounce an equivalence between $\sigma$ (some complete state) and a tuple of partitioned segments of that state.

| Graypaper               | Equation                 | Implementation                                                 |
|-------------------------|--------------------------|----------------------------------------------------------------|
| <a name="4.4">(4.4)</a> | $\equationfourpointfour$ | [Link](/types/types_state/#pyjamaz.models.state.JamState) |

### 4.2.1. State Transition Dependency Graph 
| Graypaper                 | Equation                      | Implementation |
|---------------------------|-------------------------------|----------------|
| <a name="4.5">(4.5)</a>   | $\equationfourpointfive$      | [TODO]         |
| <a name="4.6">(4.6)</a>   | $\equationfourpointsix$       | [TODO]         |
| <a name="4.7">(4.7)</a>   | $\equationfourpointseven$     | [TODO]         |
| <a name="4.8">(4.8)</a>   | $\equationfourpointeight$     | [TODO]         |
| <a name="4.9">(4.9)</a>   | $\equationfourpointnine$      | [TODO]         |
| <a name="4.10">(4.10)</a> | $\equationfourpointten$       | [TODO]         |
| <a name="4.11">(4.11)</a> | $\equationfourpointeleven$    | [TODO]         |
| <a name="4.12">(4.12)</a> | $\equationfourpointtwelve$    | [TODO]         |
| <a name="4.13">(4.13)</a> | $\equationfourpointthirteen$  | [TODO]         |
| <a name="4.14">(4.14)</a> | $\equationfourpointfourteen$  | [TODO]         |
| <a name="4.15">(4.15)</a> | $\equationfourpointfifteen$   | [TODO]         |
| <a name="4.16">(4.16)</a> | $\equationfourpointsixteen$   | [TODO]         |
| <a name="4.17">(4.17)</a> | $\equationfourpointseventeen$ | [TODO]         |
| <a name="4.18">(4.18)</a> | $\equationfourpointeighteen$  | [TODO]         |
| <a name="4.19">(4.19)</a> | $\equationfourpointnineteen$  | [TODO]         |
| <a name="4.20">(4.20)</a> | $\equationfourpointtwenty$    | [TODO]         |

## 4.6. Economics
A value of tokens is generally referred to as a _balance_, and such a value is said to be a member of the set of balances, $\N_B$, which is exactly equivalent to the set of naturals less than $2^{64}$ (\ie 64-bit unsigned integers in coding parlance).

| Graypaper                 | Equation                      | Implementation |
|---------------------------|-------------------------------|----------------|
| <a name="4.21">(4.21)</a> | $\equationfourpointtwentyone$ | [TODO]         |

## 4.7. The Virtual Machine and Gas
| Graypaper                 | Equation                        | Implementation |
|---------------------------|---------------------------------|----------------|
| <a name="4.22">(4.22)</a> | $\equationfourpointtwentytwo$   | [TODO]         |
| <a name="4.23">(4.23)</a> | $\equationfourpointtwentythree$ | [TODO]         |
| <a name="4.24">(4.24)</a> | $\equationfourpointtwentyfour$  | [TODO]         |
| <a name="4.25">(4.25)</a> | $\equationfourpointtwentyfive$  | [TODO]         |
| <a name="4.26">(4.26)</a> | $\equationfourpointtwentysix$   | [TODO]         |
| <a name="4.27">(4.27)</a> | $\equationfourpointtwentyseven$ | [TODO]         |

## 4.8. Epochs and Slots
| Graypaper                 | Equation                        | Implementation |
|---------------------------|---------------------------------|----------------|
| <a name="4.28">(4.28)</a> | $\equationfourpointtwentyeight$ | [TODO]         |
