import os
import subprocess
import platform
import ctypes

# windows dialog structure
if platform.system().lower() == 'windows':
    from ctypes.wintypes import DWORD, WORD, LPWSTR, LPCWSTR, HWND
    class OPENFILENAME(ctypes.Structure):
        _fields_ = [
            ('lStructSize', DWORD),
            ('hwndOwner', HWND),
            ('hInstance', ctypes.c_void_p),
            ('lpstrFilter', LPCWSTR),
            ('lpstrCustomFilter', LPWSTR),
            ('nMaxCustFilter', DWORD),
            ('nFilterIndex', DWORD),
            ('lpstrFile', LPWSTR),
            ('nMaxFile', DWORD),
            ('lpstrFileTitle', LPWSTR),
            ('nMaxFileTitle', DWORD),
            ('lpstrInitialDir', LPCWSTR),
            ('lpstrTitle', LPCWSTR),
            ('Flags', DWORD),
            ('nFileOffset', WORD),
            ('nFileExtension', WORD),
            ('lpstrDefExt', LPCWSTR),
            ('lCustData', ctypes.c_void_p),
            ('lpfnHook', ctypes.c_void_p),
            ('lpTemplateName', LPCWSTR),
            ('pvReserved', ctypes.c_void_p),
            ('dwReserved', DWORD),
            ('FlagsEx', DWORD),
        ]

def get_save_dialog(title="Save As", default_name="", file_types=None):
    """Show native save file dialog without external dependencies."""
    system = platform.system().lower()
    
    # Ensure default_name has proper extension
    if default_name and file_types:
        # Get extension from the requested format
        current_ext = os.path.splitext(default_name)[1]
        if not current_ext:
            # If no extension, add it from first file type
            ext = file_types[0][1].split('*')[-1].split(';')[0]
            default_name = f"{default_name}{ext}"
        elif current_ext != file_types[0][1].split('*')[-1].split(';')[0]:
            # If extension doesn't match requested format, replace it
            base_name = os.path.splitext(default_name)[0]
            ext = file_types[0][1].split('*')[-1].split(';')[0]
            default_name = f"{base_name}{ext}"

    if system == 'darwin':  # macOS, need to test or gather feedback on whether mac and windows work
        script = '''
        tell application "System Events"
            activate
            set theFile to choose file name with prompt "{title}" default name "{default_name}"
            return POSIX path of theFile
        end tell
        '''.format(title=title, default_name=default_name)
        
        try:
            process = subprocess.Popen(['osascript', '-e', script], 
                                    stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE)
            stdout, _ = process.communicate()
            path = stdout.decode('utf-8').strip()
            return path if path else None
        except:
            return None

    elif system == 'windows':  # windows, need to test or gather feedback on whether mac and windows work
        import ctypes
        from ctypes.wintypes import LPCWSTR, LPWSTR
        
        lpszFile = ctypes.create_unicode_buffer(1024)
        if default_name:
            lpszFile.value = default_name

        OFN_OVERWRITEPROMPT = 0x00000002
        
        # create filter string from file_types
        if file_types:
            filter_string = ""
            for desc, exts in file_types:
                exts_list = exts.split(';')
                for ext in exts_list:
                    filter_string += f"{desc}\0{ext}\0"
        else:
            filter_string = "All Files (*.*)\0*.*\0"

        ofn = OPENFILENAME()
        ofn.lStructSize = ctypes.sizeof(OPENFILENAME)
        ofn.lpstrFilter = LPCWSTR(filter_string)
        ofn.lpstrFile = lpszFile
        ofn.nMaxFile = 1024
        ofn.lpstrTitle = LPCWSTR(title)
        ofn.Flags = OFN_OVERWRITEPROMPT
        if default_name:
            ofn.lpstrDefExt = LPCWSTR(os.path.splitext(default_name)[1][1:])

        # show dialog
        if ctypes.windll.comdlg32.GetSaveFileNameW(ctypes.byref(ofn)):
            return lpszFile.value
        return None

    else:  # Linux/Unix, worked for now, might have issues with some distros
        # format filename with extension
        full_path = default_name
        if file_types and not os.path.splitext(default_name)[1]:
            ext = file_types[0][1].split('*')[-1].split(';')[0]
            full_path = f"{default_name}{ext}"

        try:
            if 'KDE_FULL_SESSION' in os.environ:
                process = subprocess.Popen([
                    'kdialog', '--getsavefilename', 
                    full_path or ".", title
                ], stdout=subprocess.PIPE)
            else:  # default to zenity (GNOME and others)
                process = subprocess.Popen([
                    'zenity', '--file-selection', 
                    '--save', '--title', title,
                    '--filename', full_path
                ], stdout=subprocess.PIPE)
            
            stdout, _ = process.communicate()
            path = stdout.decode('utf-8').strip()
            return path if path else None
        except:
            return None

    return None
