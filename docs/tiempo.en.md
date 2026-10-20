# Timing and feedback

DaLogic propagates signals using queued events. Signal delay in milliseconds and extra gate stages determine when component changes reach their destinations. Gate stages and elapsed milliseconds describe different aspects of propagation. A clock's interval controls how often it toggles.

F6 pauses clocks while the current propagation can continue. F8 pauses the full simulation and retains pending events. F10 applies the next simultaneous event batch; an idle circuit can advance its clocks. Use probes to inspect the resulting signal history. F9 toggles a breakpoint on selected components; a change at their input stops the simulation so you can examine it.

## Feedback and state

A combinational truth table represents outputs that depend only on current inputs. A circuit with feedback, memory, a counter or a register also depends on its previous state. DaLogic therefore refuses to calculate a combinational truth table for such a circuit. Use normal simulation, stepping and probes to observe it over time.

Create a sequential IC to retain feedback and memory inside a reusable module. Every placed instance has independent internal state. Saving and reopening a project preserves its state. The `.dmodule` format is chosen according to its contents: 1 stores scalar truth tables; 1.1 stores scalar sequential networks; 1.2 supports bus and X/Z truth tables; 1.3 adds native memory and buses to sequential networks.

An unstable feedback loop can produce unknown X values. If an oscillation or infinite loop is detected, simulation stops and clocks pause. Check the wiring and intended timing before resuming. Independent parts of a circuit can continue when a local feedback network resolves to X.

## Probes and diagnostics

Ctrl+click a wire or port to add a probe. Probe history is bounded: select a capacity from 256 to 100,000 changes per signal. Removing old samples does not change the circuit. CSV exports tabular events; VCD exports timestamped waveforms. Captures live in memory until exported or cleared.

F7 reports free inputs, nets without sources, incompatible bus widths, active tri-state driver conflicts, free wire endpoints and unknown X signals. Some free ports are intentional. Double-click a report row to locate the element. A diagnostic report does not change the electrical state of the circuit.

When wiring or deleting components, the editor rebuilds connections as a topology change rather than introducing artificial clock pulses. Native memory and nested sequential modules retain their stored state. X means an unknown logical value; Z represents a released bus. Neither should be interpreted as the Boolean value true.
