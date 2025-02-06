\( {% include-markdown "./preamble.tex" comments=false %} \)
\( {% include-markdown "./appendix_a.tex" comments=false %} \)
# Appendix A. Polka Virtual Machine
The aim of this section is to provide a detailed implementation reference on Graypaper equation definitions.
This section has been updated to match Graypaper version 0.6.2.

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

| $\instructions_\imath$ | Name      | $\gas$ | Mutations                | Implementation |
|------------------------|-----------|--------|--------------------------|----------------|
| 50                     | jump\_ind | 0      | $\instructionfifty$      | [TODO]         |
| 51                     | load\_imm | 0      | $\instructionfiftyone$   | [TODO]         |
| 52                     | load\_u8  | 0      | $\instructionfiftytwo$   | [TODO]         |
| 53                     | load_i8   | 0      | $\instructionfiftythree$ | [TODO]         |
| 54                     | load_u16  | 0      | $\instructionfiftyfour$  | [TODO]         |
| 55                     | load_i16  | 0      | $\instructionfiftyfive$  | [TODO]         |
| 56                     | load_u32  | 0      | $\instructionfiftysix$   | [TODO]         |
| 57                     | load_i32  | 0      | $\instructionfiftyseven$ | [TODO]         |
| 58                     | load_u64  | 0      | $\instructionfiftyeight$ | [TODO]         |
| 59                     | store_u8  | 0      | $\instructionfiftynine$  | [TODO]         |
| 60                     | store_u16 | 0      | $\instructionsixty$      | [TODO]         |
| 61                     | store_u32 | 0      | $\instructionsixtyone$   | [TODO]         |
| 62                     | store_u64 | 0      | $\instructionsixtytwo$   | [TODO]         |

### A.5.7. Instructions with Arguments of One Register & Two Immediates
| Graypaper                 | Equation                   | Implementation |
|---------------------------|----------------------------|----------------|
| <a name="A.25">(A.25)</a> | $\equationapointtwentyfive$ | [TODO]         |

| $\instructions_\imath$ | Name              | $\gas$ | Mutations                  | Implementation |
|------------------------|-------------------|--------|----------------------------|----------------|
| 70                     | store_imm_ind_u8  | 0      | $\instructionseventy$      | [TODO]         |
| 71                     | store_imm_ind_u16 | 0      | $\instructionseventyone$   | [TODO]         |
| 72                     | store_imm_ind_u32 | 0      | $\instructionseventytwo$   | [TODO]         |
| 73                     | store_imm_ind_u64 | 0      | $\instructionseventythree$ | [TODO]         |

### A.5.8. Instructions with Arguments of One Register, One Immediate & One Offset
| Graypaper                 | Equation                   | Implementation |
|---------------------------|----------------------------|----------------|
| <a name="A.26">(A.26)</a> | $\equationapointtwentysix$ | [TODO]         |

| $\instructions_\imath$ | Name            | $\gas$ | Mutations                 | Implementation |
|------------------------|-----------------|--------|---------------------------|----------------|
| 80                     | load_imm_jump   | 0      | $\instructioneighty$      | [TODO]         |
| 81                     | branch_eq_imm   | 0      | $\instructioneightyone$   | [TODO]         |
| 82                     | branch_ne_imm   | 0      | $\instructioneightytwo$   | [TODO]         |
| 83                     | branch_lt_u_imm | 0      | $\instructioneightythree$ | [TODO]         |
| 84                     | branch_le_u_imm | 0      | $\instructioneightyfour$  | [TODO]         |
| 85                     | branch_ge_u_imm | 0      | $\instructioneightyfive$  | [TODO]         |
| 86                     | branch_gt_u_imm | 0      | $\instructioneightysix$   | [TODO]         |
| 87                     | branch_lt_s_imm | 0      | $\instructioneightyseven$ | [TODO]         |
| 88                     | branch_le_s_imm | 0      | $\instructioneightyeight$ | [TODO]         |
| 89                     | branch_ge_s_imm | 0      | $\instructioneightynine$  | [TODO]         |
| 90                     | branch_gt_s_imm | 0      | $\instructionninety$      | [TODO]         |

### A.5.9. Instructions with Arguments of Two Registers
| Graypaper                 | Equation                     | Implementation |
|---------------------------|------------------------------|----------------|
| <a name="A.27">(A.27)</a> | $\equationapointtwentyseven$ | [TODO]         |

