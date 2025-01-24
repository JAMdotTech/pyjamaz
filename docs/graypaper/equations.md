# Graypaper Equations
The aim of this section is to provide a detailed implementation reference on Graypaper equation definitions.
This section has been updated to match Graypaper version 0.5.4. 

## Test Latex Parsing
When \(a \ne 0\), there are two solutions to \(ax^2 + bx + c = 0\) and they are
$$x = {-b \pm \sqrt{b^2-4ac} \over 2a}.$$

## Documentation Findings:
1. LaTeX parsing not triggered when using left navigation in MKDocs, only on refresh.
2. Graypaper "\none"  translated to  LaTeX "\varnothing" and not "\empty"
3. Javascript parsing error in equation 3.5: "<scripttype="math/tex;mode=display">"
