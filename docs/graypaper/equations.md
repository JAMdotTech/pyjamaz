# Graypaper Equations
The aim of this section is to provide a detailed implementation reference on Graypaper equation definitions.
This section has been updated to match Graypaper version 0.5.4. 

## Test Latex Parsing
When \(a \ne 0\), there are two solutions to \(ax^2 + bx + c = 0\) and they are
$$x = {-b \pm \sqrt{b^2-4ac} \over 2a}.$$

## Documentation Findings:
2. Graypaper "\none"  translated to  LaTeX "\varnothing" and not "\empty"
4. No support for \textsc
5. No support for zodiac symbols \Taurus \Zodiac{5}
6. No support for \token
7. No support for \emph replace by \textit
8. No Support for \orderedin
9. No support for \lseq (sequences) [
10. No support for \rseq (sequences) ]
11. No support for \bm (sequences) empty
12. \lightning
13. \raisebox{6pt} 
14. \rotatebox{180} 
15. \textsf
16. \nicefrac
17. escape | in MD-table -> \mid
