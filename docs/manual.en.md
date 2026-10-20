# DaLogic 1.2.0 user manual

DaLogic is a desktop editor and simulator for digital logic circuits. Create a circuit, connect its ports and observe the signals. Editing and simulation work offline. Use View → Language to switch between English, Spanish and Catalan. The selection is saved for the next launch.

## Place and connect components

Choose a component in the left palette, then click the board to place it. You can also drag a palette button onto the board. Enter places the preview at the visible center; Escape or a right-click cancels placement. Double-click a switch to toggle it. Hold a button down to activate its output.

Click a port and then another port to connect them. Click empty space while routing to create bends. Double-click to finish with a free endpoint. Escape cancels routing. Double-click a junction to cycle its bridge direction. The first click on a wire selects it; the second creates a node. Right-click a wire for Create node, Change color or Delete. Right-click a component for Delete or Edit. Modules offer Delete and Change appearance; their colors and corner radius are saved with the project.

Use the wheel to zoom and the middle mouse button to pan. Select components to move them together. R rotates the selection by 90 degrees; H flips it horizontally. Delete removes the selection. View provides grid, snapping and orthogonal wire settings. Edit provides alignment, distribution and the undo history limit.

## Projects and history

File → New clears the current project after checking for unsaved changes. Open loads a `.dalogic` project; Save and Save As write it atomically. The application warns before replacing unsaved work. Undo and redo restore circuit edits, wiring and visual elements. Automatic recovery saves pending changes once per minute; after an unexpected exit the next normal launch offers to restore them.

The installed application stores preferences, recovery data, languages and the module library in the user's Windows profile. Projects and exports normally go under Documents/DaLogic. Uninstalling preserves personal data. `DALOGIC_DATA_DIR` selects another data directory. A second instance cannot use the same data directory simultaneously.

## Reusable modules

Select a group and choose Widgets → Create IC. Enter a name and choose a library folder. Combinational modules store a truth table; sequential modules retain an internal network and independent state for each instance. The application supports `.dmodule` formats 1, 1.1, 1.2 and 1.3. Format 1.3 includes native memory and bus ports. Format numbering is separate from the application version.

Search the IC tab by name and open its folders. Click an IC to place it. Right-click a library module and choose Rename to change both its displayed name and its `.dmodule` filename. Loaded instances referencing that file are updated. Duplicate names cannot replace another file. Right-click → Move to folder organizes the library.

To change only a placed instance's name, open its component properties, edit Module name and press Save. This name is stored in the project. Save IC also writes the module definition. User names, port identifiers and annotations retain their own spelling when the application language changes.

## Simulation and probes

The Simulation menu groups clock pause, full simulation pause, stepping, breakpoints and probes. View contains Theme, Language, zoom, fit, grid, snapping and orthogonal wires. The action bar wraps into rows and the visual palette stays inside the application.

F6 pauses or resumes clocks. F8 pauses all simulation, preserving pending events. F10 processes the next event batch; if idle, it advances the clocks. Select a component with inputs and press F9 to add a red breakpoint marker. When an input changes, the current batch is evaluated and simulation pauses before the following events. The marker turns orange and the view reveals the component. F10 applies the next batch; F8 resumes. Select marked components and press F9 to remove their markers. A mixed selection is marked together. Switches and clocks have no inputs and cannot be marked. Breakpoints are temporary session tools, not saved circuit data. F7 checks free inputs, missing sources, incompatible bus widths, tri-state conflicts and unknown signals. Double-click a diagnostic row to locate its element.

Ctrl+click a wire or port to add a probe. The Probes panel shows waveforms and lets you remove signals, clear history and export CSV or VCD. Capacity is configurable between 256 and 100,000 changes per signal, with a default of 10,000. Increasing capacity does not restore samples already discarded. Export captures before closing.

## Truth tables and export

Ctrl+Shift+F calculates a combinational truth table. Set unique column orders in the ordering dialog. Double-click a source or output label there to locate its component. Tables accept at most 16 input bits, or 65,536 combinations. Large calculations have cancellable progress. Circuits with memory or feedback require time-based simulation instead of a combinational table.

Table filters search visible cell values. Export tables as PNG, PDF, SVG, XLSX or CSV. Ctrl+P exports the circuit as PNG, PDF or SVG. PNG resolution is limited for very large circuits; PDF and SVG preserve vectors. Visual components add editable text, squares, circles and named planes; they do not affect signals.

## Keyboard shortcuts

| Action | Shortcut |
| --- | --- |
| New / Open | Ctrl+N / Ctrl+O |
| Save / Save As | Ctrl+S or Ctrl+G / Ctrl+Shift+S |
| Copy / Cut / Paste / Duplicate | Ctrl+C / Ctrl+X / Ctrl+V / Ctrl+D |
| Undo / Redo | Ctrl+Z / Ctrl+Y |
| Fit / Zoom in / Zoom out | Ctrl+0 / Ctrl++ / Ctrl+- |
| Align / Distribute | Ctrl+Shift+A / Ctrl+Shift+D |
| Theme / Manual | Ctrl+Shift+T / F1 |
| Check circuit / Pause clocks | F7 / F6 |
| Pause simulation / Breakpoint / Step | F8 / F9 / F10 |

## Updates and credits

DaLogic may check the latest public release on GitHub over HTTPS. `--no-update-check` disables this request. Projects and logs are not uploaded by this check. Errors are recorded in `dalogic.log` with rotation. The About dialog retains attribution to David Lopez Borrego. DaLogic is licensed under Apache 2.0; redistributed dependencies retain their own notices.


In Help → Notify about updates, turn release checks and notifications on or off. This preference is saved. Enabling it checks for a release immediately. Disabling it also suppresses a response from a check already in progress.
