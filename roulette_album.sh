#!/bin/sh
sudo pkill -f roulette.sh
sudo pkill -f ashuffle
mpc clear
mpc consume off
ashuffle --group-by album &
