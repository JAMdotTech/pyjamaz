\( {% include-markdown "./preamble.tex" comments=false %} \)
\( {% include-markdown "./appendix_a.tex" comments=false %} \)
# Appendix A. Polka Virtual Machine
The aim of this section is to provide a detailed implementation reference on Graypaper equation definitions.
This section has been updated to match Graypaper version 0.5.4.

## A.1. Basic Definition
| Graypaper               | Equation             | Implementation |
|-------------------------|----------------------|----------------|
| <a name="A.1">(A.1)</a> | $\equationapointone$ | [TODO]         |  

## A.2. Instructions, Opcodes and Skip-distance
| Graypaper               | Equation               | Implementation |
|-------------------------|------------------------|----------------|
| <a name="A.2">(A.2)</a> | $\equationapointtwo$   | [TODO]         | 
| <a name="A.3">(A.3)</a> | $\equationapointthree$ | [TODO]         |

## A.3. Basic Blocks and Termination Instructions
| Graypaper               | Equation              | Implementation |
|-------------------------|-----------------------|----------------|
| <a name="A.4">(A.4)</a> | $\equationapointfour$ | [TODO]         | 

## A.4. Single-Step State Transition
| Graypaper                 | Equation                  | Implementation |
|---------------------------|---------------------------|----------------|
| <a name="A.5">(A.5)</a>   | $\equationapointfive$     | [TODO]         |
| <a name="A.6">(A.6)</a>   | $\equationapointsix$      | [TODO]         |
| <a name="A.7">(A.7)</a>   | $\equationapointseven$    | [TODO]         |
| <a name="A.8">(A.8)</a>   | $\equationapointeight$    | [TODO]         |
| <a name="A.9">(A.9)</a>   | $\equationapointnine$     | [TODO]         |
| <a name="A.10">(A.10)</a> | $\equationapointten$      | [TODO]         |
| <a name="A.11">(A.11)</a> | $\equationapointeleven$   | [TODO]         |
| <a name="A.12">(A.12)</a> | $\equationapointtwelve$   | [TODO]         |
| <a name="A.13">(A.13)</a> | $\equationapointthirteen$ | [TODO]         |
| <a name="A.14">(A.14)</a> | $\equationapointfourteen$ | [TODO]         |
| <a name="A.15">(A.15)</a> | $\equationapointfifteen$  | [TODO]         |

## A.5. Instruction Tables
### A.5.1. Instructions without Arguments
| Graypaper                 | Equation                 | Implementation |
|---------------------------|--------------------------|----------------|
| <a name="A.16">(A.16)</a> | $\equationapointsixteen$ | [TODO]         |

| $\instructions_\imath$ | Name                  | $\gas$ | Mutations              | Implementation |
|------------------------|-----------------------|--------|------------------------|----------------|
| 0                      | $\token{trap}$        | 0      | $\varepsilon = \panic$ | [TODO]         |
| 1                      | $\token{fallthrough}$ | 0      | $\\$                   | [TODO]         |

### A.5.2. Instructions with Arguments of One Immediate
| Graypaper                 | Equation                   | Implementation |
|---------------------------|----------------------------|----------------|
| <a name="A.17">(A.17)</a> | $\equationapointseventeen$ | [TODO]         |

| $\instructions_\imath$ | Name             | $\gas$ | Mutations                             | Implementation |
|------------------------|------------------|--------|---------------------------------------|----------------|
| 10                     | $\token{ecalli}$ | 0      | $\varepsilon = \host \times \immed_X$ | [TODO]         |

### A.5.3. Instructions with Arguments of One Register and One Extended Width Immediate
| Graypaper                 | Equation                  | Implementation |
|---------------------------|---------------------------|----------------|
| <a name="A.18">(A.18)</a> | $\equationapointeighteen$ | [TODO]         |

| $\instructions_\imath$ | Name                      | $\gas$ | Mutations                                                 | Implementation |
|------------------------|---------------------------|--------|-----------------------------------------------------------|----------------|
| 30                     | $\token{store\_imm\_u8}$  | 0      | $\memwr_{\immed_X} = \immed_Y \bmod 2^8$                  | [TODO]         |
| 31                     | $\token{store\_imm\_u16}$ | 0      | $\memwr_{\immed_X\dots+2} = \se_2(\immed_Y \bmod 2^{16})$ | [TODO]         |
| 32                     | $\token{store\_imm\_u32}$ | 0      | $\memwr_{\immed_X\dots+4} = \se_4(\immed_Y \bmod 2^{32})$ | [TODO]         |
| 33                     | $\token{store\_imm\_u64}$ | 0      | $\memwr_{\immed_X\dots+8} = \se_8(\immed_Y)$              | [TODO]         |


### A.5.4. Instructions with Arguments of Two Immediates
| Graypaper                 | Equation                  | Implementation |
|---------------------------|---------------------------|----------------|
| <a name="A.19">(A.19)</a> | $\equationapointnineteen$ | [TODO]         |

| $\instructions_\imath$ | Name           | $\gas$ | Mutations | Implementation |
|------------------------|----------------|--------|-----------|----------------|
| XX                     | $\token{XXXX}$ | 0      | $$        | [TODO]         |

### A.5.5. Instructions with Arguments of One Offset
| Graypaper                 | Equation                | Implementation |
|---------------------------|-------------------------|----------------|
| <a name="A.20">(A.20)</a> | $\equationapointtwenty$ | [TODO]         |

| $\instructions_\imath$ | Name           | $\gas$ | Mutations | Implementation |
|------------------------|----------------|--------|-----------|----------------|
| XX                     | $\token{XXXX}$ | 0      | $$        | [TODO]         |

