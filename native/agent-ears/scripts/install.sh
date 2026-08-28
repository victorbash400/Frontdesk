#!/bin/sh
set -eu

root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
product="$root/build/DerivedData/Build/Products/Release/AgentEars.driver"
destination=/Library/Audio/Plug-Ins/HAL/AgentEars.driver

"$root/scripts/test.sh"
test -d "$product"
sudo ditto "$product" "$destination"
sudo codesign --force --deep --sign - "$destination"
sudo killall coreaudiod

if ! system_profiler SPAudioDataType | grep -q "Agent Ears:"; then
  echo "Agent Ears did not appear after Core Audio restarted." >&2
  exit 1
fi

echo "Agent Ears is installed and visible to Core Audio."
