#include "AgentEarsRingBuffer.h"

#include <assert.h>
#include <stdio.h>

static AgentEarsRingBuffer buffer;

static void test_underflow_is_silence(void)
{
    float output[8] = { 1, 1, 1, 1, 1, 1, 1, 1 };
    AgentEarsRingBufferReset(&buffer);
    AgentEarsRingBufferRead(&buffer, output, 4);
    for (size_t index = 0; index < 8; ++index)
        assert(output[index] == 0);
}

static void test_preserves_stereo_pcm(void)
{
    const float input[8] = { .1f, -.1f, .2f, -.2f, .3f, -.3f, .4f, -.4f };
    float output[8] = { 0 };
    AgentEarsRingBufferReset(&buffer);
    AgentEarsRingBufferWrite(&buffer, input, 4);
    AgentEarsRingBufferRead(&buffer, output, 4);
    for (size_t index = 0; index < 8; ++index)
        assert(output[index] == input[index]);
}

static void test_wraps_without_reordering(void)
{
    float input[(AGENT_EARS_RING_FRAMES + 16) * AGENT_EARS_CHANNELS];
    float output[16 * AGENT_EARS_CHANNELS] = { 0 };
    for (size_t index = 0; index < sizeof(input) / sizeof(input[0]); ++index)
        input[index] = (float)index;
    AgentEarsRingBufferReset(&buffer);
    AgentEarsRingBufferWrite(&buffer, input, AGENT_EARS_RING_FRAMES + 16);
    AgentEarsRingBufferRead(&buffer, output, 16);
    const size_t retainedStart = 16 * AGENT_EARS_CHANNELS;
    for (size_t index = 0; index < 16 * AGENT_EARS_CHANNELS; ++index)
        assert(output[index] == input[retainedStart + index]);
}

int main(void)
{
    test_underflow_is_silence();
    test_preserves_stereo_pcm();
    test_wraps_without_reordering();
    puts("Agent Ears ring buffer tests passed");
    return 0;
}
