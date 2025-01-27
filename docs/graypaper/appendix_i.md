# Appendix I. Index of Notation
The aim of this section is to provide a detailed implementation reference on Graypaper equation definitions.
This section has been updated to match Graypaper version 0.5.4.
\(
    \newcommand{\token}[1]{\text{{\small \texttt{#1}}}}
    \newcommand{\beefycommitmap}{\mathbf{C}}    
    \newcommand\nb{\textsc{nb}\@\xspace}
    \renewcommand{\H}{\mathbb{H}}
    \newcommand{\N}{\mathbb{N}}
    \newcommand{\Y}{\mathbb{Y}}
    \newcommand{\Z}{\mathbb{Z}}
    \newcommand{\sig}[2]{\mathbb{E}_{#1}\langle#2\rangle}
    \newcommand{\bandersnatch}[3]{\bar{\mathbb{F}}_{#1}^{#3}\langle#2\rangle}
    \newcommand{\bandersig}[3]{\mathbb{F}_{#1}^{#3}\langle#2\rangle}
    \newcommand{\dict}[2]{\mathbb{D}\langle #1\to#2\rangle}
    \newcommand{\gascounter}{\varrho}
    \newcommand{\registers}{\omega}
    \newcommand{\memory}{\mu}
    \newcommand{\se}{\mathcal{E}}
    \newcommand{\powset}[2][{}]{\wp\left\langle#2\right\rangle_{#1}}
    \newcommand{\goodset}{\psi_\mathbf{g}}
    \newcommand{\badset}{\psi_\mathbf{b}}
    \newcommand{\wonkyset}{\psi_\mathbf{w}}
    \newcommand{\offenders}{\psi_\mathbf{o}}
\)
## I.1 Sets
### I.1.1 Regular Notation
| Graypaper    | Description                                                                       | References     |
|--------------|-----------------------------------------------------------------------------------|----------------|
| $\N$         | The set of non-negative integers. Subscript denotes one greater than the maximum. | Section: 3.4   |
| $\quad \N^+$ | The set of positive integers (not including zero).                                | N/A            |
| $\quad \N_B$ | The set of balance values. Equivalent to $\N_{2^{64}}$.                           | Equation: 4.21 |
| $\quad \N_G$ | The set of unsigned gas values. Equivalent to $\mathbb{N}_{2^{64}}$.              | Equation: 4.23 |
| $\quad \N_L$ | The set of blob length values. Equivalent to $\N_{2^{32}}$.                       | Section: 3.4   |
| $\quad \N_S$ | The set from which service indices are drawn. Equivalent to $\N_{2^{32}}$.        | Section: 9.1   |
| $\quad \N_T$ | The set of timeslot values. Equivalent to $\N_{2^{32}}$.                          | Equation: 4.28 |
| $\mathbb{Q}$ | The set of rational numbers. Unused.                                              | Unused         |
| $\mathbb{R}$ | The set of real numbers. Unused.                                                  | Unused         |
| $\mathbb{Z}$ | The set of integers. Subscript denotes range.                                     | Section: 3.4   |
| $\quad \Z_G$ | The set of signed gas values. Equivalent to $\mathbb{Z}_{-2^{63}\dots2^{63}}$.    | Equation: 4.23 |

### I.1.2 Custom Notation
| Graypaper                      | Description                                                                                                                         | References                                                                    |
|--------------------------------|-------------------------------------------------------------------------------------------------------------------------------------|-------------------------------------------------------------------------------|
| $\mathbb{A}$                   | The set of service accounts.                                                                                                        | See equation $\ref{eq:serviceaccount}$.                                       |
| $\mathbb{B}$                   | The set of Boolean sequences/bitstrings. Subscript denotes length.                                                                  | See section $\ref{sec:sequences}$.                                            |
| $\mathbb{C}$                   | The set of seal-key tickets.                                                                                                        | See equation $\ref{eq:ticket}$. Note: Not used as the set of complex numbers. |
| $\mathbb{D}$                   | The set of dictionaries.                                                                                                            | See section $\ref{sec:dictionaries}$.                                         |
| $\quad \dict{K}{V}$            | The set of dictionaries making a partial bijection of domain $K$ to range $V$.                                                      | See section $\ref{sec:dictionaries}$.                                         |
| $\mathbb{E}$                   | The set of valid Ed25519 signatures. A subset of $\Y_{64}$.                                                                         | See section $\ref{sec:cryptography}$.                                         |
| $\sig{K}{M}$                   | The set of valid Ed25519 signatures of the key $K$ and message $M$. A subset of $\mathbb{E}$.                                       | See section $\ref{sec:cryptography}$.                                         |
| $\mathbb{F}$                   | The set of Bandersnatch signatures. A subset of $\Y_{64}$.                                                                          | See section $\ref{sec:cryptography}$. Note: Not used as finite fields.        |
| $\quad \bandersig{K}{C}{M}$    | The set of Bandersnatch signatures of the public key $K$, context $C$ and message $M$. A subset of $\mathbb{F}$.                    | See section $\ref{sec:cryptography}$.                                         |
| $\quad \bar{\mathbb{F}}$       | The set of Bandersnatch RingVRF proofs.                                                                                             | See section $\ref{sec:cryptography}$.                                         |
| $\quad \bandersnatch{R}{C}{M}$ | The set of Bandersnatch RingVRF proofs of the root $R$, context $C$ and message $M$. A subset of $\bar{\mathbb{F}}$.                | See section $\ref{sec:cryptography}$.                                         |
| $\mathbb{G}$                   | The set of data segments, equivalent to octet sequences of length $\mathsf{W}_G$.                                                   | See equation $\ref{eq:segment}$.                                              |
| $\H$                           | The set of 32-octet cryptographic values. A subset of $\Y_{32}$. $\H$ without a subscript generally implies a hash function result. | See section $\ref{sec:cryptography}$. Note: Not used as quaternions.          |
| $\quad \H_B$                   | The set of Bandersnatch public keys. A subset of $\Y_{32}$.                                                                         | See section $\ref{sec:cryptography}$ and appendix $\ref{sec:bandersnatch}$.   |
| $\quad \H_E$                   | The set of Ed25519 public keys. A subset of $\Y_{32}$.                                                                              | See section $\ref{sec:signing}$.                                              |
| $\mathbb{I}$                   | The set of work items.                                                                                                              | See equation $\ref{eq:workitem}$.                                             |
| $\mathbb{J}$                   | The set of work execution errors.                                                                                                   |                                                                               |
| $\mathbb{K}$                   | The set of validator key-sets.                                                                                                      | See equation $\ref{eq:validatorkeys}$.                                        |
| $\mathbb{L}$                   | The set of work results.                                                                                                            |                                                                               |
| $\mathbb{M}$                   | The set of PVM RAM states. A superset of $\Y_{2^{32}}$.                                                                             | See appendix $\ref{sec:virtualmachine}$.                                      |
| $\mathbb{O}$                   | The accumulation operand element, corresponding to a single work result.                                                            |                                                                               |
| $\mathbb{P}$                   | The set of work-packages.                                                                                                           | See equation $\ref{eq:workpackage}$.                                          |
| $\mathbb{S}$                   | The set of availability specifications.                                                                                             |                                                                               |
| $\mathbb{T}$                   | The set of deferred transfers.                                                                                                      |                                                                               |
| $\mathbb{U}$                   | The set of partial state, used during accumulation.                                                                                 | See equation $\ref{eq:partialstate}$.                                         |
| $\mathbb{V}_{\memory}$         | The set of validly readable indices for PVM RAM $\memory$.                                                                          | See appendix $\ref{sec:virtualmachine}$.                                      |
| $\mathbb{V}^*_{\memory}$       | The set of validly writable indices for PVM RAM $\memory$.                                                                          | See appendix $\ref{sec:virtualmachine}$.                                      |
| $\mathbb{W}$                   | The set of work-reports.                                                                                                            |                                                                               |
| $\mathbb{X}$                   | The set of refinement contexts.                                                                                                     |                                                                               | 
| $\Y$                           | The set of octet strings/"blobs". Subscript denotes length.                                                                         | See section $\ref{sec:sequences}$.                                            |
| $\quad \Y_{BLS}$               | The set of BLS public keys. A subset of $\Y_{144}$.                                                                                 | See section $\ref{sec:signing}$.                                              |
| $\quad \Y_R$                   | The set of Bandersnatch ring roots. A subset of $\Y_{144}$.                                                                         | See section $\ref{sec:cryptography}$ and appendix $\ref{sec:bandersnatch}$.   |

## I.2 Functions
| Graypaper              | Description                                                                        | References                                                                          |
|------------------------|------------------------------------------------------------------------------------|-------------------------------------------------------------------------------------|
| $\Delta$               | The accumulation function; certain subscripts are used to denote helper functions. |                                                                                     |
| $\quad \Delta_1$       | The single-step accumulation function.                                             |                                                                                     |
| $\quad \Delta_*$       | The parallel accumulation function.                                                |                                                                                     |
| $\quad \Delta_+$       | The full sequential accumulation function.                                         |                                                                                     | 
| $\Lambda$              | The historical lookup function.                                                    | See equation $\ref{eq:historicallookup}$.                                           | 
| $\Xi$                  | The work result computation function.                                              | See equation $\ref{eq:workresultfunction}$.                                         | 
| $\Upsilon$             | The general state transition function.                                             | See equations $\ref{eq:statetransition}$, $\ref{eq:transitionfunctioncomposition}$. |
| $\Phi$                 | The key-nullifier function.                                                        | See equation $\ref{eq:blacklistfilter}$.                                            |  
| $\Psi$                 | The whole-program PVM machine state-transition function.                           | See equation $\ref{sec:virtualmachine}$.                                            |                                          
| $\quad \Psi_1$         | The single-step (PVM) machine state-transition function.                           | See appendix $\ref{sec:virtualmachine}$.                                            |                                          
| $\quad \Psi_A$         | The Accumulate PVM invocation function.                                            | See appendix $\ref{sec:virtualmachineinvocations}$.                                 |
| $\quad \Psi_H$         | The host-function invocation (PVM) with host-function marshalling.                 | See appendix $\ref{sec:virtualmachine}$.                                            |                            
| $\quad \Psi_I$         | The Is-Authorized PVM invocation function.                                         | See appendix $\ref{sec:virtualmachineinvocations}$.                                 |                                   
| $\quad \Psi_M$         | The marshalling whole-program PVM machine state-transition function.               | See appendix $\ref{sec:virtualmachine}$.                                            |                                    
| $\quad \Psi_R$         | The Refine PVM invocation function.                                                | See appendix $\ref{sec:virtualmachineinvocations}$.                                 |                                   
| $\quad \Psi_T$         | The On-Transfer PVM invocation function.                                           | See appendix $\ref{sec:virtualmachineinvocations}$.                                 |                                 
| $\Omega$               | Virtual machine host-call functions.                                               | See appendix $\ref{sec:virtualmachineinvocations}$.                                 |                           
| $\quad \Omega_A$       | Assign-core host-call.                                                             |                                                                                     |
| $\quad \Omega_B$       | Empower-service host-call.                                                         |                                                                                     |
| $\quad \Omega_C$       | Checkpoint host-call.                                                              |                                                                                     |
| $\quad \Omega_D$       | Designate-validators host-call.                                                    |                                                                                     |
| $\quad \Omega_E$       | Export segment host-call.                                                          |                                                                                     |
| $\quad \Omega_F$       | Forget-preimage host-call.                                                         |                                                                                     |
| $\quad \Omega_G$       | Gas-remaining host-call.                                                           |                                                                                     |
| $\quad \Omega_H$       | Historical-lookup-preimage host-call.                                              |                                                                                     |
| $\quad \Omega_I$       | Information-on-service host-call.                                                  |                                                                                     |
| $\quad \Omega_J$       | Eject-service host-call.                                                           |                                                                                     |
| $\quad \Omega_K$       | Kickoff-PVM host-call.                                                             |                                                                                     |
| $\quad \Omega_L$       | Lookup-preimage host-call.                                                         |                                                                                     |
| $\quad \Omega_M$       | Make-PVM host-call.                                                                |                                                                                     |
| $\quad \Omega_N$       | New-service host-call.                                                             |                                                                                     |
| $\quad \Omega_O$       | Poke-PVM host-call.                                                                |                                                                                     |
| $\quad \Omega_P$       | Peek-PVM host-call.                                                                |                                                                                     |
| $\quad \Omega_Q$       | Query-preimage host-call.                                                          |                                                                                     |
| $\quad \Omega_R$       | Read-storage host-call.                                                            |                                                                                     |
| $\quad \Omega_S$       | Solicit-preimage host-call.                                                        |                                                                                     |
| $\quad \Omega_T$       | Transfer host-call.                                                                |                                                                                     |
| $\quad \Omega_U$       | Upgrade-service host-call.                                                         |                                                                                     |
| $\quad \Omega_V$       | Void inner-PVM memory host-call.                                                   |                                                                                     |
| $\quad \Omega_W$       | Write-storage host-call.                                                           |                                                                                     |
| $\quad \Omega_X$       | Expunge-PVM host-call.                                                             |                                                                                     |
| $\quad \Omega_Y$       | Import segment host-call.                                                          |                                                                                     |
| $\quad \Omega_Z$       | Zero inner-PVM memory host-call.                                                   |                                                                                     |
| $\quad \Omega_\Taurus$ | Yield accumulation trie result host-call.                                          |                                                                                     | 

## I.3 Utilities, Externalities and Standard Functions
| Graypaper                   | Description                                                                                                | References                                                                  |
|-----------------------------|------------------------------------------------------------------------------------------------------------|-----------------------------------------------------------------------------|
| $\mathcal{A}(\dots)$)       | The Merkle mountain range append function.                                                                 | See equation $\ref{eq:mmrappend}$.                                          |
| $\mathcal{B}_n(\dots)$      | The octets-to-bits function for $n$ octets. Superscripted ${}^{-1}$ to denote the inverse.                 | See equation $\ref{eq:bitsfunc}$.                                           |
| $\mathcal{C}(\dots)$        | The group of erasure-coding functions.                                                                     |                                                                             |
| $\mathcal{C}_n(\dots)$      | The erasure-coding functions for $n$ chunks.                                                               | See equation $\ref{eq:erasurecoding}$.                                      |
| $\se(\dots)$                | The octet-sequence encode function. Superscripted ${}^{-1}$ to denote the inverse.                         | See appendix $\ref{sec:serialization}$.                                     |
| $\mathcal{F}(\dots)$        | The Fisher-Yates shuffle function.                                                                         | See equation $\ref{eq:suffle}$.                                             |
| $\mathcal{H}(\dots)$        | The Blake 2b 256-bit hash function.                                                                        | See section $\ref{sec:cryptography}$.                                       |
| $\mathcal{H}_K(\dots))$     | The Keccak 256-bit hash function.                                                                          | See section $\ref{sec:cryptography}$.                                       |
| $\mathcal{J}_x$             | The justification path to a specific $2^x$ size page of a constant-depth Merkle tree.                      | See equation $\ref{eq:constantdepthsubtreemerklejust}$.                     |
| $\mathcal{K}(\dots)$        | The domain, or set of keys, of a dictionary.                                                               | See section $\ref{sec:dictionaries}$.                                       |
| $\mathcal{L}_x$             | The $2^x$ size page function for a constant-depth Merkle tree.                                             | See equation $\ref{eq:constantdepthsubtreemerkleleafpage}$.                 |
| $\mathcal{M}(\dots)$        | The constant-depth binary Merklization function.                                                           | See appendix $\ref{sec:merklization}$.                                      |
| $\mathcal{M}_B(\dots)$      | The well-balanced binary Merklization function.                                                            | See appendix $\ref{sec:merklization}$.                                      |
| $\mathcal{M}_\sigma(\dots)$ | The state Merklization function.                                                                           | See appendix $\ref{sec:statemerklization}$.                                 |
| $\mathcal{N}(\dots)$        | The erasure-coding chunks function.                                                                        | See appendix $\ref{sec:erasurecoding}$.                                     |
| $\mathcal{O}(\dots)$        | The Bandersnatch ring root function.                                                                       | See section $\ref{sec:cryptography}$ and appendix $\ref{sec:bandersnatch}$. |
| $\mathcal{P}_n(\dots)$      | The octet-array zero-padding function.                                                                     | See equation $\ref{eq:zeropadding}$.                                        |
| $\mathcal{Q}(\dots)$        | The numeric-sequence-from-hash function.                                                                   | See equation $\ref{eq:sequencefromhash}$.                                   |
| $\mathcal{R}$               | The group of erasure-coding piece-recovery functions.                                                      |                                                                             | 
| $\mathcal{S}_k(\dots)$      | The general signature function.                                                                            | See section $\ref{sec:cryptography}$.                                       |
| $\mathcal{T}$               | The current time expressed in seconds after the start of the JAM Common Era.                               | See section $\ref{sec:commonera}$.                                          |
| $\mathcal{U}(\dots)$        | The substitute-if-nothing function.                                                                        | See equation $\ref{eq:substituteifnothing}$.                                |
| $\mathcal{V}(\dots)$        | The range, or set of values, of a dictionary or sequence.                                                  | See section $\ref{sec:dictionaries}$.                                       |
| $\mathcal{X}_n(\dots)$      | The signed-extension function for a value in $\N_{2^{8n}}$.                                                | See equation $\ref{eq:signedextension}$.                                    |
| $\mathcal{Y}(\dots)$        | The alias/output/entropy function of a Bandersnatch VRF signature/proof.                                   | See section $\ref{sec:cryptography}$ and appendix $\ref{sec:bandersnatch}$. |
| $\mathcal{Z}_n(\dots)$      | The into-signed function for a value in $\N_{2^{8n}}$. Superscripted with ${}^{-1}$ to denote the inverse. | See equation $\ref{eq:signedfunc}$.                                         |
| $\powset{\dots}$            | Power set function.                                                                                        | 

## I.4 Values
### I.4.1 Block-context Terms
These terms are all contextualized to a single block. They may be superscripted with some other term to alter the context and reference some other block.

| Graypaper             | Description                                                                                                                                                                             | References                                                                        |
|-----------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|-----------------------------------------------------------------------------------|
| $\mathbf{A}$          | The ancestor set of the block.                                                                                                                                                          | See equation $\ref{eq:ancestors}$.                                                |
| $\mathbf{B}$          | The block. Without any superscript, the block is assumed to the block being imported or, if no block is being imported, the head of the best chain (see section $\ref{sec:bestchain}$). | See equation $\ref{eq:block}$.                                                    |
| $\mathbf{B}^\natural$ | The latest finalized block. Explicit block-contextualizing superscript.                                                                                                                 | See equation $\ref{sec:bestchain}$.                                               |
| $\mathbf{B}^\flat$    | The block at the head of the best chain. Explicit block-contextualizing superscript.                                                                                                    | See equation $\ref{sec:bestchain}$.                                               |
| $\beefycommitmap$     | The service accumulation-commitment, used to form the \textsc{Beefy} root.                                                                                                              | See equation $\ref{eq:beefycommitment}$.                                          |
| $\mathbf{E}$          | The block extrinsic.                                                                                                                                                                    | See equation $\ref{eq:extrinsic}$.                                                |
| $\mathbf{F}_v$        | The \textsc{Beefy} signed commitment of validator $v$.                                                                                                                                  | See equation $\ref{eq:beefysignedcommitment}$.                                    |
| $\mathbf{G}$          | The mapping from cores to guarantor keys.                                                                                                                                               | See section $\ref{sec:coresandvalidators}$.                                       |
| $\mathbf{G^*}$        | The mapping from cores to guarantor keys for the previous rotation.                                                                                                                     | See section $\ref{sec:coresandvalidators}$.                                       |
| $\mathbf{H}$          | The block header.                                                                                                                                                                       | See equation $\ref{eq:header}$.                                                   |
| $\mathbf{Q}$          | The selection of ready work-reports which a validator determined they must audit.                                                                                                       | See equation $\ref{eq:auditselection}$.                                           |
| $\mathbf{R}$          | The set of Ed25519 guarantor keys who made a work-report.                                                                                                                               | See equation $\ref{eq:guarantorsig}$.                                             |
| $\mathbf{S}$          | The set of indices of services which have been accumulated (``progressed'') in the block.                                                                                               | See equation $\ref{eq:servicestoaccumulate}$.                                     |
| $\mathbf{T}$          | The ticketed condition, true if the block was sealed with a ticket signature rather than a fallback.                                                                                    | See equations $\ref{eq:ticketconditiontrue}$ and $\ref{eq:ticketconditionfalse}$. |
| $\mathbf{U}$          | The audit condition, equal to $\top$ once the block is audited.                                                                                                                         | See section $\ref{sec:auditing}$.                                                 |
| $\mathbf{V}$          | The set of verdicts in the present block.                                                                                                                                               | See equation $\ref{eq:verdicts}$.                                                 |
| $\mathbf{W}$          | The sequence of work-reports which have now become available and ready for accumulation.                                                                                                | See equation $\ref{eq:availableworkreports}$.                                     |

### I.4.2 State components
Here, the prime annotation indicates posterior state. Individual components may be identified with a letter subscript.

| Graypaper                 | Description                                                                                          | References                                                             |
|---------------------------|------------------------------------------------------------------------------------------------------|------------------------------------------------------------------------|
| $\alpha$                  | The core $\alpha$uthorizations pool.                                                                 | See equation $\ref{eq:authstatecomposition}$.                          |
| $\beta$                   | Information on the most recent $\beta$locks.                                                         |                                                                        |
| $\gamma$                  | State concerning Safrole.                                                                            | See equation $\ref{eq:consensusstatecomposition}$.                     |
| $\quad \gamma_\mathbf{a}$ | The sealing lottery ticket accumulator.                                                              |                                                                        |
| $\quad \gamma_\mathbf{k}$ | The keys for the validators of the next epoch, equivalent to those keys which constitute $\gamma_z$. |                                                                        | 
| $\quad \gamma_\mathbf{s}$ | The sealing-key sequence of the current epoch.                                                       |                                                                        |
| $\quad \gamma_z$          | The Bandersnatch root for the current epoch's ticket submissions.                                    |                                                                        | 
| $\delta$                  | The (prior) state of the service accounts.                                                           |                                                                        |
| $\quad \delta^\dagger$    | The post-preimage integration, pre-accumulation intermediate state.                                  |                                                                        | 
| $\quad \delta^\ddagger$   | The post-accumulation, pre-transfer intermediate state.                                              |                                                                        | 
| $\eta$                    | The e$\eta$tropy accumulator and epochal ra$\eta$domness.                                            |                                                                        |
| $\iota$                   | The validator keys and metadata to be drawn from next.                                               |                                                                        |
| $\kappa$                  | The validator $\kappa$eys and metadata currently active.                                             |                                                                        |
| $\lambda$                 | The validator keys and metadata which were active in the prior epoch.                                |                                                                        |
| $\rho$                    | The $\rho$ending reports, per core, which are being made available prior to accumulation.            |                                                                        | 
| $\quad \rho^\dagger$      | The post-judgment, pre-guarantees-extrinsic intermediate state.                                      |                                                                        |
| $\quad \rho^\ddagger$     | The post-guarantees-extrinsic, pre-assurances-extrinsic, intermediate state.                         |                                                                        | 
| $\sigma$                  | The $\sigma$verall state of the system.                                                              | See equations $\ref{eq:statetransition}$, $\ref{eq:statecomposition}$. |
| $\tau$                    | The most recent block's $\tau$imeslot.                                                               |                                                                        | 
| $\varphi$                 | The authorization queue.                                                                             |                                                                        |
| $\psi$                    | Past judgments on work-reports and validators.                                                       |                                                                        |
| $\quad \badset$           | Work-reports judged to be incorrect.                                                                 |                                                                        |
| $\quad \goodset$          | Work-reports judged to be correct.                                                                   |                                                                        |
| $\quad \wonkyset$         | Work-reports whose validity is judged to be unknowable.                                              |                                                                        |
| $\quad \offenders$        | Validators who made a judgment found to be incorrect.                                                |                                                                        | 
| $\chi$                    | The privileged service indices.                                                                      |                                                                        |
| $\quad \chi_m$            | The index of the blessed service.                                                                    |                                                                        |
| $\quad \chi_v$            | The index of the designate service.                                                                  |                                                                        |
| $\quad \chi_a$            | The index of the assign service.                                                                     |                                                                        |
| $\quad \chi_\mathbf{g}$   | The always-accumulate service indices and their basic gas allowance.                                 |                                                                        | 
| $\pi$                     | The activity statistics for the validators.                                                          |                                                                        | 
| $\vartheta$               | The accumulation queue.                                                                              |                                                                        | 
| $\xi$                     | The accumulation history.                                                                            |                                                                        | 

### I.4.3 Virtual Machine components
| Graypaper     | Description                                                   | References |
|---------------|---------------------------------------------------------------|------------|
| $\varepsilon$ | The exit-reason resulting from all machine state transitions. |            |
| $\nu$         | The immediate values of an instruction.                       |            |
| $\memory$     | The memory sequence; a member of the set $\mathbb{M}$.        |            |
| $\gascounter$ | The gas counter.                                              |            |
| $\registers$  | The registers.                                                |            |
| $\zeta$       | The instruction sequence.                                     |            |
| $\varpi$      | The sequence of basic blocks of the program.                  |            |
| $\imath$      | The instruction counter.                                      |            |

### I.4.4 Constants
| Graypaper                                        | Description                                                                                                                                                  | References                                    |
|--------------------------------------------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------|-----------------------------------------------|
| $\mathsf{A} = 8$                                 | The period, in seconds, between audit tranches.                                                                                                              |                                               |
| $\mathsf{B}_I = 10$                              | The additional minimum balance required per item of elective service state.                                                                                  |                                               |
| $\mathsf{B}_L = 1$                               | The additional minimum balance required per octet of elective service state.                                                                                 |                                               |
| $\mathsf{B}_S = 100$                             | The basic minimum balance which all services require.                                                                                                        |                                               |
| $\mathsf{C} = 341$                               | The total number of cores.                                                                                                                                   |                                               |
| $\mathsf{D} = 28,800$                            | The period in timeslots after which an unreferenced preimage may be expunged.                                                                                |                                               |
| $\mathsf{E} = 600$                               | The length of an epoch in timeslots.                                                                                                                         |                                               |
| $\mathsf{F} = 2$                                 | The audit bias factor, the expected number of additional validators who will audit a work-report in the following tranche for each no-show in the previous.  |                                               |
| $\mathsf{G}_A = 10,000,000$                      | The gas allocated to invoke a work-report's Accumulation logic.                                                                                              |                                               |
| $\mathsf{G}_I = 50,000,000$                      | The gas allocated to invoke a work-package's Is-Authorized logic.                                                                                            |                                               |
| $\mathsf{G}_R = 5,000,000,000$                   | The gas allocated to invoke a work-package's Refine logic.                                                                                                   |                                               |
| $\mathsf{G}_T = 3,500,000,000$                   | The total gas allocated across for all Accumulation. Should be no smaller than $\mathsf{G}_A\cdot\mathsf{C} + \sum_{g \in \mathcal{V}(\chi_\mathbf{g})}(g)$. |                                               |
| $\mathsf{H} = 8$                                 | The size of recent history, in blocks.                                                                                                                       |                                               |
| $\mathsf{I} = 4$                                 | The maximum amount of work items in a package.                                                                                                               |                                               |
| $\mathsf{J} = 8$                                 | The maximum sum of dependency items in a work-report.                                                                                                        |                                               |
| $\mathsf{K} = 16$                                | The maximum number of tickets which may be submitted in a single extrinsic.                                                                                  |                                               |
| $\mathsf{L} = 14,400$                            | The maximum age in timeslots of the lookup anchor.                                                                                                           |                                               |
| $\mathsf{N} = 2$                                 | The number of ticket entries per validator.                                                                                                                  |                                               |
| $\mathsf{O} = 8$                                 | The maximum number of items in the authorizations pool.                                                                                                      |                                               |
| $\mathsf{P} = 6$                                 | The slot period, in seconds.                                                                                                                                 |                                               |
| $\mathsf{Q} = 80$                                | The number of items in the authorizations queue.                                                                                                             |                                               |
| $\mathsf{R} = 10$                                | The rotation period of validator-core assignments, in timeslots.                                                                                             |                                               |
| $\mathsf{S} = 1024$                              | The maximum number of entries in the accumulation queue.                                                                                                     |                                               |
| $\mathsf{U} = 5$                                 | The period in timeslots after which reported but unavailable work may be replaced.                                                                           |                                               |
| $\mathsf{V} = 1023$                              | The total number of validators.                                                                                                                              |                                               |
| $\mathsf{W}_B = 12\cdot2^{20}$                   | The maximum size of an encoded work-package together with its extrinsic data and import implications, in octets.                                             |                                               |
| $\mathsf{W}_C = 4,000,000$                       | The maximum size of service code in octets.                                                                                                                  |                                               |
| $\mathsf{W}_E = 684$                             | The basic size of erasure-coded pieces in octets.                                                                                                            | See equation $\ref{eq:erasurecoding}$.        |
| $\mathsf{W}_G = \mathsf{W}_P\mathsf{W}_E = 4104$ | The size of a segment in octets.                                                                                                                             |                                               |
| $\mathsf{W}_M = 2^{11}$                          | The maximum number of entries in a work-package manifest.                                                                                                    |                                               |
| $\mathsf{W}_P = 6$                               | The number of erasure-coded pieces in a segment.                                                                                                             |                                               |
| $\mathsf{W}_R = 48\cdot2^{10}$                   | The maximum total size of all output blobs in a work-report, in octets.                                                                                      |                                               |
| $\mathsf{W}_T = 128$                             | The size of a transfer memo in octets.                                                                                                                       |                                               |
| $\mathsf{X}$                                     | Context strings, see below.                                                                                                                                  |                                               |
| $\mathsf{Y} = 500$                               | The number of slots into an epoch at which ticket-submission ends.                                                                                           |                                               |
| $\mathsf{Z}_A = 2$                               | The PVM dynamic address alignment factor.                                                                                                                    | See equation $\ref{eq:jumptablealignment}$.   |
| $\mathsf{Z}_I = 2^{24}$                          | The standard PVM program initialization input data size.                                                                                                     | See equation $\ref{sec:standardprograminit}$. |
| $\mathsf{Z}_P = 2^{12}$                          | The PVM memory page size.                                                                                                                                    | See equation $\ref{eq:pvmmemory}$.            |

### I.4.5 Signing Contexts
| Graypaper                              | Description                                                               | References |
|----------------------------------------|---------------------------------------------------------------------------|------------|
| $\mathsf{X}_A = \$jam\_available$      | $\textit{Ed25519}$ Availability assurances.                               |            |
| $\mathsf{X}_B = \$jam\_beefy$          | $\textit{BLS}$ Accumulate-result-root-\textsc{mmr} commitment.            |            |
| $\mathsf{X}_E = \$jam\_entropy$        | On-chain entropy generation.                                              |            |
| $\mathsf{X}_F = \$jam\_fallback\_seal$ | $\textit{Bandersnatch}$ Fallback block seal.                              |            |
| $\mathsf{X}_G = \$jam\_guarantee$      | $\textit{Ed25519}$ Guarantee statements.                                  |            |
| $\mathsf{X}_I = \$jam\_announce$       | $\textit{Ed25519}$ Audit announcement statements.                         |            |
| $\mathsf{X}_T = \$jam\_ticket\_seal$   | $\textit{Bandersnatch RingVRF}$ Ticket generation and regular block seal. |            |
| $\mathsf{X}_U = \$jam\_audit$          | $\textit{Bandersnatch}$ Audit selection entropy.                          |            |
| $\mathsf{X}_\top = \$jam\_valid$       | $\textit{Ed25519}$ Judgments for valid work-reports.                      |            |
| $\mathsf{X}_\bot = \$jam\_invalid$     | $\textit{Ed25519}$ Judgments for invalid work-reports.                    |            |
