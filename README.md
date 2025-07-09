# gpucpu-fancontrol


## Prerequisites

- [ ] Linux `ipmitool` and `sensors` packages.

## Installing? Easy. Peasy. Lemon Squeezy.

- [ ] 1. Copy the two files in place on to Dell R730xd hardware (NO VM'S, duh).
- [ ] 2. Run the 3 commands (using sudo, or as root) below to enable and start the service:

```
systemctl daemon-reload
systemctl enable gpu-cpu-fan-control.service
systemctl start gpu-cpu-fan-control.service
```
***

## Name
GPU-CPU Fan Control

## Description
Keeps your Dell R730xd/Intel Xeon CPUs & Nvidia GPU from becoming lava, while also keeping your fans from sounding like a widebody jet at takeoff thrust.

## Usage
Install it per the above instructions, set it up as a SystemD service. Fire, and forget it.

## Support
You can put in a comment on GitHub or DM me.

## Roadmap
Fun project, if anyone wants to contribute. Go for it!

## Authors and acknowledgment
Aiman Al-Khazaali

## Project status
Stable, don't duck it up (too badly).
