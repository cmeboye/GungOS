/* Host stand-in: no RTC, so the driver stamps files 2020-01-01. */
#pragma once
#include <stdbool.h>
#include <time.h>
static inline bool aon_timer_get_time_calendar(struct tm *t)
{
    (void)t;
    return false;
}
