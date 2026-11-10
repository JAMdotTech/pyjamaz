Offender evidence is checked against the prior punish-set (GP 0.8.0 equations
10.6--10.7). The culprit and fault lists must each have unique keys (10.9),
but the same validator may appear in both lists in one block.

The posterior punish-set contains that key once (10.18). The header offenders
marker concatenates culprit keys followed by fault keys, preserving the key's
two occurrences and the order of each list (10.19).

::: pyjamaz.state.components.Disputes
