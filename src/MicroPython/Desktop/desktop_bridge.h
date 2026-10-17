#pragma once

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

void desktop_log_message(const char *message);
size_t desktop_storage_file_size(const char *path);
size_t desktop_storage_file_read(const char *path, void *buffer,
                                 size_t buffer_size);
size_t desktop_storage_file_read_chunk(const char *path, void *buffer,
                                       size_t buffer_size, size_t offset);
bool desktop_storage_file_write(const char *path, const void *buffer,
                                size_t buffer_size);
void *desktop_storage_file_open(const char *path);
size_t desktop_storage_file_read_file_chunk(void *handle, void *buffer, size_t size);
void *desktop_storage_file_write_open(const char *path);
void desktop_storage_file_close(void *handle);
bool desktop_storage_file_write_file_chunk(void *handle, const void *data,
                                           size_t size);

bool desktop_http_get_response(void *buffer, size_t buffer_size);
bool desktop_http_is_finished(void);
bool desktop_http_send_request(const char *url, const char *method,
                               const char *headers, const char *payload);
bool desktop_http_get_websocket_response(void *buffer, size_t buffer_size);
bool desktop_http_websocket_is_connected(void);
bool desktop_http_websocket_send(const char *message);
bool desktop_http_websocket_start(const char *url, int port);
bool desktop_http_websocket_stop(void);

#ifdef __cplusplus
}
#endif
