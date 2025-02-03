\( {% include-markdown "./preamble.tex" comments=false %} \)
\( {% include-markdown "./appendix_a.tex" comments=false %} \)
# Appendix A. Polka Virtual Machine
The aim of this section is to provide a detailed implementation reference on Graypaper equation definitions.
This section has been updated to match Graypaper version 0.5.4.

## A.1. Basic Definition
| Graypaper               | Equation             | Implementation |
|-------------------------|----------------------|----------------|
| <a name="A.1">(A.1)</a> | $\equationapointone$ | [TODO]         |  
| <a name="A.2">(A.2)</a> | $\equationapointtwo$ | [TODO]         | 

## A.2. Instructions, Opcodes and Skip-distance
| Graypaper               | Equation               | Implementation |
|-------------------------|------------------------|----------------|
| <a name="A.3">(A.3)</a> | $\equationapointthree$ | [TODO]         |
| <a name="A.4">(A.4)</a> | $\equationapointfour$  | [TODO]         | 

## A.3. Basic Blocks and Termination Instructions
| Graypaper               | Equation              | Implementation |
|-------------------------|-----------------------|----------------|
| <a name="A.5">(A.5)</a> | $\equationapointfive$ | [TODO]         |

## A.4. Single-Step State Transition
| Graypaper                 | Equation                  | Implementation |
|---------------------------|---------------------------|----------------|
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
| <a name="A.16">(A.16)</a> | $\equationapointsixteen$  | [TODO]         |
| <a name="A.17">(A.17)</a> | $\equationapointseventeen$ | [TODO]         |
| <a name="A.18">(A.18)</a> | $\equationapointeighteen$ | [TODO]         |

## A.5. Instruction Tables
### A.5.1. Instructions without Arguments
| Graypaper                 | Equation                 | Implementation |
|---------------------------|--------------------------|----------------|
| <a name="A.19">(A.19)</a> | $\equationapointnineteen$ | [TODO]         |

| $\instructions_\imath$ | Name        | $\gas$ | Mutations          | Implementation |
|------------------------|-------------|--------|--------------------|----------------|
| 0                      | trap        | 0      | $\instructionzero$ | [TODO]         |
| 1                      | fallthrough | 0      | $\instructionone$  | [TODO]         |

### A.5.2. Instructions with Arguments of One Immediate
| Graypaper                 | Equation                   | Implementation |
|---------------------------|----------------------------|----------------|
| <a name="A.20">(A.20)</a> | $\equationapointtwenty$ | [TODO]         |

| $\instructions_\imath$ | Name   | $\gas$ | Mutations         | Implementation |
|------------------------|--------|--------|-------------------|----------------|
| 10                     | ecalli | 0      | $\instructionten$ | [TODO]         |

### A.5.3. Instructions with Arguments of One Register and One Extended Width Immediate
| Graypaper                 | Equation                  | Implementation |
|---------------------------|---------------------------|----------------|
| <a name="A.21">(A.21)</a> | $\equationapointtwentyone$ | [TODO]         |

| $\instructions_\imath$ | Name        | $\gas$ | Mutations            | Implementation |
|------------------------|-------------|--------|----------------------|----------------|
| 20                     | load_imm_64 | 0      | $\instructiontwenty$ | [TODO]         |

### A.5.4. Instructions with Arguments of Two Immediates
| Graypaper                 | Equation                  | Implementation |
|---------------------------|---------------------------|----------------|
| <a name="A.22">(A.22)</a> | $\equationapointtwentytwo$ | [TODO]         |

| $\instructions_\imath$ | Name          | $\gas$ | Mutations                 | Implementation |
|------------------------|---------------|--------|---------------------------|----------------|
| 30                     | store_imm_u8  | 0      | $\instructionthirty$      | [TODO]         |
| 31                     | store_imm_u16 | 0      | $\instructionthirtyone$   | [TODO]         |
| 32                     | store_imm_u32 | 0      | $\instructionthirtytwo$   | [TODO]         |
| 33                     | store_imm_u64 | 0      | $\instructionthirtythree$ | [TODO]         |

### A.5.5. Instructions with Arguments of One Offset
| Graypaper                 | Equation                | Implementation |
|---------------------------|-------------------------|----------------|
| <a name="A.23">(A.23)</a> | $\equationapointtwentythree$ | [TODO]         |

