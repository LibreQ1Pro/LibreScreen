"""The TJC screen: serial port, instructions, events, pictures, page ids.

Page ids and widget ids correspond to the pages / components of the screen project
display_firmware/project.json (the page id is the position of the page in it).

NOTE: the port follows QIDI's xindi V4.4.22 binary (there are no sources of it) for the screen firmware
V4.4.24: page 81 became the network page, pages 94 and 95 were added; QIDI Link (QIDI's cloud) is not implemented,
the network page keeps it disabled ("LAN only").
"""
