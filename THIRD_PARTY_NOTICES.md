# Third-party notices

The GungOS/Picoware derivative is GNU GPLv3 software; the root `LICENSE` contains
the license text. Component notices and source headers are retained. The root
GPL notice does not override a component's own license.

| Component | Sources and notices |
|---|---|
| Picoware | `src/MicroPython/`; original copyright headers; root GPLv3 license |
| MicroPython | `vendor/micropython/LICENSE` (MIT), `ACKNOWLEDGEMENTS` and component notices |
| Lenia Orbium seed and parameters | Bert Chan (2018), MIT; `guides/Lenia-LICENSE.txt`; [original dataset](https://github.com/Chakazul/Lenia/blob/master/Python/animals.json), preset O2u |
| ulab | `src/MicroPython/ulab/upstream/LICENSE` (MIT), `source.json` |
| Pico SDK | `vendor/micropython/lib/pico-sdk/LICENSE.TXT`; component SPDX headers |
| picotool | `vendor/picotool/LICENSE.TXT`; bundled component notices such as clipp |
| TinyUSB, lwIP, BTstack, CYW43, Mbed TLS | Notices in their `vendor/micropython/lib/` directories |
| micropython-lib and Berkeley DB | Notices in their `vendor/micropython/lib/` directories |
| JPEGDEC | `src/MicroPython/JPEGDEC/LICENSE` and source headers |

Some dependencies, including BTstack and the CYW43 wireless firmware, have
component-specific license terms; read their preserved notices for your use.
Exact source revisions appear in `vendor/revisions.json`. This distribution
preserves the sources and notices used by the build.

## Optional audio

The public repository and default build omit the originally supplied Game Boy
Tetris recordings. No redistribution grant was supplied for them. Local originals
and converted files are excluded by Git; they are not relicensed under GPLv3.
Use your own recordings with suitable permissions for any audio-enabled release.
The converter and PCM player are software, separate from media rights.

## Public test keys

The pinned Mbed TLS tests and Pico SDK `tools/example_keys/` include upstream
public test/example private keys. These are preserved fixtures, not GungOS device
credentials. Never use those sample keys to sign a real release or protect data.
Other upstream test constants and example passwords remain with their source.

GPLv3 notice and source-distribution terms are available at
https://www.gnu.org/licenses/gpl-3.0.html. This software license does not grant
permission to redistribute unrelated recordings or third-party trademarks.
