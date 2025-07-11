# gpucpu-fancontrol


## Prerequisites

- [ ] Linux `ipmitool`, `nvidia-smi` and optionally `sensors` packages.

## Installing? Easy. Peasy. Lemon Squeezy.

- [ ] 1. Upload systemd service file `gpu-cpu-fan-control.service` to the specified directory on Dell R730xd hardware (NO VM'S, duh).
- [ ] 2. Upload `gpu-cpu-fan-control.sh` *OR* `gpu-cpu-fan-control.py` to the specified directory on Dell R730xd hardware.
- [ ] 3. Uncomment the appropriate line to enable the bash or python script in the .system service file from step 1.
- [ ] 4. Run the 3 commands (using sudo, or as root) below to enable and start the service:

```
systemctl daemon-reload
systemctl enable gpu-cpu-fan-control.service
systemctl start gpu-cpu-fan-control.service
```
- [ ] 5. Check to make sure the service isn't buggered by running the following command (using sudo, or as root):

```
journalctl -u gpu-cpu-fan-control.service -f
```
***

## Name
GPU-CPU Fan Control

## Description
Keeps your Dell R730xd/Intel Xeon CPUs & Nvidia GPU from becoming lava, while also keeping your server fans from sounding like a widebody jet at takeoff thrust.

## Usage
Install it per the above instructions, set it up as a SystemD service. Fire, and forget it.

## Support
You can put in a comment on GitHub or DM me.

## Roadmap
Fun project, if anyone wants to contribute. Go for it!

## Authors and acknowledgment
Aiman Al-Khazaali, and my employer **Elemental Genius**

## Project status
Stable, don't duck it up (too badly).