| $\instructions_\imath$ | Name | $\gas$ | Mutations           | Implementation |
|------------------------|------|--------|---------------------|----------------|
| 40                     | jump | 0      | $\instructionforty$ | [TODO]         |

### A.5.6. Instructions with Arguments of One Register & One Immediate
| Graypaper                 | Equation                   | Implementation |
|---------------------------|----------------------------|----------------|
| <a name="A.24">(A.24)</a> | $\equationapointtwentyfour$ | [TODO]         |

| $\instructions_\imath$ | Name | $\gas$ | Mutations                | Implementation |
|------------------------|------|--------|--------------------------|----------------|
| 50                     |      | 0      | $\instructionfifty$      | [TODO]         |
| 51                     |      | 0      | $\instructionfiftyone$   | [TODO]         |
| 52                     |      | 0      | $\instructionfiftytwo$   | [TODO]         |
| 53                     |      | 0      | $\instructionfiftythree$ | [TODO]         |
| 54                     |      | 0      | $\instructionfiftyfour$  | [TODO]         |
| 55                     |      | 0      | $\instructionfiftyfive$  | [TODO]         |
| 56                     |      | 0      | $\instructionfiftysix$   | [TODO]         |
| 57                     |      | 0      | $\instructionfiftyseven$ | [TODO]         |
| 58                     |      | 0      | $\instructionfiftyeight$ | [TODO]         |
| 59                     |      | 0      | $\instructionfiftynine$  | [TODO]         |
| 60                     |      | 0      | $\instructionsixty$      | [TODO]         |
| 61                     |      | 0      | $\instructionsixtyone$   | [TODO]         |
| 62                     |      | 0      | $\instructionsixtytwo$   | [TODO]         |

### A.5.7. Instructions with Arguments of One Register & Two Immediates
| Graypaper                 | Equation                   | Implementation |
|---------------------------|----------------------------|----------------|
| <a name="A.25">(A.25)</a> | $\equationapointtwentyfive$ | [TODO]         |

| $\instructions_\imath$ | Name           | $\gas$ | Mutations | Implementation |
|------------------------|----------------|--------|-----------|----------------|
| 50                     |      | 0      | $\instructionfifty$      | [TODO]         |
| 51                     |      | 0      | $\instructionfiftyone$   | [TODO]         |
| 52                     |      | 0      | $\instructionfiftytwo$   | [TODO]         |
| 53                     |      | 0      | $\instructionfiftythree$ | [TODO]         |
| 54                     |      | 0      | $\instructionfiftyfour$  | [TODO]         |
| 55                     |      | 0      | $\instructionfiftyfive$  | [TODO]         |
| 56                     |      | 0      | $\instructionfiftysix$   | [TODO]         |
| 57                     |      | 0      | $\instructionfiftyseven$ | [TODO]         |
| 58                     |      | 0      | $\instructionfiftyeight$ | [TODO]         |
| 59                     |      | 0      | $\instructionfiftynine$  | [TODO]         |
| 60                     |      | 0      | $\instructionsixty$      | [TODO]         |
| 61                     |      | 0      | $\instructionsixtyone$   | [TODO]         |
| 62                     |      | 0      | $\instructionsixtytwo$   | [TODO]         |

### A.5.8. Instructions with Arguments of One Register, One Immediate & One Offset
| Graypaper                 | Equation                   | Implementation |
|---------------------------|----------------------------|----------------|
| <a name="A.26">(A.26)</a> | $\equationapointtwentysix$ | [TODO]         |

| $\instructions_\imath$ | Name           | $\gas$ | Mutations | Implementation |
|------------------------|----------------|--------|-----------|----------------|
| 50                     |      | 0      | $\instructionfifty$      | [TODO]         |
| 51                     |      | 0      | $\instructionfiftyone$   | [TODO]         |
| 52                     |      | 0      | $\instructionfiftytwo$   | [TODO]         |
| 53                     |      | 0      | $\instructionfiftythree$ | [TODO]         |
| 54                     |      | 0      | $\instructionfiftyfour$  | [TODO]         |
| 55                     |      | 0      | $\instructionfiftyfive$  | [TODO]         |
| 56                     |      | 0      | $\instructionfiftysix$   | [TODO]         |
| 57                     |      | 0      | $\instructionfiftyseven$ | [TODO]         |
| 58                     |      | 0      | $\instructionfiftyeight$ | [TODO]         |
| 59                     |      | 0      | $\instructionfiftynine$  | [TODO]         |
| 60                     |      | 0      | $\instructionsixty$      | [TODO]         |
| 61                     |      | 0      | $\instructionsixtyone$   | [TODO]         |
| 62                     |      | 0      | $\instructionsixtytwo$   | [TODO]         |

