#include "AgentMikeRingBuffer.h"

#include <assert.h>
#include <stdio.h>

static AgentMikeRingBuffer buffer;

static void test_underflow_is_silence(void)
{
    float output[8] = { 1, 1, 1, 1, 1, 1, 1, 1 };
    AgentMikeRingBufferReset(&buffer);
    AgentMikeRingBufferRead(&buffer, output, 4);
    for (size_t index = 0; index < 8; ++index)
        assert(output[index] == 0);
}

static void test_preserves_stereo_pcm(void)
{
    const float input[8] = { .1f, -.1f, .2f, -.2f, .3f, -.3f, .4f, -.4f };
    float output[8] = { 0 };
    AgentMikeRingBufferReset(&buffer);
    AgentMikeRingBufferWrite(&buffer, input, 4);
    AgentMikeRingBufferRead(&buffer, output, 4);
    for (size_t index = 0; index < 8; ++index)
        assert(output[index] == input[index]);
}

static void test_wraps_without_reordering(void)
{
    float input[(AGENT_MIKE_RING_FRAMES + 16) * AGENT_MIKE_CHANNELS];
    float output[16 * AGENT_MIKE_CHANNELS] = { 0 };
    for (size_t index = 0; index < sizeof(input) / sizeof(input[0]); ++index)
        input[index] = (float)index;
    AgentMikeRingBufferReset(&buffer);
    AgentMikeRingBufferWrite(&buffer, input, AGENT_MIKE_RING_FRAMES + 16);
    AgentMikeRingBufferRead(&buffer, output, 16);
    const size_t retainedStart = 16 * AGENT_MIKE_CHANNELS;
    for (size_t index = 0; index < 16 * AGENT_MIKE_CHANNELS; ++index)
        assert(output[index] == input[retainedStart + index]);
}

int main(void)
{
    test_underflow_is_silence();
    test_preserves_stereo_pcm();
    test_wraps_without_reordering();
    puts("Agent Mike ring buffer tests passed");
    return 0;
}
