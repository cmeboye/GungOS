#pragma once

#if defined(PICOCALC)
#define SD_SPI (spi0)
#define SD_MISO (16)   // master in, slave out (MISO)
#define SD_CS (17)     // chip select (CS)
#define SD_SCK (18)    // serial clock (SCK)
#define SD_MOSI (19)   // master out, slave in (MOSI)
#define SD_DETECT (22) // card detect (CD)
#endif
