"""Bounded JPEG input, native scaled decoding and explicit resource cleanup."""
import jpegdec
from time import ticks_ms, ticks_diff, sleep_ms


class JPEG(jpegdec.JPEGDecoder):
    """JPEG decoder; file streaming uses the firmware's two input buffers."""

    def __init__(self, screen_width=320, screen_height=320,
                 buffer_size=8192, buffer_num=2):
        super().__init__()
        if screen_width < 1 or screen_height < 1:
            raise ValueError('JPEG viewport must be positive')
        if buffer_num != 2 or buffer_size < 2048:
            raise ValueError('JPEG streaming needs two buffers of at least 2048 bytes')
        self._max_width, self._max_height = int(screen_width), int(screen_height)
        self._buffer_size, self._buffer_num = int(buffer_size), 2
        self._filebuffer = None
        self._buffers = [None, None]
        self._buffers_pos = [-1, -1]
        self._buffers_len = [0, 0]
        self._decoder_running = False
        self._closed = False
        self._file_pos = 0
        self.last_error = ''

    def draw(self, x, y, file_path, storage=None):
        """Decode a mounted SD JPEG; accept absolute paths and uppercase suffixes."""
        if self._closed: return False
        self.last_error = ''
        mounted = False
        try:
            if not file_path.lower().endswith(('.jpg', '.jpeg')):
                raise ValueError('Not a JPEG path')
            if storage and not storage.vfs_mounted:
                mounted = bool(storage.mount_vfs())
                if not mounted: raise OSError('Cannot mount SD card')
            if not file_path.startswith('/'):
                prefix = getattr(storage, 'vfs_prefix', '/sd') if storage else '/sd'
                if file_path.startswith('sd/'): file_path = '/'+file_path
                else: file_path = prefix.rstrip('/')+'/'+file_path
            with open(file_path, 'rb') as handle:
                handle.seek(0, 2); size = handle.tell(); handle.seek(0)
                # Small files fit in less memory than the two streaming buffers.
                if 0 < size <= self._buffer_size:
                    data = bytearray(size); view = memoryview(data); count = 0
                    while count < size:
                        n = handle.readinto(view[count:])
                        if not n: raise OSError('Truncated JPEG file')
                        count += n
                    return self._decode_buffer(x, y, data)
                return self._decode_split(handle, size, x, y)
        except (OSError, ValueError, MemoryError) as exc:
            self.last_error = str(exc) or 'JPEG decoding failed'
            return False
        finally:
            self._cleanup()
            if mounted and storage:
                try: storage.unmount_vfs()
                except OSError: pass

    def draw_buffer(self, x, y, buf):
        """Decode borrowed JPEG bytes directly, without BytesIO or input copies."""
        if self._closed: return False
        self.last_error = ''
        try:
            return self._decode_buffer(x, y, buf)
        except (OSError, ValueError, MemoryError) as exc:
            self.last_error = str(exc) or 'JPEG decoding failed'
            return False
        finally:
            self._cleanup()

    def _decode_buffer(self, x, y, data):
        info = self._dimensions(data)
        if not info[0]: raise ValueError('Invalid or unsupported JPEG header')
        width, height = info[1:]
        scale, offset = self._get_scale(width, height, x, y)
        result = self.decode_opt(data, (x+offset[0], y+offset[1]),
                                 (0, 0, width, height), self._get_option(scale))
        if not result[0]: self.last_error = 'Native JPEG decoding failed'
        return bool(result[0])

    @staticmethod
    def _dimensions(data):
        """Find a baseline SOF without building Huffman tables twice."""
        size = len(data)
        if size < 4 or data[0] != 255 or data[1] != 216: return False, 0, 0
        pos = 2
        while pos < size:
            if data[pos] != 255: return False, 0, 0
            while pos < size and data[pos] == 255: pos += 1
            if pos == size: break
            marker = data[pos]; pos += 1
            if marker in (216, 1) or 208 <= marker <= 215: continue
            if marker in (217, 218) or pos+2 > size: break
            length = (data[pos] << 8) | data[pos+1]
            if length < 2 or pos+length > size: break
            if marker == 192:  # baseline Huffman JPEG, as supported by JPEGDEC
                if length < 8 or data[pos+2] != 8: break
                height = (data[pos+3] << 8) | data[pos+4]
                width = (data[pos+5] << 8) | data[pos+6]
                return bool(width and height), width, height
            if marker in (193, 194, 195, 197, 198, 199, 201, 202, 203, 205, 206, 207): break
            pos += length
        return False, 0, 0

    def _init_buffers(self):
        if self._filebuffer is None:
            self._filebuffer = bytearray(self._buffer_size*2)
            view = memoryview(self._filebuffer)
            self._buffers = [view[:self._buffer_size], view[self._buffer_size:]]

    def _cleanup(self):
        if getattr(self, '_decoder_running', False):
            try: self.decode_core_wait(1)  # cancel a worker blocked on input
            finally: self._decoder_running = False

    def close(self):
        """Release retained buffers and, on updated firmware, the native context."""
        if getattr(self, '_closed', False): return
        self._cleanup()
        self._buffers = [None, None]; self._filebuffer = None
        close = getattr(super(), 'close', None)
        if close: close()
        self._closed = True

    def __del__(self):
        self.close()

    def _get_option(self, scale):
        return {1:0, 0.5:2, 0.25:4, 0.125:8}[scale]

    def _get_scale(self, width, height, x=0, y=0):
        available_w = self._max_width-max(0, int(x))
        available_h = self._max_height-max(0, int(y))
        for divisor in (1, 2, 4, 8):
            sw, sh = (width+divisor-1)//divisor, (height+divisor-1)//divisor
            if sw <= available_w and sh <= available_h:
                return 1/divisor, ((available_w-sw)//2, (available_h-sh)//2)
        raise ValueError('JPEG is too large even at 1/8 scale')

    def _test_buffer(self, pos, length):
        found, free = -1, 0
        for i in range(2):
            start, size = self._buffers_pos[i], self._buffers_len[i]
            if start < 0 or start+size <= pos: free |= 1 << i
            if start >= 0 and start <= pos and pos+length <= start+size: found = i
        return found, free

    def _fill(self, handle, index, pos, size, publish=True):
        expected = min(self._buffer_size, size-pos)
        if expected <= 0: return False
        if self._file_pos != pos: handle.seek(pos)
        buf = self._buffers[index]; count = 0
        while count < expected:
            n = handle.readinto(buf[count:expected])
            if not n: raise OSError('Truncated JPEG input')
            count += n
        self._file_pos = pos+count
        self._buffers_pos[index], self._buffers_len[index] = pos, count
        if publish and not self.decode_split_buffer(index, pos, buf[:count]):
            raise ValueError('JPEG input buffer rejected')
        return True

    def _start_split(self, size, first, x, y):
        # Older firmware initializes split headers on the feeding core. A bounded
        # getinfo probe is needed there to reject headers outside the first block.
        info = self._dimensions(first) if getattr(jpegdec, 'SPLIT_PREFIX_SAFE', False) else self.getinfo(first)
        if not info[0]: raise ValueError('JPEG header is unsupported or exceeds the first input buffer')
        scale, offset = self._get_scale(info[1], info[2], x, y)
        self._decoder_running = True  # also cover an exception returning the tuple
        result = self.decode_split(size, first, (x+offset[0], y+offset[1]), None, self._get_option(scale))
        self._decoder_running = bool(result[0])
        if not result[0]: self.last_error = 'Native JPEG header initialization failed'
        return bool(result[0])

    def _decode_split(self, handle, size, x, y):
        self._cleanup()
        if size <= 0: raise ValueError('Empty JPEG file')
        self._init_buffers()
        self._buffers_pos = [-1, -1]; self._buffers_len = [0, 0]
        self._file_pos = 0
        handle.seek(0)
        self._fill(handle, 0, 0, size, False)
        first = self._buffers[0][:self._buffers_len[0]]
        if not self._start_split(size, first, x, y): return False
        self._fill(handle, 1, self._buffers_len[0], size)
        progress = ticks_ms(); previous = None
        while True:
            status, pos, length, index = self.decode_split_wait()
            if status != 0:
                if status == 1: self._decoder_running = False
                ok = status == 1 and pos == 1
                if not ok: self.last_error = 'Native JPEG decoding failed'
                return ok
            request = (pos, length)
            if request != previous:
                progress = ticks_ms(); previous = request
            if pos >= 0:
                cached, free = self._test_buffer(pos, length)
                if length > 0 and cached < 0:
                    if pos >= size: raise OSError('JPEG requested data beyond EOF')
                    # The worker has paused waiting for this exact position.
                    target = next((i for i in range(2) if free & (1 << i)), 0)
                    self._fill(handle, target, pos, size)
                    progress = ticks_ms(); continue
                if length == 0 and free:
                    end = max(self._buffers_pos[i]+self._buffers_len[i] for i in range(2))
                    target = next(i for i in range(2) if free & (1 << i))
                    if self._fill(handle, target, end, size):
                        progress = ticks_ms(); continue
            if ticks_diff(ticks_ms(), progress) > 10000:
                raise OSError('JPEG decoder stalled')
            sleep_ms(1)
