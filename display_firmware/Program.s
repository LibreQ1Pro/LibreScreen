// Runs once at power-up: global variables, the settings kept in the screen's EEPROM, the first page.
// Globals are 4-byte signed integers only (a string needs a variable component on a page).
// The compiler is strict about spaces: none inside if(...) and none around the comma of an instruction.

// ---- globals ----
int sys0=0                      // scratch variables of the page events
int sys1=0
int sys2=0
int lang=2                      // screen language 0..12 (0 zh, 1 ru, 2 en, 3 ja, 4 fr, 5 de, 6 it, 7 es, 8 ko, 9 pt, 10 ar, 11 tr, 12 he)
int sleep_time=300              // seconds before the screen saver: 0 (never), 300, 900 or 1800
int sleep_counts=0              // seconds counted by the screen saver timer of the page
int max_dim=100                 // brightness while the screen is awake
int kbmode=1                    // keyboard page: what the typed text is (the host sets it before opening the page)
int kbmin=8                     // keyboard page: the shortest accepted text (the host sets it too)

// ---- system settings ----
bauds=115200
dims=100                        // brightness after power-up

// ---- settings kept in the EEPROM (written by the pages with wepo) ----
repo lang,100
if(lang<0||lang>12)
{
  lang=2
}
repo sleep_time,200
if(sleep_time!=0&&sleep_time!=300&&sleep_time!=900&&sleep_time!=1800)
{
  sleep_time=300
}

repo max_dim,300
if(max_dim<10||max_dim>100)
{
  max_dim=100
}
dim=max_dim

page ${page:boot_logo}
