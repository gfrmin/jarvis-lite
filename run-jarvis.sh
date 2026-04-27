#!/bin/bash
while true; do
    cd /home/g/git/jarvis-lite
    claude
    echo "Claude exited, restarting in 10s..."
    sleep 10
done