### A.5.9. Instructions with Arguments of Two Registers
| Graypaper                 | Equation                     | Implementation |
|---------------------------|------------------------------|----------------|
| <a name="A.27">(A.27)</a> | $\equationapointtwentyseven$ | [TODO]         |

| $\instructions_\imath$ | Name           | $\gas$ | Mutations | Implementation |
|------------------------|----------------|--------|-----------|----------------|
| 50                     |      | 0      | $\instructionfifty$      | [TODO]         |
| 51                     |      | 0      | $\instructionfiftyone$   | [TODO]         |
| 52                     |      | 0      | $\instructionfiftytwo$   | [TODO]         |
| 53                     |      | 0      | $\instructionfiftythree$ | [TODO]         |
| 54                     |      | 0      | $\instructionfiftyfour$  | [TODO]         |
| 55                     |      | 0      | $\instructionfiftyfive$  | [TODO]         |
| 56                     |      | 0      | $\instructionfiftysix$   | [TODO]         |
| 57                     |      | 0      | $\instructionfiftyseven$ | [TODO]         |
| 58                     |      | 0      | $\instructionfiftyeight$ | [TODO]         |
| 59                     |      | 0      | $\instructionfiftynine$  | [TODO]         |
| 60                     |      | 0      | $\instructionsixty$      | [TODO]         |
| 61                     |      | 0      | $\instructionsixtyone$   | [TODO]         |
| 62                     |      | 0      | $\instructionsixtytwo$   | [TODO]         |

### A.5.10. Instructions with Arguments of Two Registers & One Immediate
| Graypaper                 | Equation                     | Implementation |
|---------------------------|------------------------------|----------------|
| <a name="A.28">(A.28)</a> | $\equationapointtwentyeight$ | [TODO]         |

| $\instructions_\imath$ | Name           | $\gas$ | Mutations | Implementation |
|------------------------|----------------|--------|-----------|----------------|
| 50                     |      | 0      | $\instructionfifty$      | [TODO]         |
| 51                     |      | 0      | $\instructionfiftyone$   | [TODO]         |
| 52                     |      | 0      | $\instructionfiftytwo$   | [TODO]         |
| 53                     |      | 0      | $\instructionfiftythree$ | [TODO]         |
| 54                     |      | 0      | $\instructionfiftyfour$  | [TODO]         |
| 55                     |      | 0      | $\instructionfiftyfive$  | [TODO]         |
| 56                     |      | 0      | $\instructionfiftysix$   | [TODO]         |
| 57                     |      | 0      | $\instructionfiftyseven$ | [TODO]         |
| 58                     |      | 0      | $\instructionfiftyeight$ | [TODO]         |
| 59                     |      | 0      | $\instructionfiftynine$  | [TODO]         |
| 60                     |      | 0      | $\instructionsixty$      | [TODO]         |
| 61                     |      | 0      | $\instructionsixtyone$   | [TODO]         |
| 62                     |      | 0      | $\instructionsixtytwo$   | [TODO]         |

### A.5.11. Instructions with Arguments of Two Registers & One Offset
| Graypaper                 | Equation                    | Implementation |
|---------------------------|-----------------------------|----------------|
| <a name="A.29">(A.29)</a> | $\equationapointtwentynine$ | [TODO]         |

| $\instructions_\imath$ | Name           | $\gas$ | Mutations | Implementation |
|------------------------|----------------|--------|-----------|----------------|
| 50                     |      | 0      | $\instructionfifty$      | [TODO]         |
| 51                     |      | 0      | $\instructionfiftyone$   | [TODO]         |
| 52                     |      | 0      | $\instructionfiftytwo$   | [TODO]         |
| 53                     |      | 0      | $\instructionfiftythree$ | [TODO]         |
| 54                     |      | 0      | $\instructionfiftyfour$  | [TODO]         |
| 55                     |      | 0      | $\instructionfiftyfive$  | [TODO]         |
| 56                     |      | 0      | $\instructionfiftysix$   | [TODO]         |
| 57                     |      | 0      | $\instructionfiftyseven$ | [TODO]         |
| 58                     |      | 0      | $\instructionfiftyeight$ | [TODO]         |
| 59                     |      | 0      | $\instructionfiftynine$  | [TODO]         |
| 60                     |      | 0      | $\instructionsixty$      | [TODO]         |
| 61                     |      | 0      | $\instructionsixtyone$   | [TODO]         |
| 62                     |      | 0      | $\instructionsixtytwo$   | [TODO]         |

