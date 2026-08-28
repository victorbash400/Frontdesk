#pragma once

#include <stdatomic.h>
#include <stdint.h>

#define AGENT_MIKE_CHANNELS 2
#define AGENT_MIKE_RING_FRAMES 32768

typedef struct {
    float samples[AGENT_MIKE_RING_FRAMES * AGENT_MIKE_CHANNELS];
    atomic_uint_fast64_t readFrame;
    atomic_uint_fast64_t writeFrame;
} AgentMikeRingBuffer;

void AgentMikeRingBufferReset(AgentMikeRingBuffer* buffer);
void AgentMikeRingBufferWrite(AgentMikeRingBuffer* buffer, const float* samples, uint32_t frameCount);
void AgentMikeRingBufferRead(AgentMikeRingBuffer* buffer, float* samples, uint32_t frameCount);
