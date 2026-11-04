# Pictures of every page from the editor's emulator

Plugins for the live agent of the USART HMI editor (`QSART_Linux_EN`, "Live agent" in its README): no mouse and no keyboard automation.

1. Start the editor with the agent: `AGENT_DIR=/some/dir PROJECT=out/librescreen_vNN.HMI ./run.sh` (in `QSART_Linux_EN`).
2. Compile the plugins into `AGENT_DIR` (the agent runs a DLL when it appears or changes, and writes `<name>.out`):
   `wine "C:\windows\Microsoft.NET\Framework\v4.0.30319\csc.exe" /target:library /r:System.Windows.Forms.dll /r:System.Drawing.dll /out:Z:\...\snap_pages.dll Z:\...\snap_pages.cs`
3. `debug_open.cs`: presses *Debug* (the emulator opens; the editor must have finished loading the project).
4. In `AGENT_DIR` put `pages.txt` (one page name per line, the keys of `project.json`) and `outdir.txt` (the Windows path of the folder for the pictures), then run `snap_pages.cs`:
   for every page it types `page NAME` into the command box, calls the emulator's own `sendall()` (a click on the "run all code" button does nothing: the
   emulator sends on the mouse-up of the button) and saves the screen control as `NAME.png` (272 x 480).
5. `python3 tools/emulator/snap_sheets.py SNAPS pages.txt SHEETS` makes contact sheets.

The emulator has no host: values the host writes are empty (`---`), the Home page shows the version warning, the language is Chinese. Pages that are the same on the screen
(`error` / `gcode_error`, `filament_cold` / `print_cold`) give the same picture.