### A.5.12. Instructions with Arguments of Two Registers & Two Immediates
| Graypaper                 | Equation                | Implementation |
|---------------------------|-------------------------|----------------|
| <a name="A.30">(A.30)</a> | $\equationapointthirty$ | [TODO]         |

| $\instructions_\imath$ | Name           | $\gas$ | Mutations | Implementation |
|------------------------|----------------|--------|-----------|----------------|
| 50                     |      | 0      | $\instructionfifty$      | [TODO]         |
| 51                     |      | 0      | $\instructionfiftyone$   | [TODO]         |
| 52                     |      | 0      | $\instructionfiftytwo$   | [TODO]         |
| 53                     |      | 0      | $\instructionfiftythree$ | [TODO]         |
| 54                     |      | 0      | $\instructionfiftyfour$  | [TODO]         |
| 55                     |      | 0      | $\instructionfiftyfive$  | [TODO]         |
| 56                     |      | 0      | $\instructionfiftysix$   | [TODO]         |
| 57                     |      | 0      | $\instructionfiftyseven$ | [TODO]         |
| 58                     |      | 0      | $\instructionfiftyeight$ | [TODO]         |
| 59                     |      | 0      | $\instructionfiftynine$  | [TODO]         |
| 60                     |      | 0      | $\instructionsixty$      | [TODO]         |
| 61                     |      | 0      | $\instructionsixtyone$   | [TODO]         |
| 62                     |      | 0      | $\instructionsixtytwo$   | [TODO]         |

### A.5.13. Instructions with Arguments of Three Registers
| Graypaper                 | Equation                   | Implementation |
|---------------------------|----------------------------|----------------|
| <a name="A.31">(A.31)</a> | $\equationapointthirtyone$ | [TODO]         |

| $\instructions_\imath$ | Name           | $\gas$ | Mutations | Implementation |
|------------------------|----------------|--------|-----------|----------------|
| 50                     |      | 0      | $\instructionfifty$      | [TODO]         |
| 51                     |      | 0      | $\instructionfiftyone$   | [TODO]         |
| 52                     |      | 0      | $\instructionfiftytwo$   | [TODO]         |
| 53                     |      | 0      | $\instructionfiftythree$ | [TODO]         |
| 54                     |      | 0      | $\instructionfiftyfour$  | [TODO]         |
| 55                     |      | 0      | $\instructionfiftyfive$  | [TODO]         |
| 56                     |      | 0      | $\instructionfiftysix$   | [TODO]         |
| 57                     |      | 0      | $\instructionfiftyseven$ | [TODO]         |
| 58                     |      | 0      | $\instructionfiftyeight$ | [TODO]         |
| 59                     |      | 0      | $\instructionfiftynine$  | [TODO]         |
| 60                     |      | 0      | $\instructionsixty$      | [TODO]         |
| 61                     |      | 0      | $\instructionsixtyone$   | [TODO]         |
| 62                     |      | 0      | $\instructionsixtytwo$   | [TODO]         |

| Graypaper                   | Equation                     | Implementation |
|-----------------------------|------------------------------|----------------|
| <a name="A.29a">(A.29a)</a> | $\equationapointtwentyninea$ | [TODO]         |

\(
    \reg'_D = \begin{cases}
        0 \quad \when a = -2^{31} \wedge b = -1 \\
        \unsigned{\smod(a, b)} \quad \otherwise \\
        \quad \where a = \signedn{4}{\reg_A \bmod 2^{32}}\,,\ b = \signedn{4}{\reg_B \bmod 2^{32}}
    \end{cases}
\)

\(
    \reg'_D = \begin{cases}
        0 \quad \when \signed{\reg_A} = -2^{63} \wedge \signed{\reg_B} = -1\\
        \unsigned{\smod(\signed{\reg_A}, \signed{\reg_B})} \quad \otherwise
    \end{cases}
\)

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
