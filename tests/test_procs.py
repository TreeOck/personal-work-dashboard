from personal_tracker import procs


def test_no_console_window_flag_only_on_windows():
    assert procs.no_window("win32") == {"creationflags": 0x08000000}      # CREATE_NO_WINDOW
    assert procs.no_window("darwin") == {} and procs.no_window("linux") == {}