| $\instructions_\imath$ | Name                  | $\gas$ | Mutations                      | Implementation |
|------------------------|-----------------------|--------|--------------------------------|----------------|
| 100                    | move_reg              | 0      | $\instructiononehundred$       | [TODO]         |
| 101                    | sbrk                  | 0      | $\instructiononehundredone$    | [TODO]         |
| 102                    | count_set_bits_64     | 0      | $\instructiononehundredtwo$    | [TODO]         |
| 103                    | count_set_bits_32     | 0      | $\instructiononehundredthree$  | [TODO]         |
| 104                    | leading_zero_bits_64  | 0      | $\instructiononehundredfour$   | [TODO]         |
| 105                    | leading_zero_bits_32  | 0      | $\instructiononehundredfive$   | [TODO]         |
| 106                    | trailing_zero_bits_64 | 0      | $\instructiononehundredsix$    | [TODO]         |
| 107                    | trailing_zero_bits_32 | 0      | $\instructiononehundredseven$  | [TODO]         |
| 108                    | sign_extend_8         | 0      | $\instructiononehundredeight$  | [TODO]         |
| 109                    | sign_extend_16        | 0      | $\instructiononehundrednine$   | [TODO]         |
| 110                    | zero_extend_16        | 0      | $\instructiononehundredten$    | [TODO]         |
| 111                    | reverse_bytes         | 0      | $\instructiononehundredeleven$ | [TODO]         |

### A.5.10. Instructions with Arguments of Two Registers & One Immediate
| Graypaper                 | Equation                     | Implementation |
|---------------------------|------------------------------|----------------|
| <a name="A.28">(A.28)</a> | $\equationapointtwentyeight$ | [TODO]         |

| $\instructions_\imath$ | Name              | $\gas$ | Mutations                           | Implementation |
|------------------------|-------------------|--------|-------------------------------------|----------------|
| 120                    | store_ind_u8      | 0      | $\instructiononehundredtwenty$      | [TODO]         |
| 121                    | store_ind_u16     | 0      | $\instructiononehundredtwentyone$   | [TODO]         |
| 122                    | store_ind_u32     | 0      | $\instructiononehundredtwentytwo$   | [TODO]         |
| 123                    | store_ind_u64     | 0      | $\instructiononehundredtwentythree$ | [TODO]         |
| 124                    | load_ind_u8       | 0      | $\instructiononehundredtwentyfour$  | [TODO]         |
| 125                    | load_ind_i8       | 0      | $\instructiononehundredtwentyfive$  | [TODO]         |
| 126                    | load_ind_u16      | 0      | $\instructiononehundredtwentysix$   | [TODO]         |
| 127                    | load_ind_i16      | 0      | $\instructiononehundredtwentyseven$ | [TODO]         |
| 128                    | load_ind_u32      | 0      | $\instructiononehundredtwentyeight$ | [TODO]         |
| 129                    | load_ind_i32      | 0      | $\instructiononehundredtwentynine$  | [TODO]         |
| 130                    | load_ind_u64      | 0      | $\instructiononehundredthirty$      | [TODO]         |
| 131                    | add_imm_32        | 0      | $\instructiononehundredthirtyone$   | [TODO]         |
| 132                    | and_imm           | 0      | $\instructiononehundredthirtytwo$   | [TODO]         |
| 133                    | xor_imm           | 0      | $\instructiononehundredthirtythree$ | [TODO]         |
| 134                    | or_imm            | 0      | $\instructiononehundredthirtyfour$  | [TODO]         |
| 135                    | mul_imm_32        | 0      | $\instructiononehundredthirtyfive$  | [TODO]         |
| 136                    | set_lt_u_imm      | 0      | $\instructiononehundredthirtysix$   | [TODO]         |
| 137                    | set_lt_s_imm      | 0      | $\instructiononehundredthirtyseven$ | [TODO]         |
| 138                    | shlo_l_imm-32     | 0      | $\instructiononehundredthirtyeight$ | [TODO]         |
| 139                    | shlo_r_imm-32     | 0      | $\instructiononehundredthirtynine$  | [TODO]         |
| 140                    | shar_r_imm_32     | 0      | $\instructiononehundredforty$       | [TODO]         |
| 141                    | neg_add_imm_32    | 0      | $\instructiononehundredfortyone$    | [TODO]         |
| 142                    | set_gt_u_imm      | 0      | $\instructiononehundredfortytwo$    | [TODO]         |
| 143                    | set_gt_s_imm      | 0      | $\instructiononehundredfortythree$  | [TODO]         |
| 144                    | shlo_l_imm_alt_32 | 0      | $\instructiononehundredfortyfour$   | [TODO]         |
| 145                    | shlo_r_imm_alt_32 | 0      | $\instructiononehundredfortyfive$   | [TODO]         |
| 146                    | shar_r_imm_alt_32 | 0      | $\instructiononehundredfortysix$    | [TODO]         |
| 147                    | cmov_iz_imm       | 0      | $\instructiononehundredfortyseven$  | [TODO]         |
| 148                    | cmov_nz_imm       | 0      | $\instructiononehundredfortyeight$  | [TODO]         |
| 149                    | add_imm_64        | 0      | $\instructiononehundredfortynine$   | [TODO]         |
| 150                    | mul_imm_64        | 0      | $\instructiononehundredfifty$       | [TODO]         |
| 151                    | shlo_l_imm_64     | 0      | $\instructiononehundredfiftyone$    | [TODO]         |
| 152                    | shlo_r_imm_64     | 0      | $\instructiononehundredfiftytwo$    | [TODO]         |
| 153                    | shar_r_imm_64     | 0      | $\instructiononehundredfiftythree$  | [TODO]         |
| 154                    | neg_add_imm_64    | 0      | $\instructiononehundredfiftyfour$   | [TODO]         |
| 155                    | shlo_l_imm_alt_64 | 0      | $\instructiononehundredfiftyfive$   | [TODO]         |
| 156                    | shlo_r_imm_alt_64 | 0      | $\instructiononehundredfiftysix$    | [TODO]         |
| 157                    | shar_r_imm_alt_64 | 0      | $\instructiononehundredfiftyseven$  | [TODO]         |
| 158                    | rot_r_64_imm      | 0      | $\instructiononehundredfiftyeight$  | [TODO]         |
| 159                    | rot_r_64_imm_alt  | 0      | $\instructiononehundredfiftynine$   | [TODO]         |
| 160                    | rot_r_32_imm      | 0      | $\instructiononehundredsixty$       | [TODO]         |
| 161                    | rot_r_32_imm_alt  | 0      | $\instructiononehundredsixtyone$    | [TODO]         |