### A.5.6. Instructions with Arguments of One Register & One Immediate
| Graypaper                 | Equation                   | Implementation |
|---------------------------|----------------------------|----------------|
| <a name="A.21">(A.21)</a> | $\equationapointtwentyone$ | [TODO]         |

| $\instructions_\imath$ | Name           | $\gas$ | Mutations | Implementation |
|------------------------|----------------|--------|-----------|----------------|
| XX                     | $\token{XXXX}$ | 0      | $$        | [TODO]         |

### A.5.7. Instructions with Arguments of One Register & Two Immediates
| Graypaper                 | Equation                   | Implementation |
|---------------------------|----------------------------|----------------|
| <a name="A.22">(A.22)</a> | $\equationapointtwentytwo$ | [TODO]         |

| $\instructions_\imath$ | Name           | $\gas$ | Mutations | Implementation |
|------------------------|----------------|--------|-----------|----------------|
| XX                     | $\token{XXXX}$ | 0      | $$        | [TODO]         |

### A.5.8. Instructions with Arguments of One Register, One Immediate & One Offset
| Graypaper                 | Equation                     | Implementation |
|---------------------------|------------------------------|----------------|
| <a name="A.23">(A.23)</a> | $\equationapointtwentythree$ | [TODO]         |

| $\instructions_\imath$ | Name           | $\gas$ | Mutations | Implementation |
|------------------------|----------------|--------|-----------|----------------|
| XX                     | $\token{XXXX}$ | 0      | $$        | [TODO]         |

### A.5.9. Instructions with Arguments of Two Registers
| Graypaper                 | Equation                    | Implementation |
|---------------------------|-----------------------------|----------------|
| <a name="A.24">(A.24)</a> | $\equationapointtwentyfour$ | [TODO]         |

| $\instructions_\imath$ | Name           | $\gas$ | Mutations | Implementation |
|------------------------|----------------|--------|-----------|----------------|
| XX                     | $\token{XXXX}$ | 0      | $$        | [TODO]         |

### A.5.10. Instructions with Arguments of Two Registers & One Immediate
| Graypaper                 | Equation                    | Implementation |
|---------------------------|-----------------------------|----------------|
| <a name="A.25">(A.25)</a> | $\equationapointtwentyfive$ | [TODO]         |

| $\instructions_\imath$ | Name           | $\gas$ | Mutations | Implementation |
|------------------------|----------------|--------|-----------|----------------|
| XX                     | $\token{XXXX}$ | 0      | $$        | [TODO]         |

### A.5.11. Instructions with Arguments of Two Registers & One Offset
| Graypaper                 | Equation                   | Implementation |
|---------------------------|----------------------------|----------------|
| <a name="A.26">(A.26)</a> | $\equationapointtwentysix$ | [TODO]         |

| $\instructions_\imath$ | Name           | $\gas$ | Mutations | Implementation |
|------------------------|----------------|--------|-----------|----------------|
| XX                     | $\token{XXXX}$ | 0      | $$        | [TODO]         |

### A.5.12. Instructions with Arguments of Two Registers & Two Immediates
| Graypaper                 | Equation                     | Implementation |
|---------------------------|------------------------------|----------------|
| <a name="A.27">(A.27)</a> | $\equationapointtwentyseven$ | [TODO]         |

| $\instructions_\imath$ | Name           | $\gas$ | Mutations | Implementation |
|------------------------|----------------|--------|-----------|----------------|
| XX                     | $\token{XXXX}$ | 0      | $$        | [TODO]         |

### A.5.13. Instructions with Arguments of Three Registers
| Graypaper                 | Equation                     | Implementation |
|---------------------------|------------------------------|----------------|
| <a name="A.28">(A.28)</a> | $\equationapointtwentyeight$ | [TODO]         |

| $\instructions_\imath$ | Name           | $\gas$ | Mutations | Implementation |
|------------------------|----------------|--------|-----------|----------------|
| XX                     | $\token{XXXX}$ | 0      | $$        | [TODO]         |

## A.6. Host Call Definition
| Graypaper                 | Equation                    | Implementation |
|---------------------------|-----------------------------|----------------|
| <a name="A.29">(A.29)</a> | $\equationapointtwentynine$ | [TODO]         |
| <a name="A.30">(A.30)</a> | $\equationapointthirty$     | [TODO]         |

## A.7. Standard Program Initialization
| Graypaper                 | Equation                     | Implementation |
|---------------------------|------------------------------|----------------|
| <a name="A.31">(A.31)</a> | $\equationapointthirtyone$   | [TODO]         |
| <a name="A.32">(A.32)</a> | $\equationapointthirtytwo$   | [TODO]         |
| <a name="A.33">(A.33)</a> | $\equationapointthirtythree$ | [TODO]         |
| <a name="A.34">(A.34)</a> | $\equationapointthirtyfour$  | [TODO]         |
| <a name="A.35">(A.35)</a> | $\equationapointthirtyfive$  | [TODO]         |
| <a name="A.36">(A.36)</a> | $\equationapointthirtysix$   | [TODO]         |
| <a name="A.37">(A.37)</a> | $\equationapointthirtyseven$ | [TODO]         |

## A.8. Argument Invocation Definition
| Graypaper                 | Equation                     | Implementation |
|---------------------------|------------------------------|----------------|
| <a name="A.38">(A.38)</a> | $\equationapointthirtyeight$ | [TODO]         |
| <a name="A.39">(A.39)</a> | $\equationapointthirtynine$  | [TODO]         |
