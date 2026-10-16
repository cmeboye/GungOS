"""Native wrappers, imported only on targets with a supported emitter."""
import micropython


def native_wrapper(func):
    @micropython.native
    def wrapper(*args, **kwargs):
        return func(*args, **kwargs)
    return wrapper


def viper_wrapper(func):
    @micropython.viper
    def wrapper():
        return func()
    return wrapper