### A.5.11. Instructions with Arguments of Two Registers & One Offset
| Graypaper                 | Equation                    | Implementation |
|---------------------------|-----------------------------|----------------|
| <a name="A.29">(A.29)</a> | $\equationapointtwentynine$ | [TODO]         |

| $\instructions_\imath$ | Name        | $\gas$ | Mutations                            | Implementation |
|------------------------|-------------|--------|--------------------------------------|----------------|
| 170                    | branch_eq   | 0      | $\instructiononehundredseventy$      | [TODO]         |
| 171                    | branch_ne   | 0      | $\instructiononehundredseventyone$   | [TODO]         |
| 172                    | branch_lt_u | 0      | $\instructiononehundredseventytwo$   | [TODO]         |
| 173                    | branch_lt_s | 0      | $\instructiononehundredseventythree$ | [TODO]         |
| 174                    | branch_ge_u | 0      | $\instructiononehundredseventyfour$  | [TODO]         |
| 175                    | branch_ge_s | 0      | $\instructiononehundredseventyfive$  | [TODO]         |

### A.5.12. Instructions with Arguments of Two Registers & Two Immediates
| Graypaper                 | Equation                | Implementation |
|---------------------------|-------------------------|----------------|
| <a name="A.30">(A.30)</a> | $\equationapointthirty$ | [TODO]         |

| $\instructions_\imath$ | Name              | $\gas$ | Mutations                      | Implementation |
|------------------------|-------------------|--------|--------------------------------|----------------|
| 180                    | load_imm_jump_ind | 0      | $\instructiononehundredeighty$ | [TODO]         |

### A.5.13. Instructions with Arguments of Three Registers
| Graypaper                 | Equation                   | Implementation |
|---------------------------|----------------------------|----------------|
| <a name="A.31">(A.31)</a> | $\equationapointthirtyone$ | [TODO]         |

