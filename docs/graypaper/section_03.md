# 3. Notational Conventions
\(
    \newcommand{\none}{\varnothing}
    \newcommand{\dict}[2]{\mathbb{D}\langle #1\to#2\rangle}
    \newcommand{\keys}[1]{\mathcal{K}(#1)}
\)

The aim of this section is to provide a detailed implementation reference on Graypaper equation definitions.
This section has been updated to match Graypaper version 0.5.4. 

## 3.2. Functions and Operators 
| Graypaper               | Equation                                                                                                  | Implementation |
|-------------------------|-----------------------------------------------------------------------------------------------------------|----------------|
| <a name="3.1">(3.1)</a> | $y \prec x \Longleftrightarrow \exists f: y = f(x)$                                                       | [TODO]         | 
| <a name="3.2">(3.2)</a> | $\mathcal{U}(a_0, \dots a_n ) \equiv a_x : (a_x \ne \none \vee x = n), \bigwedge_{i=0}^{x-1} a_i = \none$ | [TODO]         |

## 3.5. Dictionaries 
| Graypaper                 | Equation                                                                                                                                                                     | Implementation |
|---------------------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|----------------|
| <a name="3.3">(3.3)</a>   | $\mathbb{D} \subset \big \{ \{ (k \mapsto v) \} \big \}$                                                                                                                     | [TODO]         |
| <a name="3.4">(3.4)</a>   | $\forall \mathbf{d} \in \mathbb{D} : \forall (k \mapsto v) \in \mathbf{d} : \exists! v' : (k \mapsto v') \in \mathbf{d}$                                                     | [TODO]         |
| <a name="3.5">(3.5)</a>   | $\forall \mathbf{d} \in \mathbb{D}: \mathbf{d}[k] \equiv \\ \begin{cases} v & \text{if}\ \exists k : (k \mapsto v) \in \mathbf{d} \\ \none & otherwise \end{cases}$          | [TODO]         |
| <a name="3.6">(3.6)</a>   | $\forall \mathbf{d} \in \mathbb{D}, \mathbf{s} \subseteq K: \mathbf{d} \setminus \mathbf{s} \equiv \{ (k \mapsto v): (k \mapsto v) \in \mathbf{d}, k \not \in \mathbf{s} \}$ | [TODO]         |
| <a name="3.7">(3.7)</a>   | $\dict{K}{V} \subset \mathbb{D}$                                                                                                                                             | [TODO]         |
| <a name="3.8">(3.8)</a>   | $\dict{K}{V} \equiv \big \{ \{ (k \mapsto v) \mid k \in K \wedge v \in V \} \big \}$                                                                                         | [TODO]         |
| <a name="3.9">(3.9)</a>   | $\keys{\mathbf{d} \in \mathbb{D}} \equiv \{ k \mid \exists v : (k \mapsto v) \in \mathbf{d} \}$                                                                              | [TODO]         |
| <a name="3.10">(3.10)</a> | $\mathcal{V} (\mathbf{d} \in \mathbb{D}) \equiv \{ v \mid \exists k : (k \mapsto v) \in \mathbf{d} \}$                                                                       | [TODO]         |
| <a name="3.11">(3.11)</a> | $\forall \mathbf{d} \in \mathbb{D}, \mathbf{e} \in \mathbb{D}: \mathbf{d} \cup \mathbf{e} \equiv (\mathbf{d} \setminus \keys{\mathbf{e}}) \cup \mathbf{e}$                   | [TODO]         |
