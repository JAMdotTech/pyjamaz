# 3. Notational Conventions
\(
    \newcommand{\none}{\varnothing}
    \newcommand{\dict}[2]{\mathbb{D}\langle #1\to#2\rangle}
    \newcommand{\keys}[1]{\mathcal{K}(#1)}
\)

The aim of this section is to provide a detailed implementation reference on Graypaper equation definitions.
This section has been updated to match Graypaper version 0.5.4. 

## 3.2. Functions and Operators 
| Graypaper Reference | Stub | Implementation | Conformance | Documentation |
|---------------------|-----:|---------------:|------------:|--------------:|
| Equation 3.1        |   0% |             0% |          0% |            0% |
| Equation 3.2        |   0% |             0% |          0% |            0% |

### Equation 3.1
\(
    (3.1)  \quad 
    y \prec x \Longleftrightarrow \exists f: y = f(x)
\)
### Implementation
[TODO]
### Conformance
[TODO]
### Documentation
We define the precedes relation to indicate that one term is defined in terms of another. 
E.g. \(y \prec x\) indicates that \(y\) may be defined purely in terms of \(x\)
### References
https://graypaper.fluffylabs.dev/#/579bd12/061f00062b00

### Equation 3.2
\(
    (3.2)  \quad 
    \mathcal{U}(a_0, \dots a_n ) \equiv a_x : (a_x \ne \none \vee x = n), \bigwedge_{i=0}^{x-1} a_i = \none
\)
### Implementation
[TODO]
### Conformance
[TODO]
### Documentation
The substitute-if-nothing function \(\mathcal{U}\) is equivalent to the first argument which is not \(\none\), or \(\none\) if no such argument exists:
### References
[TODO]



## 3.5. Dictionaries 
| Graypaper Reference | Stub | Implementation | Conformance | Documentation |
|---------------------|-----:|---------------:|------------:|--------------:|
| Equation 3.3        |   0% |             0% |          0% |            0% |
| Equation 3.4        |   0% |             0% |          0% |            0% |
| Equation 3.5        |   0% |             0% |          0% |            0% |
| Equation 3.6        |   0% |             0% |          0% |            0% |
| Equation 3.7        |   0% |             0% |          0% |            0% |
| Equation 3.8        |   0% |             0% |          0% |            0% |
| Equation 3.9        |   0% |             0% |          0% |            0% |
| Equation 3.10       |   0% |             0% |          0% |            0% |
| Equation 3.11       |   0% |             0% |          0% |            0% |

### Equation 3.3
\(
    (3.3)  \quad 
    \mathbb{D} \subset \big \{ \{ (k \mapsto v) \} \big \}
\)
### Implementation
[TODO]
### Conformance
[TODO]
### Documentation
Thus, we define the formalism \(\dict{\mathrm{K}}{\mathrm{V}}\) to denote a dictionary which maps from the domain \(\mathrm{K}\) to the range \(\mathrm{V}\). We define a dictionary as a member of the set of all dictionaries \(\mathbb{D}\) and a set of pairs \(p = (k \mapsto v)\):
### References
[TODO]

### Equation 3.4
\(
    (3.4)  \quad 
    \forall \mathbf{d} \in \mathbb{D} : \forall (k \mapsto v) \in \mathbf{d} : \exists! v' : (k \mapsto v') \in \mathbf{d}
\)
### Implementation
[TODO]
### Conformance
[TODO]
### Documentation
A dictionary's members must associate at most one unique value for any key \(k\):
### References
[TODO]

### Equation 3.5
\(
    (3.5)  \quad 
    \forall \mathbf{d} \in \mathbb{D}: \mathbf{d}[k] \equiv 
    \begin{cases} 
        v & \text{if}\ \exists k : (k \mapsto v) \in \mathbf{d} \\
        \none & otherwise
    \end{cases}
\)
### Implementation
[TODO]
### Conformance
[TODO]
### Documentation
This assertion allows us to unambiguously define the subscript and subtraction operator for a dictionary \(d\):
### References
[TODO]

### Equation 3.6
\( 
    (3.6)  \quad 
    \forall \mathbf{d} \in \mathbb{D}, \mathbf{s} \subseteq K: \mathbf{d} \setminus \mathbf{s} \equiv \{ (k \mapsto v): (k \mapsto v) \in \mathbf{d}, k \not \in \mathbf{s} \}
\)
### Implementation
[TODO]
### Conformance
[TODO]
### Documentation
This assertion allows us to unambiguously define the subscript and subtraction operator for a dictionary \(d\):
### References
[TODO]

### Equation 3.7
\(
    (3.7)  \quad
    \dict{K}{V} \subset \mathbb{D}
\)
### Implementation
[TODO]
### Conformance
[TODO]
### Documentation
It is typically useful to limit the sets from which the keys and values may be drawn. Formally, we define a typed dictionary \(\dict{K}{V}\) as a set of pairs \(p\) of the form \((k \mapsto v)\):
### References
[TODO]

### Equation 3.8
\(
    (3.8)  \quad 
    \dict{K}{V} \equiv \big \{ \{ (k \mapsto v) \mid k \in K \wedge v \in V \} \big \} \\
\)
### Implementation
[TODO]
### Conformance
[TODO]
### Documentation
It is typically useful to limit the sets from which the keys and values may be drawn. Formally, we define a typed dictionary \(\dict{K}{V}\) as a set of pairs \(p\) of the form \((k \mapsto v)\):
### References
[TODO]

### Equation 3.9
\(
    (3.9)  \quad 
    \keys{\mathbf{d} \in \mathbb{D}} \equiv \{ k \mid \exists v : (k \mapsto v) \in \mathbf{d} \}
\)
### Implementation
[TODO]
### Conformance
[TODO]
### Documentation
To denote the active domain (\ie set of keys) of a dictionary \(\mathbf{d} \in \dict{K}{V}\), we use \(\keys{\mathbf{d}} \subseteq K\) and for the range (\ie set of values), \(\mathcal{V}(\mathbf{d}) \subseteq V\). Formally:
### References
[TODO]

### Equation 3.10
\(
    (3.10)  \quad 
    \mathcal{V} (\mathbf{d} \in \mathbb{D}) \equiv \{ v \mid \exists k : (k \mapsto v) \in \mathbf{d} \}
\)
### Implementation
[TODO]
### Conformance
[TODO]
### Documentation
To denote the active domain (\ie set of keys) of a dictionary \(\mathbf{d} \in \mathbb{D} \langle {K} \to {V} \rangle\), we use \(\keys{\mathbf{d}} \subseteq K\) and for the range (\ie set of values), \(\mathcal{V}(\mathbf{d}) \subseteq V\). Formally:
### References
[TODO]

### Equation 3.11
\(
    (3.11)  \quad 
    \forall \mathbf{d} \in \mathbb{D}, \mathbf{e} \in \mathbb{D}: \mathbf{d} \cup \mathbf{e} \equiv (\mathbf{d} \setminus \keys{\mathbf{e}}) \cup \mathbf{e}    
\)
### Implementation
[TODO]
### Conformance
[TODO]
### Documentation
Dictionaries may be combined through the union operator \(\cup\), which priorities the right-side operand in the case of a key-collision:
### References
[TODO]
