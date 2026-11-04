"""Checks librescreen/network.py against the NetworkManager of the real printer (nothing of it is run on the host).

Copy librescreen_py to the printer and run as root there:  sudo python3 check_network.py
It lists the interfaces and the saved Wi-Fi connections, then makes a dummy saved connection ("librescreen:test", no
autoconnect), toggles autoconnect, tries to connect it with a new password (it fails: the network does not exist,
this takes about 25 seconds), forgets it, and deletes it again if anything went wrong. Other connections are not touched.
"""
import sys, subprocess; sys.path.insert(0, "/home/mks/librescreen_py")   # where the port is installed
from librescreen import network as n
subprocess.run(["nmcli","con","add","type","wifi","ifname","*","con-name","librescreen:test","ssid","librescreen-test-net","connection.autoconnect","no"],check=True,stdout=subprocess.DEVNULL)
try:
    items = n.saved_wifi(); print("saved:", items)
    it = [i for i in items if i["name"] == "librescreen:test"][0]
    print("autoconnect off->on:", n.set_autoconnect(it["uuid"], True), [i["autoconnect"] for i in n.saved_wifi() if i["name"]=="librescreen:test"])
    print("report wifi:", n.device_report("wifi")); print("report eth:", n.device_report("ethernet"))
    print("radio:", n.wifi_radio())
    import time; t=time.time(); print("connect_saved w/ new psk (expected False):", n.connect_saved(it["uuid"], "password123"), round(time.time()-t,1),"s")
    print("sec after:", subprocess.run(["nmcli","-t","-f","802-11-wireless-security.key-mgmt","con","show","uuid",it["uuid"]],stdout=subprocess.PIPE).stdout.decode())
    print("forget:", n.forget(it["uuid"]), [i["name"] for i in n.saved_wifi()])
finally:
    subprocess.run(["nmcli","con","delete","id","librescreen:test"],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
