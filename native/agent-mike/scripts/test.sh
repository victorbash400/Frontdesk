#!/bin/sh
set -eu

root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
build="$root/build"
mkdir -p "$build"

clang -std=c11 -Wall -Wextra -Werror \
  "$root/AgentMikeRingBuffer.c" \
  "$root/AgentMikeRingBufferTests.c" \
  -o "$build/agent-mike-ring-tests"
"$build/agent-mike-ring-tests"

xcodebuild \
  -project "$root/AgentMike.xcodeproj" \
  -scheme AgentMike \
  -configuration Release \
  -derivedDataPath "$build/DerivedData" \
  CODE_SIGNING_ALLOWED=NO \
  build
