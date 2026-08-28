#include "AgentEarsRingBuffer.h"

#include <string.h>

void AgentEarsRingBufferReset(AgentEarsRingBuffer* buffer)
{
    memset(buffer->samples, 0, sizeof(buffer->samples));
    atomic_store_explicit(&buffer->readFrame, 0, memory_order_relaxed);
    atomic_store_explicit(&buffer->writeFrame, 0, memory_order_relaxed);
}

void AgentEarsRingBufferWrite(AgentEarsRingBuffer* buffer, const float* samples, uint32_t frameCount)
{
    uint64_t writeFrame = atomic_load_explicit(&buffer->writeFrame, memory_order_relaxed);
    uint64_t readFrame = atomic_load_explicit(&buffer->readFrame, memory_order_acquire);
    if (frameCount > AGENT_EARS_RING_FRAMES) {
        samples += (frameCount - AGENT_EARS_RING_FRAMES) * AGENT_EARS_CHANNELS;
        frameCount = AGENT_EARS_RING_FRAMES;
    }
    if (writeFrame + frameCount - readFrame > AGENT_EARS_RING_FRAMES) {
        readFrame = writeFrame + frameCount - AGENT_EARS_RING_FRAMES;
        atomic_store_explicit(&buffer->readFrame, readFrame, memory_order_release);
    }
    for (uint32_t frame = 0; frame < frameCount; ++frame) {
        const uint32_t ringFrame = (uint32_t)((writeFrame + frame) % AGENT_EARS_RING_FRAMES);
        memcpy(&buffer->samples[ringFrame * AGENT_EARS_CHANNELS],
               &samples[frame * AGENT_EARS_CHANNELS],
               sizeof(float) * AGENT_EARS_CHANNELS);
    }
    atomic_store_explicit(&buffer->writeFrame, writeFrame + frameCount, memory_order_release);
}

void AgentEarsRingBufferRead(AgentEarsRingBuffer* buffer, float* samples, uint32_t frameCount)
{
    const uint64_t writeFrame = atomic_load_explicit(&buffer->writeFrame, memory_order_acquire);
    uint64_t readFrame = atomic_load_explicit(&buffer->readFrame, memory_order_relaxed);
    const uint64_t available = writeFrame - readFrame;
    const uint32_t readable = available < frameCount ? (uint32_t)available : frameCount;
    for (uint32_t frame = 0; frame < readable; ++frame) {
        const uint32_t ringFrame = (uint32_t)((readFrame + frame) % AGENT_EARS_RING_FRAMES);
        memcpy(&samples[frame * AGENT_EARS_CHANNELS],
               &buffer->samples[ringFrame * AGENT_EARS_CHANNELS],
               sizeof(float) * AGENT_EARS_CHANNELS);
    }
    if (readable < frameCount) {
        memset(&samples[readable * AGENT_EARS_CHANNELS], 0,
               sizeof(float) * (frameCount - readable) * AGENT_EARS_CHANNELS);
    }
    readFrame += readable;
    atomic_store_explicit(&buffer->readFrame, readFrame, memory_order_release);
}
