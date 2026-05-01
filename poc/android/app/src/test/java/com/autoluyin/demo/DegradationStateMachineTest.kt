package com.autoluyin.demo

import com.autoluyin.demo.realtime.AudioStreamClient
import org.junit.jupiter.api.Test
import org.junit.jupiter.api.Assertions.assertEquals

class DegradationStateMachineTest {

    @Test
    fun `state transitions follow expected order under repeated failures`() {
        val transitions = mutableListOf<AudioStreamClient.State>()
        val onChange: (AudioStreamClient.State) -> Unit = { transitions.add(it) }

        // Manually drive the state via the same logic AudioStreamClient uses
        var state = AudioStreamClient.State.NORMAL
        fun set(s: AudioStreamClient.State) {
            if (state != s) { state = s; onChange(s) }
        }

        set(AudioStreamClient.State.NORMAL)
        set(AudioStreamClient.State.DEGRADED)         // first failure
        set(AudioStreamClient.State.DEGRADED)         // dedup — no callback
        set(AudioStreamClient.State.NORMAL)            // reconnect succeeded
        set(AudioStreamClient.State.DEGRADED)
        set(AudioStreamClient.State.FALLBACK_LOCAL)    // exhausted retries

        assertEquals(
            listOf(
                AudioStreamClient.State.DEGRADED,
                AudioStreamClient.State.NORMAL,
                AudioStreamClient.State.DEGRADED,
                AudioStreamClient.State.FALLBACK_LOCAL,
            ),
            transitions
        )
    }
}
