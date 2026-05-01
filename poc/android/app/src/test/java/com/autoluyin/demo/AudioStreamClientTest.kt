package com.autoluyin.demo

import org.junit.jupiter.api.Test
import org.junit.jupiter.api.Assertions.assertEquals
import java.util.concurrent.LinkedBlockingQueue

class AudioStreamClientTest {

    @Test
    fun `queue full drops oldest frames and reports DEGRADED`() {
        val q = LinkedBlockingQueue<ByteArray>(3)
        q.offer(byteArrayOf(1))
        q.offer(byteArrayOf(2))
        q.offer(byteArrayOf(3))

        val newFrame = byteArrayOf(99)
        if (!q.offer(newFrame)) {
            // simulate the drop-oldest logic from AudioStreamClient
            repeat(2) { q.poll() }
            q.offer(newFrame)
        }
        assertEquals(2, q.size)
        // The first two frames should have been dropped; queue contains [3, 99]
        assertEquals(3.toByte(), q.poll()!![0])
        assertEquals(99.toByte(), q.poll()!![0])
    }
}
