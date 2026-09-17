import struct

from app.audiosocket import FRAME_BYTES_8K, _frame, _resample_pcm


def test_audiosocket_frame_header():
    payload = b"1234"
    packet = _frame(0x10, payload)
    assert packet[0] == 0x10
    assert struct.unpack(">H", packet[1:3])[0] == 4
    assert packet[3:] == payload


def test_resample_8k_to_16k_doubles_sample_count():
    pcm_8k = b"\x00\x00" * 160
    pcm_16k = _resample_pcm(pcm_8k, 8000, 16000)
    assert len(pcm_16k) == 640


def test_phone_frame_size_is_20ms():
    assert FRAME_BYTES_8K == 320
