# errors.py

_last_error = 0
_last_error_msg = "No error"

def get_last_error():
    return _last_error

def set_last_error(err_code, err_msg):
    global _last_error, _last_error_msg
    _last_error = err_code
    _last_error_msg = err_msg

def get_last_error_msg():
    return _last_error_msg
