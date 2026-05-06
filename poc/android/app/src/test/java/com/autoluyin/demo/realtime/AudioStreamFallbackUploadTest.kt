package com.autoluyin.demo.realtime

import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Assertions.assertNotNull
import org.junit.jupiter.api.Assertions.assertNull
import org.junit.jupiter.api.Assertions.assertTrue
import org.junit.jupiter.api.Test
import org.junit.jupiter.api.io.TempDir
import java.io.File
import java.io.FileOutputStream

/**
 * Sprint 12 (T4) — verifies the FALLBACK_LOCAL → upload contract.
 *
 * AudioStreamClient.start() depends on Android's AudioRecord, which is
 * not available in pure JVM unit tests. This test instead drives the
 * fallback path via reflection: pre-populate the internal PCM file,
 * then invoke the public stopAndCollectWav() and assert:
 *   1. it returns a non-null File
 *   2. that File is a valid WAV (RIFF/WAVE magic header).
 *
 * The actual upload via /api/v1/calls/upload is exercised by the backend
 * test suite — we only verify the producer side contract here.
 */
class AudioStreamFallbackUploadTest {

    private fun newClient(): AudioStreamClient = AudioStreamClient(
        callId = 42L,
        token = "test-token",
        onTranscript = {},
        onSuggestion = { _, _ -> },
        onTagReady = {},
        onStateChange = {},
    )

    /** Reflection helper: write a private field on the client. */
    private fun setPrivate(target: AudioStreamClient, name: String, value: Any?) {
        val f = AudioStreamClient::class.java.getDeclaredField(name)
        f.isAccessible = true
        f.set(target, value)
    }

    @Test
    fun `stopAndCollectWav returns null when no fallback file was started`() {
        val client = newClient()
        // No fallback ever started → finalize returns null
        val result = client.stopAndCollectWav()
        assertNull(result, "expected null when fallback was never engaged")
    }

    @Test
    fun `stopAndCollectWav returns non-null File when fallback PCM exists`(@TempDir tmp: File) {
        val client = newClient()

        // Simulate the FALLBACK_LOCAL path having captured ~1s of 16kHz mono PCM
        val pcm = File(tmp, "call_42_fallback.pcm")
        val pcmBytes = ByteArray(16000 * 2) { (it and 0xff).toByte() }
        FileOutputStream(pcm).use { it.write(pcmBytes) }

        setPrivate(client, "fallbackFile", pcm)
        setPrivate(client, "fallbackOutputStream", null)

        val wav = client.stopAndCollectWav()
        assertNotNull(wav, "expected a WAV file when PCM exists")
        assertTrue(wav!!.exists(), "WAV file should exist on disk")
        assertTrue(wav.length() > pcmBytes.size, "WAV should be larger than raw PCM (header)")
        assertEquals("wav", wav.extension)
        // Original PCM file is consumed
        assertTrue(!pcm.exists(), "PCM source should be deleted after WAV finalization")
    }

    @Test
    fun `WAV file produced by fallback has valid RIFF header`(@TempDir tmp: File) {
        val client = newClient()
        val pcm = File(tmp, "call_42_riff.pcm")
        // 200 ms of silence is enough to verify header layout
        FileOutputStream(pcm).use { it.write(ByteArray(16000 * 2 / 5)) }
        setPrivate(client, "fallbackFile", pcm)
        setPrivate(client, "fallbackOutputStream", null)

        val wav = client.stopAndCollectWav()!!
        val bytes = wav.readBytes()
        assertTrue(bytes.size >= 44, "WAV must contain at least the 44-byte header")

        // Magic bytes
        assertEquals("RIFF", String(bytes.copyOfRange(0, 4)))
        assertEquals("WAVE", String(bytes.copyOfRange(8, 12)))
        assertEquals("fmt ", String(bytes.copyOfRange(12, 16)))
        assertEquals("data", String(bytes.copyOfRange(36, 40)))

        // PCM format = 1 (LE), 16-bit mono @ 16 kHz
        val audioFormat = (bytes[20].toInt() and 0xff) or ((bytes[21].toInt() and 0xff) shl 8)
        val channels = (bytes[22].toInt() and 0xff) or ((bytes[23].toInt() and 0xff) shl 8)
        val sampleRate = (bytes[24].toInt() and 0xff) or
            ((bytes[25].toInt() and 0xff) shl 8) or
            ((bytes[26].toInt() and 0xff) shl 16) or
            ((bytes[27].toInt() and 0xff) shl 24)
        val bitsPerSample = (bytes[34].toInt() and 0xff) or ((bytes[35].toInt() and 0xff) shl 8)
        assertEquals(1, audioFormat, "PCM format")
        assertEquals(1, channels, "mono")
        assertEquals(16000, sampleRate, "sample rate")
        assertEquals(16, bitsPerSample, "bits/sample")
    }

    @Test
    fun `empty PCM yields null and cleans up the source file`(@TempDir tmp: File) {
        val client = newClient()
        val pcm = File(tmp, "call_42_empty.pcm")
        pcm.createNewFile()
        setPrivate(client, "fallbackFile", pcm)
        setPrivate(client, "fallbackOutputStream", null)

        val wav = client.stopAndCollectWav()
        assertNull(wav, "empty PCM should not produce a WAV")
        assertTrue(!pcm.exists(), "empty PCM should be removed")
    }
}
