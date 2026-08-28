#pragma once

#include <stdatomic.h>
#include <stdint.h>

#define AGENT_EARS_CHANNELS 2
#define AGENT_EARS_RING_FRAMES 32768

typedef struct {
    float samples[AGENT_EARS_RING_FRAMES * AGENT_EARS_CHANNELS];
    atomic_uint_fast64_t readFrame;
    atomic_uint_fast64_t writeFrame;
} AgentEarsRingBuffer;

void AgentEarsRingBufferReset(AgentEarsRingBuffer* buffer);
void AgentEarsRingBufferWrite(AgentEarsRingBuffer* buffer, const float* samples, uint32_t frameCount);
void AgentEarsRingBufferRead(AgentEarsRingBuffer* buffer, float* samples, uint32_t frameCount);