| $\instructions_\imath$ | Name          | $\gas$ | Mutations                           | Implementation |
|------------------------|---------------|--------|-------------------------------------|----------------|
| 190                    | add_32        | 0      | $\instructiononehundredninety$      | [TODO]         |
| 191                    | sub_32        | 0      | $\instructiononehundredninetyone$   | [TODO]         |
| 192                    | mul_32        | 0      | $\instructiononehundredninetytwo$   | [TODO]         |
| 193                    | div_u_32      | 0      | $\instructiononehundredninetythree$ | [TODO]         |
| 194                    | div_s_32      | 0      | $\instructiononehundredninetyfour$  | [TODO]         |
| 195                    | rem_u_32      | 0      | $\instructiononehundredninetyfive$  | [TODO]         |
| 196                    | rem_s_32      | 0      | $\instructiononehundredninetysix$   | [TODO]         |
| 197                    | shlo_l_32     | 0      | $\instructiononehundredninetyseven$ | [TODO]         |
| 198                    | shlo_r_32     | 0      | $\instructiononehundredninetyeight$ | [TODO]         |
| 199                    | shar_r_32     | 0      | $\instructiononehundredninetynine$  | [TODO]         |
| 200                    | add_64        | 0      | $\instructiontwohundred$            | [TODO]         |
| 201                    | sub_64        | 0      | $\instructiontwohundredone$         | [TODO]         |
| 202                    | mul_64        | 0      | $\instructiontwohundredtwo$         | [TODO]         |
| 203                    | div_u_64      | 0      | $\instructiontwohundredthree$       | [TODO]         |
| 204                    | div_s_64      | 0      | $\instructiontwohundredfour$        | [TODO]         |
| 205                    | rem_u_64      | 0      | $\instructiontwohundredfive$        | [TODO]         |
| 206                    | rem_s_64      | 0      | $\instructiontwohundredsix$         | [TODO]         |
| 207                    | shlo_l_64     | 0      | $\instructiontwohundredseven$       | [TODO]         |
| 208                    | shlo_r_64     | 0      | $\instructiontwohundredeight$       | [TODO]         |
| 209                    | shar_r_64     | 0      | $\instructiontwohundrednine$        | [TODO]         |
| 210                    | and           | 0      | $\instructiontwohundredten$         | [TODO]         |
| 211                    | xor           | 0      | $\instructiontwohundredeleven$      | [TODO]         |
| 212                    | or            | 0      | $\instructiontwohundredtwelve$      | [TODO]         |
| 213                    | mul_upper_s_s | 0      | $\instructiontwohundredthirteen$    | [TODO]         |
| 214                    | mul_upper_u_u | 0      | $\instructiontwohundredfourteen$    | [TODO]         |
| 215                    | mul_upper_s_u | 0      | $\instructiontwohundredfifteen$     | [TODO]         |
| 216                    | set_lt_u      | 0      | $\instructiontwohundredsixteen$     | [TODO]         |
| 217                    | set_lt_s      | 0      | $\instructiontwohundredseventeen$   | [TODO]         |
| 218                    | cmov_iz       | 0      | $\instructiontwohundredeighteen$    | [TODO]         |
| 219                    | cmov_nz       | 0      | $\instructiontwohundrednineteen$    | [TODO]         |
| 220                    | rot_l_64      | 0      | $\instructiontwohundredtwenty$      | [TODO]         |
| 221                    | rot_l_32      | 0      | $\instructiontwohundredtwentyone$   | [TODO]         |
| 222                    | rot_r_64      | 0      | $\instructiontwohundredtwentytwo$   | [TODO]         |
| 223                    | rot_r_32      | 0      | $\instructiontwohundredtwentythree$ | [TODO]         |
| 224                    | and_inv       | 0      | $\instructiontwohundredtwentyfour$  | [TODO]         |
| 225                    | or_inv        | 0      | $\instructiontwohundredtwentyfive$  | [TODO]         |
| 226                    | xnor          | 0      | $\instructiontwohundredtwentysix$   | [TODO]         |
| 227                    | max           | 0      | $\instructiontwohundredtwentyseven$ | [TODO]         |
| 228                    | max_u         | 0      | $\instructiontwohundredtwentyeight$ | [TODO]         |
| 229                    | min           | 0      | $\instructiontwohundredtwentynine$  | [TODO]         |
| 230                    | min_u         | 0      | $\instructiontwohundredthirty$      | [TODO]         |

| Graypaper                 | Equation                     | Implementation |
|---------------------------|------------------------------|----------------|
| <a name="A.32">(A.32)</a> | $\equationapointthirtytwo$   | [TODO]         |
| <a name="A.33">(A.33)</a> | $\equationapointthirtythree$ | [TODO]         |


## A.6. Host Call Definition
| Graypaper                 | Equation                    | Implementation |
|---------------------------|-----------------------------|----------------|
| <a name="A.34">(A.34)</a> | $\equationapointthirtyfour$ | [TODO]         |
| <a name="A.35">(A.35)</a> | $\equationapointthirtyfive$ | [TODO]         |

## A.7. Standard Program Initialization
| Graypaper                 | Equation                     | Implementation |
|---------------------------|------------------------------|----------------|
| <a name="A.36">(A.36)</a> | $\equationapointthirtysix$   | [TODO]         |
| <a name="A.37">(A.37)</a> | $\equationapointthirtyseven$ | [TODO]         |
| <a name="A.38">(A.38)</a> | $\equationapointthirtyeight$ | [TODO]         |
| <a name="A.39">(A.39)</a> | $\equationapointthirtynine$  | [TODO]         |
| <a name="A.40">(A.40)</a> | $\equationapointforty$       | [TODO]         |
| <a name="A.41">(A.41)</a> | $\equationapointfortyone$    | [TODO]         |
| <a name="A.42">(A.42)</a> | $\equationapointfortytwo$    | [TODO]         |

## A.8. Argument Invocation Definition
| Graypaper                 | Equation                    | Implementation |
|---------------------------|-----------------------------|----------------|
| <a name="A.42">(A.42)</a> | $\equationapointfortytwo$   | [TODO]         |
| <a name="A.43">(A.43)</a> | $\equationapointfortythree$ | [TODO]         |
| <a name="A.44">(A.44)</a> | $\equationapointfortyfour$  | [TODO]         |
